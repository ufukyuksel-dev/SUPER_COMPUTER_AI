"""jev_task / jev_help (design design note plan-jev-chrome-agent.md (private)) with a fake TypeSafe client: no network.

The fake answers like a sensible model would from the state it receives, so these tests check the loop, the page
view, the done rule, the code-side selection, escalation and the continue-after-help contract, not model quality.
"""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from jev import agent as A
from jev.agent import Agent, TaskSpec, TaskStore, build_options, parse_price
from jev.browser import Element
from jev.pageview import PageView, Region, fit, next_chunk

from test_scenarios import base_url, browser  # noqa: F401  (fixtures: local server, own + ext backends)


def ch(choice, p=0.9, others=()):
    probs = {choice: p, **{o: (1 - p) / max(len(others), 1) for o in others}}
    return NS(choice=choice, confidence=p, probabilities=probs)


class FakeClient:
    """policy(state, questions) -> {"next": oid, "p": float, "done": float, "blocked": str, "value": key}"""

    def __init__(self, policy):
        self.policy, self.calls = policy, []

    async def system_one(self, state, questions):
        self.calls.append((state, questions))
        if "pairs" in state:  # field–value gate: search phrase -> search box, prices -> price fields only
            nouls = {}
            for qid in questions:
                pair = state["pairs"][int(qid[1:])]
                f, v = pair["field"].lower(), pair["value"]
                ok = ("inputs.query" in v and ("search" in f)) or ("inputs.max_price" in v and "price" in f) or \
                     ("inputs.rating" in v and "rating" in f)
                nouls[qid] = NS(noul=0.95 if ok else 0.03)
            return NS(choices={}, nouls=nouls, usage=NS(input_tokens=80))
        if "next" not in questions:  # card relevance (select)
            nouls = {}
            for qid in questions:
                text = state["cards"][int(qid[1:])]
                is_it = "Pro Console" in text and "Bundle" not in text and "Stand" not in text
                nouls[qid] = NS(noul=0.95 if is_it else 0.05)
            return NS(choices={}, nouls=nouls, usage=NS(input_tokens=100))
        d = self.policy(state, questions)
        opts = list(questions["next"].criteria)
        choices = {"next": ch(d["next"], d.get("p", 0.9), [o for o in opts if o != d["next"]][:2]),
                   "blocked": ch(d.get("blocked", "nothing"), 0.9)}
        if "value" in questions:
            choices["value"] = ch(d.get("value", "none"), 0.9)
        return NS(choices=choices, nouls={"done": NS(noul=d.get("done", 0.05))}, usage=NS(input_tokens=500))


def find_oid(questions, *words, kind="click"):
    for oid, desc in questions["next"].criteria.items():
        if oid.startswith(kind + ":") and all(w.lower() in desc.lower() for w in words):
            return oid
    raise AssertionError(f"no {kind} option with {words}: {list(questions['next'].criteria.values())[:20]}")


@pytest.fixture(autouse=True)
def tasks_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path))


# ---------------------------------------------------------------- pure units

@pytest.mark.parametrize("text, value", [("$749.99", 749.99), ("TRY 32,450.00", 32450.0), ("32.450 TL", 32450.0),
                                         ("€1.234,56", 1234.56), ("Price US$589", 589.0), ("See options", None)])
def test_parse_price(text, value):
    got = parse_price(text)
    assert (got[0] if got else None) == value


def el(i, role="link", text="x"):
    return Element(id=f"e{i}", role=role, tag="a", type="", text=f"{text}{i}", hint="", handle=None)


def test_options_never_exceed_255_including_generic():
    els = {f"e{i}": el(i) for i in range(400)}
    view = PageView("u", "t", [Region("r0", "card", "big list", list(els))], els)
    shown, groups = fit(view, "goal", 10**9)
    opts = build_options(view, shown, [{"gid": f"g{i}", "kinds": ["card"], "count": 3, "rids": [], "preview": ""}
                                       for i in range(4)], {}, ["r0", "r1", "r2", "r3"])
    kinds = {o.kind for o in opts}
    assert len(opts) <= A.MAX_OPTIONS and {"scroll", "back", "wait", "none", "ask", "show_more", "read_more"} <= kinds


def test_read_more_cursor_continues_and_ends():
    r = Region("r1", "text", "".join(chr(65 + i % 26) + str(i) for i in range(20)))  # unique, 50 chars
    c1, n1 = next_chunk(r, 0, 20)
    c2, n2 = next_chunk(r, n1, 20)
    c3, n3 = next_chunk(r, n2, 20)
    assert (c1 + c2 + c3) == r.text and n3 is None and c2 != c1


def test_budget_fit_reports_omitted_groups():
    regions = [Region(f"r{i}", "card", f"card number {i} " * 20, []) for i in range(30)]
    view = PageView("u", "t", regions, {})
    shown, groups = fit(view, "card number 3", 300)
    assert shown and groups and sum(g["count"] for g in groups) + len(shown) == 30 and len(groups) <= 4


# ---------------------------------------------------------------- page view on fixtures (both backends)

async def test_page_view_cards_carry_prices(browser, base_url):
    from jev.pageview import build
    await browser.open(f"{base_url}/s24_results.html")
    view = await build(browser)
    pro2 = next(r for r in view.regions if "Console (Renewed)" in r.text)
    assert "$589.00" in pro2.text and any(view.elements[e].role == "link" for e in pro2.eids)
    assert any(r.kind == "text" and "Results for your search" in r.text for r in view.regions)


# ---------------------------------------------------------------- whole task with the fake model

def shop_policy(state, questions):
    url = state["url"]
    if "s24_shop" in url:
        return {"next": find_oid(questions, "Search shop", kind="type"), "value": "query"}
    if "ok.html" in url:
        return {"next": "none", "done": 0.95}
    return {"next": "scroll", "p": 0.3}


async def test_task_search_then_cheapest_matching_listing(browser, base_url):
    client = FakeClient(shop_policy)
    spec = TaskSpec(goal="Open the cheapest PlayStation 5 Pro console listing", start_url=f"{base_url}/s24_shop.html",
                    inputs={"query": "PlayStation 5 Pro console"},
                    select={"item": "PlayStation 5 Pro console", "order_by": "price_asc"},
                    end_condition={"checks": [{"url_contains": "ok.html"}],
                                   "semantic": "the page of the chosen PlayStation 5 Pro console listing"})
    res = await Agent(browser, client).run(spec)
    assert res["status"] == "done", res
    assert "#pro2" in res["evidence"]["url"]            # $589 Pro (renewed): cheapest matching, not the $19.99 stand
    assert res["answer"]["price"] == 589.0 and "0 matching listings had no visible price" in res["answer"]["scope"]


async def test_task_prices_hidden_asks_for_help(browser, base_url):
    client = FakeClient(shop_policy)
    spec = TaskSpec(goal="Open the cheapest PlayStation 5 Pro console listing",
                    start_url=f"{base_url}/s25_results_noprice.html",
                    select={"item": "PlayStation 5 Pro console", "order_by": "price_asc"},
                    end_condition={"checks": [{"url_contains": "ok.html"}]})
    res = await Agent(browser, client).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "blocked"
    assert "none shows a price" in res["help"]["question"] and res["help"]["options"]


async def test_help_is_single_use_and_continues(browser, base_url):
    def policy(state, questions):
        if "s06_same_name_rows" in state["url"] and "OK" not in state["title"]:
            return {"next": "none"}  # Jev cannot decide -> needs_help
        return {"next": "none", "done": 0.95}
    agent = Agent(browser, FakeClient(policy))
    spec = TaskSpec(goal="Edit campaign B", start_url=f"{base_url}/s06_same_name_rows.html",
                    end_condition={"checks": [{"new_page_title_contains": "OK B"}]})
    res = await agent.run(spec)
    assert res["status"] == "needs_help"
    h = res["help"]
    store = TaskStore(res["task_id"])
    req = next(r for r in store.records() if r["kind"] == "help")
    # the caller picks "Düzenle" in row B (not necessarily in Jev's top 3): offer it through a clarify-free pick
    view_opts = [o for o in req["options"]]
    assert h["help_id"] and isinstance(h["page_version"], int) and view_opts is not None
    pick = next((o["oid"] for o in view_opts if "Kampanya B" in o["desc"]), None)
    if pick is None:  # fake top-3 may not include it: clarify instead (still exercises the contract)
        out = await agent.help(res["task_id"], h["help_id"], h["page_version"], {"clarify": "row Kampanya B"})
    else:
        out = await agent.help(res["task_id"], h["help_id"], h["page_version"], {"pick": pick})
    again = await agent.help(res["task_id"], h["help_id"], h["page_version"], {"pick": pick or "x"})
    assert again["status"] == "rejected" and "already used" in again["reason"]
    assert out["status"] in ("done", "needs_help")


async def test_intent_without_result_is_not_retried(browser, base_url):
    spec = TaskSpec(goal="g", start_url=f"{base_url}/s01_icon_aria.html", end_condition={"checks": []})
    store = TaskStore("crash1")
    from dataclasses import asdict
    store.add("spec", spec=asdict(spec))
    store.add("intent", option="click:e0", option_desc="click button: Ayarlar")
    await browser.open(f"{base_url}/s01_icon_aria.html")
    res = await Agent(browser, FakeClient(lambda s, q: {"next": "none"})).run(spec, task_id="crash1")
    assert res["status"] == "needs_help" and res["help"]["kind"] == "clarify"
    assert "may or may not have happened" in res["help"]["question"]


async def test_risky_action_needs_approval(browser, base_url):
    def policy(state, questions):
        return {"next": find_oid(questions, "Tümünü kabul et")}  # "kabul" is not risky; use a submit-like page
    agent = Agent(browser, FakeClient(lambda s, q: {"next": next(o for o in q["next"].criteria
                                                                 if o.startswith("click:"))}))
    await browser.open(f"{base_url}/s15_cookie.html")
    # rename a button to a risky word, Jev picks it -> approval required, not clicked
    if browser.kind == "own":
        await browser.page.evaluate("document.querySelector('a').textContent = 'Delete account'")
    else:
        await browser._call("browser_evaluate",
                            {"function": "() => { document.querySelector('a').textContent = 'Delete account'; }"})
    spec = TaskSpec(goal="g", end_condition={"checks": [{"url_contains": "never"}]})
    res = await agent.run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "approve", res


async def test_task_max_price_filters_in_code(browser, base_url):
    client = FakeClient(shop_policy)
    spec = TaskSpec(goal="Open the cheapest PlayStation 5 Pro console under $550",
                    start_url=f"{base_url}/s24_results.html",
                    select={"item": "PlayStation 5 Pro console", "order_by": "price_asc", "max_price": 550},
                    end_condition={"checks": [{"url_contains": "ok.html"}]})
    res = await Agent(browser, client).run(spec)
    # matching consoles cost $749.99 and $589: none ≤ 550 -> Jev asks instead of opening the $449 Slim or the stand
    assert res["status"] == "needs_help" and "none is at or below the maximum 550" in res["help"]["question"]


# ---------------------------------------------------------------- universal widgets (plan-universal-widgets.md)

async def test_widgets_found_with_state(browser, base_url):
    await browser.open(f"{base_url}/s26_widgets.html")
    els = {e.label: e for e in await browser.read_elements()}
    slider = next(e for e in els.values() if e.role == "slider" and "Max price" in e.text)
    assert slider.is_value_field() and not slider.is_text_field() and "$1050+" in slider.state
    assert any(e.role == "slider" and "Minimum rating" in e.text for e in els.values())
    assert any(e.role == "spinbutton" and "Quantity" in e.text for e in els.values())
    assert any(e.role == "searchbox" for e in els.values())
    if browser.kind == "own":  # the accessibility snapshot shows date/contenteditable differently
        assert any(e.type == "date" and e.is_value_field() for e in els.values())
        assert any(e.role == "textbox" and "Gift note" in e.text for e in els.values())


async def test_set_slider_reaches_largest_value_not_above_target(browser, base_url):
    await browser.open(f"{base_url}/s26_widgets.html")
    els = await browser.read_elements()
    price = next(e for e in els if e.role == "slider" and "Max price" in e.text)
    rating = next(e for e in els if e.role == "slider" and "Minimum rating" in e.text)
    assert await A.set_slider(browser, price, "550") == "$550"       # shown value, not the raw index 12
    assert await A.set_slider(browser, rating, "4") == "4 stars"      # ARIA slider moved up by keyboard


async def test_gate_keeps_price_out_of_the_search_box(browser, base_url):
    seen = {}

    def policy(state, questions):
        seen["opts"] = list(questions["next"].criteria.values())
        return {"next": "none"}
    spec = TaskSpec(goal="Filter max price 550", start_url=f"{base_url}/s26_widgets.html",
                    inputs={"query": "PlayStation 5 Pro", "max_price": "550"},
                    end_condition={"checks": [{"url_contains": "never"}]})
    await Agent(browser, FakeClient(policy)).run(spec)
    opts = seen["opts"]
    assert any("inputs.max_price" in o and "Max price" in o and o.startswith("set") for o in opts)
    assert not any("inputs.max_price" in o and "Search products" in o for o in opts)
    assert any("inputs.query" in o and "Search products" in o for o in opts)
