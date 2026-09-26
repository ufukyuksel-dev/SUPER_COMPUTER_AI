"""jev v4 (design note plan-jev-v4-fast-general.md (private)): snapshot, executor, value contract, completion rule and the task loop.

No network model: a fake TypeSafe client and a fake text helper. Browser tests run on both backends (own + ext).
"""

from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace as NS

import pytest

from jev import agent as A
from jev.agent import TaskSpec
from jev.v4 import values as V
from jev.v4.agent import AgentV4, final
from jev.v4.executor import Executor
from jev.v4.snapshot import Control, take

from test_scenarios import base_url, browser  # noqa: F401  (fixtures: local server, own + ext backends)

TODAY = dt.date(2026, 9, 24)  # Thursday


@pytest.fixture(autouse=True)
def tasks_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path))


# ---------------------------------------------------------------- completion rule (model-free)

@pytest.mark.parametrize("op, p, done_p, blocked, want", [
    ("DONE", 0.95, 0.30, "nothing", "ESCALATE"),
    ("DONE", 0.95, 0.90, "login", "ESCALATE"),
    ("CLICK", 0.90, 0.85, "nothing", "DONE"),
    ("CLICK", 0.40, 0.10, "nothing", "ESCALATE"),
    ("CLICK", 0.95, 0.10, "captcha", "ESCALATE"),
    ("TYPE", 0.95, 0.10, "login", "ESCALATE"),
    ("SET", 0.99, 0.10, "captcha", "ESCALATE"),
    ("CLICK", 0.90, 0.10, "data_not_available", "CLICK"),
    ("ASK", 0.99, 0.10, "nothing", "ESCALATE"),
    ("SCROLL_DOWN", 0.7, 0.2, "nothing", "SCROLL_DOWN"),
])
def test_final_rule(op, p, done_p, blocked, want):
    assert final(op, "j1", p, done_p, blocked)[0] == want



def test_back_is_not_low_threshold_navigation():
    # run 14: BACK at p 0.32 undid a verified cheapest pick; going back discards progress, so it keeps 0.5
    assert final("BACK", None, 0.32, 0.1, "nothing", nav_threshold=0.3)[0] == "ESCALATE"
    assert final("SCROLL_DOWN", None, 0.32, 0.1, "nothing", nav_threshold=0.3)[0] == "SCROLL_DOWN"

# ---------------------------------------------------------------- value contract v1.2 (model-free)

G = "On Amazon, search PlayStation 5 Pro and limit the price to at most 550 dollars"
SEARCH = {"label": "searchbox: Search Amazon", "role": "searchbox"}
SLIDER = {"label": "slider: Max price", "role": "slider", "state": "value $1050+", "min": 0, "max": 1050}
DEP = {"label": "textbox: Departure", "role": "textbox"}
FL = "Find one-way flights from Zurich to London on 20 October 2026"
TZ = "haftaya salı günü istanbul tuzlada hava kaç derece olacak"


@pytest.mark.parametrize("name, prop, field, goal, ok", [
    ("550 into search", {"value": "550", "role_in_goal": "max price", "goal_span": "550 dollars"}, SEARCH, G, False),
    ("query + limit", {"value": "PlayStation 5 Pro under 550", "role_in_goal": "search query",
                       "goal_span": "PlayStation 5 Pro"}, SEARCH, G, False),
    ("5500 for 550", {"value": "5500", "role_in_goal": "max price", "goal_span": "at most 550 dollars"}, SLIDER, G, False),
    ("span not in goal", {"value": "500", "role_in_goal": "max price", "goal_span": "max 500 $"}, SLIDER, G, False),
    ("out of range", {"value": "2000", "role_in_goal": "max price", "goal_span": "at most 2000"}, SLIDER,
     G + " at most 2000", False),
    ("wrong date", {"value": "2026-10-21", "role_in_goal": "date", "goal_span": "20 October 2026"}, DEP, FL, False),
    ("this week's tuesday", {"value": "2026-09-22", "role_in_goal": "date", "goal_span": "haftaya salı"}, DEP, TZ, False),
    ("EUR field, $ goal", {"value": "550", "unit": "EUR", "goal_span": "at most 550 dollars"},
     {"label": "textbox: Max price (€)", "role": "textbox"}, G, False),
    ("car is not carpet", {"value": "car", "role_in_goal": "search query", "goal_span": "search carpet"},
     {"label": "searchbox: Search", "role": "searchbox"}, "search carpet", False),
    ("email field", {"value": "a@b.c", "role_in_goal": "email", "goal_span": "newsletter"},
     {"label": "textbox: Email", "role": "textbox"}, "newsletter", False),
    ("query ok", {"value": "PlayStation 5 Pro", "role_in_goal": "search query", "goal_span": "PlayStation 5 Pro"},
     SEARCH, G, True),
    ("550 ok", {"value": "550", "unit": "$", "role_in_goal": "max price", "goal_span": "at most 550 dollars"},
     SLIDER, G, True),
    ("date ok", {"value": "2026-10-20", "role_in_goal": "date", "goal_span": "20 October 2026"}, DEP, FL, True),
    ("haftaya salı", {"value": "2026-09-29", "role_in_goal": "date", "goal_span": "haftaya salı"}, DEP, TZ, True),
    ("Turkish suffix", {"value": "Tuzla", "role_in_goal": "place", "goal_span": "istanbul tuzlada"},
     {"label": "textbox: İl veya ilçe ara", "role": "textbox"}, TZ, True),
    ("quoted span", {"value": "browser-use/jev-ultrafast", "role_in_goal": "search query",
                     "goal_span": "search 'browser-use/jev-ultrafast'"}, {"label": "combobox: Search or jump to",
                     "role": "combobox"}, "e.g. search 'browser-use/jev-ultrafast'", True),
    ("ZIP in text field", {"value": "10001", "role_in_goal": "zip code", "goal_span": "ZIP code 10001"},
     {"label": "textbox: ZIP code", "role": "textbox"}, "change the ZIP code 10001", True),
])
def test_value_contract(name, prop, field, goal, ok):
    prop = {"field": field["label"], **prop}
    assert V.check(prop, field, [goal], TODAY)[0] is ok, (name, V.check(prop, field, [goal], TODAY))


def test_helper_checklist_is_not_a_source():
    prop = {"field": SLIDER["label"], "value": "500", "role_in_goal": "max price", "goal_span": "max 500"}
    assert not V.check(prop, SLIDER, [G], TODAY)[0]
    assert V.check(prop, SLIDER, [G, "caller checklist: max 500"], TODAY)[0]  # caller-given sources only


def test_sensitive_controls_are_flagged():
    assert Control("j1", "textbox", "input", "password", "Password").sensitive
    assert Control("j2", "textbox", "input", "text", "E-posta adresi").sensitive
    assert not Control("j3", "searchbox", "input", "search", "Search").sensitive


# ---------------------------------------------------------------- snapshot + executor on fixtures (both backends)

async def test_proxy_controls_are_found_and_real_overlays_hide(browser, base_url):
    await browser.open(f"{base_url}/s27_proxy_controls.html")
    s = await take(browser)
    labels = [c.label for c in s.controls]
    assert any(c.type == "select-option" and c.text == "Price: Low to High" for c in s.controls), labels
    assert "button: Dismiss" in labels and "button: Change Address" in labels, labels
    assert not any("Hidden behind" in lab for lab in labels) and any("Veil link" in lab for lab in labels)
    x = Executor(browser)
    await x.click(next(c for c in s.controls if c.text == "Change Address"))
    assert (await browser.info())["title"] == "change address"
    await x.click(next(c for c in s.controls if c.text == "Price: Low to High"))
    assert (await browser.info())["title"] == "sorted price-asc"


async def test_css_modal_scopes_page_and_pointer_span_is_clickable(browser, base_url):
    await browser.open(f"{base_url}/s28_css_modal.html")
    s = await take(browser)
    assert s.popup and [c.text for c in s.controls] == ["KAPAT"], [c.label for c in s.controls]
    assert "Ana sayfa" not in s.text and "KAPAT" in s.text
    await Executor(browser).click(s.controls[0])
    s2 = await take(browser)
    assert not s2.popup and {"Tahminler", "Kurumsal"} <= {c.text for c in s2.controls}


async def test_widgets_viewport_and_shadow(browser, base_url):
    await browser.open(f"{base_url}/s26_widgets.html")
    s = await take(browser)
    by = {c.text: c for c in s.controls}
    assert by["Max price"].role == "slider" and "$1050+" in by["Max price"].state
    assert by["Minimum rating"].role == "slider" and by["Quantity"].role == "spinbutton"
    assert by["Gift note"].role == "textbox"
    await browser.open(f"{base_url}/s13_offscreen.html")
    s = await take(browser)
    by = {c.text: c for c in s.controls}
    assert by["Üst"].in_view and not by["En alttaki düğme"].in_view
    await browser.open(f"{base_url}/s18_shadow.html")
    s = await take(browser)
    assert s.controls, "shadow DOM controls must be found"


# ---------------------------------------------------------------- task loop with a fake model and a fake helper

def ch(choice, p=0.9):
    return NS(choice=choice, confidence=p, probabilities={choice: p})


class FakeClient:
    """policy(state, questions) -> {"op", "target" (label substring), "p", "done", "blocked", "tie"}."""

    def __init__(self, policy, tie=0.9, commits=0.05, elig=None):
        self.policy, self.tie, self.commits, self.calls = policy, tie, commits, []
        self.elig = elig or (lambda text: 0.9)   # eligibility of an option (PICK_CHEAPEST), from its text

    async def system_one(self, state, questions):
        self.calls.append((state, questions))
        usage = NS(input_tokens=100)
        if "fits" in questions:
            return NS(choices={}, nouls={"fits": NS(noul=0.95), "commits": NS(noul=self.commits)}, usage=usage)
        if "commits" in questions:
            return NS(choices={}, nouls={"commits": NS(noul=self.commits)}, usage=usage)
        if "tied" in questions:
            return NS(choices={}, nouls={"tied": NS(noul=self.tie)}, usage=usage)
        if "operation" not in questions and questions and all(k.startswith("e") for k in questions):
            opts = state["options"]
            return NS(choices={}, nouls={k: NS(noul=self.elig(opts[int(k[1:])])) for k in questions}, usage=usage)
        d = self.policy(state, questions)
        choices = {"operation": ch(d["op"], d.get("p", 0.9)), "blocked": ch(d.get("blocked", "nothing"))}
        for name, q in questions.items():
            if name.endswith("_target") and name != "scroll_target":
                want = d.get("target", "")
                cid = next((k for k, v in q.criteria.items() if want and want in v), next(iter(q.criteria)))
                choices[name] = ch(cid, d.get("p", 0.9))
            if name == "scroll_target":
                choices[name] = ch("page")
        nouls = {"done": NS(noul=d.get("done", 0.05))}
        nouls.update({k: NS(noul=d.get("req", 0.95)) for k in questions if k.startswith("req")})
        return NS(choices=choices, nouls=nouls, usage=usage)


class FakeHelper:
    provider = "fake"

    def __init__(self, values=None, answer=None, reqs=None):
        self.vals, self.ans, self.calls, self.reqs = values or {}, answer or {}, [], reqs or []

    async def requirements(self, goal, today):
        self.calls.append({"kind": "requirements", "ms": 1})
        return self.reqs

    async def value(self, goal, today, field, context, tried=None):
        self.calls.append({"kind": "value", "ms": 1})
        return next((v for k, v in self.vals.items() if k in field["label"]), {"value": None})

    async def values(self, goal, today, fields, context):  # one call for all fields of the page
        self.calls.append({"kind": "values", "ms": 1})
        return [next((v for k, v in self.vals.items() if k in f["label"]), {"field": f["label"], "value": None})
                for f in fields]

    async def answer(self, goal, today, page_text, url):
        self.calls.append({"kind": "answer", "ms": 1})
        return self.ans


def shop_policy(state, questions):
    if "s24_shop" in state["url"]:
        return {"op": "TYPE", "target": "Search shop"}
    if "s24_results" in state["url"]:
        return {"op": "CLICK", "target": "Console (Renewed)"}
    return {"op": "DONE", "done": 0.95}


async def test_task_types_checked_value_and_finishes_on_checks(browser, base_url):
    helper = FakeHelper({"Search shop": {"field": "searchbox: Search shop", "value": "PlayStation 5 Pro",
                                         "role_in_goal": "search query", "goal_span": "PlayStation 5 Pro"}})
    spec = TaskSpec(goal="Search the shop for PlayStation 5 Pro and open the renewed PlayStation 5 Pro console",
                    end_condition={"checks": [{"url_contains": "#pro2"}]}, start_url=f"{base_url}/s24_shop.html")
    res = await AgentV4(browser, FakeClient(shop_policy), helper, TODAY).run(spec)
    assert res["status"] == "done", res
    assert "#pro2" in res["evidence"]["url"] and res["metrics"]["steps"] == 2


async def test_550_into_search_is_never_typed(browser, base_url):
    helper = FakeHelper({"Search shop": {"field": "searchbox: Search shop", "value": "550",
                                         "role_in_goal": "max price", "goal_span": "550 dollars"}})
    spec = TaskSpec(goal="Find a PS5 under 550 dollars", end_condition={}, start_url=f"{base_url}/s24_shop.html")
    res = await AgentV4(browser, FakeClient(shop_policy), helper, TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "value", res
    assert "s24_shop" in (await browser.info())["url"]  # nothing typed or submitted


async def test_captcha_block_escalates_even_with_a_confident_action(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={}, start_url=f"{base_url}/s24_results.html")
    pol = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.99, "blocked": "captcha"}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(), TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "blocked"
    assert "s24_results" in (await browser.info())["url"]


async def test_help_single_use_and_takeover_is_re_read(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={"checks": [{"url_contains": "#pro2"}]},
                    start_url=f"{base_url}/s24_results.html")
    low = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.3}  # noqa: E731
    ag = AgentV4(browser, FakeClient(low), FakeHelper(), TODAY)
    res = await ag.run(spec, task_id="t-help")
    h = res["help"]
    assert res["status"] == "needs_help" and h["options"][0]["oid"].startswith("CLICK:")
    # the caller clicks itself, then says so: Jev re-reads the page and its checks decide
    await browser.open(f"{base_url}/ok.html#pro2")
    done = await AgentV4(browser, FakeClient(lambda s, q: {"op": "DONE", "done": 0.9}), FakeHelper(), TODAY).help(
        "t-help", h["help_id"], h["page_version"], {"takeover_done": True})
    assert done["status"] == "done", done
    again = await ag.help("t-help", h["help_id"], h["page_version"], {"takeover_done": True})
    assert again["status"] == "rejected"


async def test_risky_click_needs_approval_then_runs_once_approved(browser, base_url):
    spec = TaskSpec(goal="Save the campaign", end_condition={"checks": [{"new_page_title_contains": "SAVED"}]},
                    start_url=f"{base_url}/s30_save.html")
    pol = lambda st, q: {"op": "CLICK", "target": "Kaydet", "p": 0.99}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(), TODAY).run(spec, task_id="t-risk")
    assert res["status"] == "needs_help" and res["help"]["kind"] == "approve"
    assert (await browser.info())["title"] == "S30"  # not clicked
    h = res["help"]
    pol2 = lambda st, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    done = await AgentV4(browser, FakeClient(pol2), FakeHelper(), TODAY).help(
        "t-risk", h["help_id"], h["page_version"], {"approve": h["options"][0]["oid"]})
    assert done["status"] == "done", done


FORECAST_GOAL = "haftaya salı günü istanbul tuzlada hava kaç derece olacak"


async def test_read_task_answer_must_be_tied_to_entity_and_date(browser, base_url):
    good = {"answer": "15–23 °C", "quote": "29 Eylül Salı Az Bulutlu 15 °C 23 °C", "entity": "Tuzla",
            "date": "29 Eylül Salı", "unit": "°C"}
    spec = TaskSpec(goal=FORECAST_GOAL, end_condition={}, start_url=f"{base_url}/s29_forecast.html")
    pol = lambda s, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=good), TODAY).run(spec)
    assert res["status"] == "done" and res["answer"]["answer"] == "15–23 °C", res
    assert res["evidence"]["asked_date"] == "2026-09-29"


@pytest.mark.parametrize("bad, why", [
    ({"answer": "9–20 °C", "quote": "Ankara 29 Eylül Salı: En Düşük 9 °C En Yüksek 20 °C", "entity": "Ankara",
      "unit": "°C"}, "entity"),
    ({"answer": "17–22 °C", "quote": "28 Eylül Pazartesi Sağanak Yağışlı 17 °C 22 °C", "entity": "Tuzla",
      "unit": "°C"}, "date"),
    ({"answer": "15–23 °C", "quote": "Tuzla Salı 15-23 derece", "entity": "Tuzla"}, "quote"),
    ({"answer": "15", "quote": "29 Eylül Salı Az Bulutlu 15", "entity": "Tuzla", "unit": "°C"}, "unit"),
])
async def test_read_task_rejects_untied_answers(browser, base_url, bad, why):
    spec = TaskSpec(goal=FORECAST_GOAL, end_condition={}, start_url=f"{base_url}/s29_forecast.html")
    pol = lambda s, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=bad), TODAY).run(spec)
    assert res["status"] == "needs_help", res
    assert why in res["help"]["question"], res["help"]["question"]


async def test_read_task_rejects_other_places_numbers_when_asked_place_is_only_a_suggestion(browser, base_url):
    """Live failure (MGM, 2026-09-24): the home page shows Ankara's forecast while 'Tuzla' is only a search
    suggestion; the helper claimed entity Tuzla for Ankara's Tuesday. Must not be done."""
    bad = {"answer": "10–20 °C", "quote": "Salı Parçalı Bulutlu 10 °C 20 °C", "entity": "Tuzla, İstanbul",
           "date": "Salı"}
    spec = TaskSpec(goal=FORECAST_GOAL, end_condition={}, start_url=f"{base_url}/s31_other_city.html")
    pol = lambda s, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=bad), TODAY).run(spec)
    assert res["status"] == "needs_help", res
    assert "entity" in res["help"]["question"], res["help"]["question"]


async def test_checks_passing_finish_even_with_a_low_done_score(browser, base_url):
    """Live (Wikipedia, 2026-09-24): search + Enter landed on the article; checks passed but done_p was 0.77."""
    spec = TaskSpec(goal="Open the renewed console", end_condition={"checks": [{"url_contains": "#pro2"}]},
                    start_url=f"{base_url}/ok.html#pro2")
    pol = lambda s, q: {"op": "SCROLL_DOWN", "done": 0.6}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done" and res["metrics"]["steps"] == 0, res


async def test_calendar_days_carry_month_and_date(browser, base_url):
    """Live (Google Flights, 2026-09-24): day buttons were only '20'; the month was not visible to Jev."""
    await browser.open(f"{base_url}/s32_calendar.html")
    s = await take(browser)
    twenties = [c for c in s.controls if c.text == "20"]
    assert len(twenties) == 2 and all(c.role == "button" for c in twenties), [c.line() for c in twenties]
    oct20 = next(c for c in twenties if "October" in c.context)
    assert "2026-10-20" in oct20.context
    await Executor(browser).click(oct20)
    assert (await browser.info())["title"] == "picked 2026-10-20"


async def test_count_answer_must_name_what_it_counts(browser, base_url):
    """Live (GitHub, 2026-09-25): '1.3k' next to the repo name was the fork count, taken as stars."""
    goal = "How many stars does the GitHub repository browser-use/jev-ultrafast have?"
    spec = TaskSpec(goal=goal, end_condition={}, start_url=f"{base_url}/s33_repo_list.html")
    pol = lambda s, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    bad = {"answer": "1.3k", "quote": "jev-ultrafast Public Fastest and cheapest web agent Python MIT License 1.3k",
           "entity": "jev-ultrafast", "unit": "stars"}
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=bad), TODAY).run(spec)
    assert res["status"] == "needs_help" and "unit" in res["help"]["question"], res
    good = {"answer": "19.8k", "quote": "19.8k stars", "entity": "jev-ultrafast", "unit": "stars"}
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=good), TODAY).run(spec)
    assert res["status"] == "done" and res["answer"]["answer"] == "19.8k", res


# ---------------------------------------------------------------- review round 1 (Codex): regressions

async def test_answer_numbers_must_be_in_the_quote(browser, base_url):
    bad = {"answer": "999 °C", "quote": "29 Eylül Salı Az Bulutlu 15 °C 23 °C", "entity": "Tuzla", "unit": "°C"}
    spec = TaskSpec(goal=FORECAST_GOAL, end_condition={}, start_url=f"{base_url}/s29_forecast.html")
    pol = lambda s, q: {"op": "DONE", "done": 0.95}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(answer=bad), TODAY).run(spec)
    assert res["status"] == "needs_help" and "not in the quote" in res["help"]["question"], res


async def test_approve_cannot_apply_a_value_that_failed_the_contract(browser, base_url):
    helper = FakeHelper({"Search shop": {"field": "searchbox: Search shop", "value": "5500",
                                         "role_in_goal": "max price", "goal_span": "550 dollars"}})
    spec = TaskSpec(goal="Find a PS5 under 550 dollars", end_condition={}, start_url=f"{base_url}/s24_shop.html")
    res = await AgentV4(browser, FakeClient(shop_policy), helper, TODAY).run(spec, task_id="t-appr")
    h = res["help"]
    assert h["kind"] == "value"
    again = await AgentV4(browser, FakeClient(shop_policy), helper, TODAY).help(
        "t-appr", h["help_id"], h["page_version"], {"approve": h["options"][0]["oid"]})
    assert again["status"] == "rejected" and "approval request" in again["reason"]
    assert "s24_shop" in (await browser.info())["url"]


async def test_stale_help_after_navigation_is_rejected(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={}, start_url=f"{base_url}/s24_results.html")
    low = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.3}  # noqa: E731
    res = await AgentV4(browser, FakeClient(low), FakeHelper(), TODAY).run(spec, task_id="t-stale")
    h = res["help"]
    await browser.open(f"{base_url}/s24_results.html?other=1")  # same controls, different page
    again = await AgentV4(browser, FakeClient(low), FakeHelper(), TODAY).help(
        "t-stale", h["help_id"], h["page_version"], {"pick": h["options"][0]["oid"]})
    # the old option is void (not applied); Jev decided again on the current page (still unsure -> a fresh help)
    assert again["status"] == "needs_help" and again["help"]["help_id"] != h["help_id"] and again["help"]["options"]
    assert any("void" in str(t.get("help_reply", {}).get("outcome")) for t in again["trace"]), again["trace"]
    assert "#pro2" not in (await browser.info())["url"]


async def test_failed_click_is_not_retried_and_asks(browser, base_url, monkeypatch):
    calls = []

    async def boom(self, c):
        calls.append(c.cid)
        raise RuntimeError("connection lost after click")
    monkeypatch.setattr(Executor, "click", boom)
    spec = TaskSpec(goal="Open the renewed console", end_condition={}, start_url=f"{base_url}/s24_results.html")
    pol = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.95}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(), TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "clarify", res
    assert len(calls) == 1


async def test_real_overlay_hides_select_and_slider(browser, base_url):
    await browser.open(f"{base_url}/s34_overlay_widgets.html")
    s = await take(browser)
    texts = {c.text for c in s.controls}
    assert "Free button" in texts and "Sort" not in texts and "Price" not in texts, [c.label for c in s.controls]


async def test_missing_helper_config_asks_instead_of_a_silent_fallback(browser, base_url, monkeypatch):
    from jev.v4.helper import Helper
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("JEV_HELPER", raising=False)
    spec = TaskSpec(goal="Search the shop for PlayStation 5 Pro", end_condition={}, start_url=f"{base_url}/s24_shop.html")
    res = await AgentV4(browser, FakeClient(shop_policy), Helper(), TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "config", res


async def test_time_budget_counts_earlier_segments(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={}, start_url=f"{base_url}/s24_results.html",
                    limits={"steps": 30, "seconds": 30})
    low = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.3}  # noqa: E731
    res = await AgentV4(browser, FakeClient(low), FakeHelper(), TODAY).run(spec, task_id="t-budget")
    A.TaskStore("t-budget").add("segment", wall_s=100)  # time already used before this help
    h = res["help"]
    again = await AgentV4(browser, FakeClient(low), FakeHelper(), TODAY).help(
        "t-budget", h["help_id"], h["page_version"], {"clarify": "the renewed one"})
    assert again["status"] == "budget_exhausted", again


# ---------------------------------------------------------------- review round 2 (Codex): regressions

SAVE = "Save the campaign"
save_pol = lambda st, q: {"op": "CLICK", "target": "Kaydet", "p": 0.99}  # noqa: E731


async def test_hash_route_change_invalidates_an_approval(browser, base_url):
    spec = TaskSpec(goal=SAVE, end_condition={}, start_url=f"{base_url}/s30_save.html#/campaign/a")
    res = await AgentV4(browser, FakeClient(save_pol), FakeHelper(), TODAY).run(spec, task_id="t-hash")
    h = res["help"]
    assert h["kind"] == "approve"
    await browser.open(f"{base_url}/s30_save.html#/campaign/b")  # same controls, another campaign
    again = await AgentV4(browser, FakeClient(save_pol), FakeHelper(), TODAY).help(
        "t-hash", h["help_id"], h["page_version"], {"approve": h["options"][0]["oid"]})
    # the old approval is void; Jev re-decides and the risky click needs a new approval on this page
    assert again["status"] == "needs_help" and again["help"]["kind"] == "approve", again
    assert again["help"]["help_id"] != h["help_id"] and "campaign/b" in again["help"]["page"]["url"]
    assert (await browser.info())["title"] == "S30"


async def test_approve_is_bound_to_the_shown_value(browser, base_url):
    helper = FakeHelper({"Kampanya adı": {"field": "textbox: Kampanya adı", "value": "Kış",
                                           "role_in_goal": "campaign name", "goal_span": "Kış"}})
    spec = TaskSpec(goal="Kampanya adını Kış yap", end_condition={}, start_url=f"{base_url}/s30_save.html")
    pol = lambda st, q: {"op": "TYPE", "target": "Kampanya adı", "p": 0.99}  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol, commits=0.9), helper, TODAY).run(spec, task_id="t-val")
    h = res["help"]
    assert h["kind"] == "approve" and h["options"][0]["value"] == "Kış", h
    again = await AgentV4(browser, FakeClient(pol, commits=0.9), helper, TODAY).help(
        "t-val", h["help_id"], h["page_version"], {"approve": h["options"][0]["oid"], "text": "999"})
    assert again["status"] == "rejected" and "shown value" in again["reason"]
    s = await take(browser)
    assert s.text.count("999") == 0


async def test_budget_is_checked_before_a_help_action(browser, base_url):
    spec = TaskSpec(goal=SAVE, end_condition={}, start_url=f"{base_url}/s30_save.html",
                    limits={"steps": 30, "seconds": 30})
    res = await AgentV4(browser, FakeClient(save_pol), FakeHelper(), TODAY).run(spec, task_id="t-bud2")
    h = res["help"]
    A.TaskStore("t-bud2").add("segment", wall_s=100)
    again = await AgentV4(browser, FakeClient(save_pol), FakeHelper(), TODAY).help(
        "t-bud2", h["help_id"], h["page_version"], {"approve": h["options"][0]["oid"]})
    assert again["status"] == "budget_exhausted", again
    assert (await browser.info())["title"] == "S30"  # not clicked


# ---------------------------------------------------------------- latency round (Codex): one helper call per page

async def test_helper_is_asked_once_for_all_fields_of_a_page(browser, base_url):
    helper = FakeHelper({"From": {"field": "textbox: From", "value": "Istanbul", "role_in_goal": "origin",
                                  "goal_span": "from Istanbul"},
                         "To": {"field": "textbox: To", "value": "London", "role_in_goal": "destination",
                                "goal_span": "to London"}})

    def pol(state, q):
        n = len(state["last_actions"])
        return [{"op": "TYPE", "target": "From"}, {"op": "TYPE", "target": "To"},
                {"op": "CLICK", "target": "Search flights"}][min(n, 2)]
    spec = TaskSpec(goal="Search flights from Istanbul to London", end_condition={"checks": [{"url_contains": "ok.html"}]},
                    start_url=f"{base_url}/s35_form.html")
    res = await AgentV4(browser, FakeClient(pol), helper, TODAY).run(spec)
    assert res["status"] == "done", res
    assert [c["kind"] for c in helper.calls if c["kind"] != "requirements"] == ["values"], helper.calls



# ---------------------------------------------------------------- latency round 2 (Codex): typed readiness

async def test_readiness_waits_for_delayed_suggestions(browser, base_url):
    """ext returned the JS value `false` as the truthy string "false", so the wait for suggestions ended at once."""
    from jev.v4.snapshot import fingerprint
    await browser.open(f"{base_url}/s36_delayed_suggest.html")
    s = await take(browser)
    assert s.fp == await fingerprint(browser)  # the snapshot's fingerprint is the same formula
    x = Executor(browser)
    field = next(c for c in s.controls if c.text == "Where to?")
    assert await x._eval("() => false") is False and await x._eval("() => 1 + 1") == 2
    await x.fill(field, "Lon", submit=False)
    ready, _ = await x.ready_after("TYPE", s.fp, s.url, combo=True)
    s2 = await take(browser)
    assert ready and any(c.text == "London, United Kingdom" for c in s2.controls), [c.label for c in s2.controls]


# ---------------------------------------------------------------- review run 3 (Codex): identity, cache, observation

def _low_day(state, q):
    return {"op": "CLICK", "target": "20", "p": 0.4}


async def test_pick_survives_a_late_price_on_the_same_date(browser, base_url):
    spec = TaskSpec(goal="Pick 20 October", end_condition={}, start_url=f"{base_url}/s37_calendar_late.html")
    res = await AgentV4(browser, FakeClient(_low_day), FakeHelper(), TODAY).run(spec, task_id="t-late")
    h = res["help"]
    await Executor(browser)._eval("() => window.addPrice()")          # "20" -> "20 ₺7,560", same node, same date
    pol2 = lambda st, q: {"op": "DONE", "done": 0.9}  # noqa: E731
    await AgentV4(browser, FakeClient(pol2), FakeHelper(), TODAY).help(
        "t-late", h["help_id"], h["page_version"], {"pick": h["options"][0]["oid"]})
    assert (await browser.info())["title"] == "picked 2026-10-20"


async def test_pick_is_void_when_the_node_now_means_another_date(browser, base_url):
    spec = TaskSpec(goal="Pick 20 October", end_condition={}, start_url=f"{base_url}/s37_calendar_late.html")
    res = await AgentV4(browser, FakeClient(_low_day), FakeHelper(), TODAY).run(spec, task_id="t-recyc")
    h = res["help"]
    await Executor(browser)._eval("() => window.recycle()")           # same node, now 20 November
    again = await AgentV4(browser, FakeClient(_low_day), FakeHelper(), TODAY).help(
        "t-recyc", h["help_id"], h["page_version"], {"pick": h["options"][0]["oid"]})
    assert (await browser.info())["title"] == "S37"                  # not clicked
    assert any("void" in str(t.get("help_reply", {}).get("outcome")) for t in again["trace"])


async def test_approval_still_needs_the_exact_label(browser, base_url):
    from jev.v4.agent import _same_target
    await browser.open(f"{base_url}/s37_calendar_late.html")
    s = await take(browser)
    day = next(c for c in s.controls if c.text == "20")
    opt = {"label": day.label, "context": day.context, "state0": "", "role": day.role, "doc": s.doc,
           "sem": "2026-10-20"}
    await Executor(browser)._eval("() => window.addPrice()")
    s2 = await take(browser)
    day2 = s2.by_cid(day.cid)
    assert _same_target(opt, day2, s2, strict=False) and not _same_target(opt, day2, s2, strict=True)


FORM_GOAL = "Search flights from Istanbul to London"
FORM_VALS = {"From": {"field": "textbox: From", "value": "Istanbul", "role_in_goal": "origin",
                      "goal_span": "from Istanbul"},
             "To": {"field": "textbox: To", "value": "London", "role_in_goal": "destination", "goal_span": "to London"}}


async def test_query_rewrite_reuses_the_proposal_without_another_helper_call(browser, base_url):
    helper = FakeHelper(FORM_VALS)

    def pol(state, q):
        n = len(state["last_actions"])
        return [{"op": "TYPE", "target": "From"}, {"op": "TYPE", "target": "To"},
                {"op": "CLICK", "target": "Search flights"}][min(n, 2)]
    spec = TaskSpec(goal=FORM_GOAL, end_condition={"checks": [{"url_contains": "ok.html"}]},
                    start_url=f"{base_url}/s38_rewrite_form.html")
    res = await AgentV4(browser, FakeClient(pol), helper, TODAY).run(spec)
    assert res["status"] == "done", res
    assert [c["kind"] for c in helper.calls if c["kind"] != "requirements"] == ["values"], helper.calls  # rewrite: cached


async def test_proposal_cache_is_invalidated_by_goal_document_and_field_meaning(browser, base_url):
    helper = FakeHelper(FORM_VALS)
    ag = AgentV4(browser, FakeClient(lambda s, q: {"op": "WAIT"}), helper, TODAY)
    store = A.TaskStore("t-cache")
    spec = TaskSpec(goal=FORM_GOAL, end_condition={})
    await browser.open(f"{base_url}/s38_rewrite_form.html")
    s = await ag.snap()
    frm = next(c for c in s.controls if c.text == "From")

    async def ask(spec_, s_, c_):
        return await ag._value(spec_, s_, c_, {"label": c_.label}, [], [], store)
    await ask(spec, s, frm)
    await ask(spec, s, frm)
    assert len(helper.calls) == 1                                         # same goal, document, field → cached
    await ask(TaskSpec(goal=FORM_GOAL + ". Clarification: from Ankara", end_condition={}), s, frm)
    assert len(helper.calls) == 2                                         # goal revision → new proposal
    await browser.open(f"{base_url}/s38_rewrite_form.html")               # reload → new document
    s2 = await ag.snap()
    frm2 = next(c for c in s2.controls if c.text == "From")
    assert s2.doc != s.doc
    await ask(spec, s2, frm2)
    assert len(helper.calls) == 3
    changed = Control(**{**frm2.__dict__, "context": "Return trip"})      # another field meaning
    await ask(spec, s2, changed)
    assert len(helper.calls) == 4


async def test_help_saves_what_jev_saw(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={}, start_url=f"{base_url}/s24_results.html")
    low = lambda s, q: {"op": "CLICK", "target": "Renewed", "p": 0.3}  # noqa: E731
    res = await AgentV4(browser, FakeClient(low), FakeHelper(), TODAY).run(spec, task_id="t-obs")
    obs = [r for r in A.TaskStore("t-obs").records() if r["kind"] == "observation"]
    assert obs and obs[-1]["help_id"] == res["help"]["help_id"]
    assert "controls" in obs[-1]["state"] and "CLICK" in obs[-1]["targets"]


# ---------------------------------------------------------------- review run 4 (Codex): loading readiness, privacy

async def test_results_loading_is_waited_out_by_code(browser, base_url):
    spec = TaskSpec(goal="Search and show the results", end_condition={"checks": [{"text_contains": "Result C"}]},
                    start_url=f"{base_url}/s39_loading.html")
    client = FakeClient(lambda st, q: {"op": "CLICK", "target": "Search"})
    res = await AgentV4(browser, client, FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done", res
    steps = [c for c in client.calls if "operation" in c[1]]
    assert len(steps) == 2  # click, then one observation after the results arrived: no decisions spent on polls


async def test_hidden_and_unrelated_indicators_are_not_loading(browser, base_url):
    await browser.open(f"{base_url}/s39_loading.html")
    assert await Executor(browser).loading() == ""   # hidden, screen-reader-only, header, determinate: all ignored


async def test_persistent_loading_ends_in_slow_page(browser, base_url, monkeypatch):
    import jev.v4.executor as X
    monkeypatch.setattr(X, "LOADING_CAP", 1.0)
    spec = TaskSpec(goal="Search and show the results", end_condition={"checks": [{"text_contains": "Result C"}]},
                    start_url=f"{base_url}/s39_loading.html?stuck=1")
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "CLICK", "target": "Search"}), FakeHelper(),
                        TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "slow_page", res


PII = ("jane.public@example.com", "Jane Q Public", "+90 532 123 45 67")
KEEP = ("TK 1985", "2026-10-20", "09:10", "₺13,594")


async def test_personal_data_never_leaves_and_task_values_stay(browser, base_url):
    import json as _json
    seen = []

    class Spy(FakeHelper):
        async def values(self, goal, today, fields, context):
            seen.append(_json.dumps([fields, context], ensure_ascii=False))
            return await super().values(goal, today, fields, context)

        async def answer(self, goal, today, page_text, url):
            seen.append(page_text)
            return {"answer": None}
    helper = Spy({"Where to": {"field": "textbox: Where to?", "value": "London", "role_in_goal": "destination",
                                "goal_span": "to London"}})

    def pol(state, q):
        return {"op": "TYPE", "target": "Where to"} if not state["last_actions"] else {"op": "CLICK", "target": "Search"}
    client = FakeClient(pol)
    spec = TaskSpec(goal="Search flights to London", end_condition={"checks": [{"url_contains": "ok.html"}]},
                    start_url=f"{base_url}/s40_signed_in.html")
    res = await AgentV4(browser, client, helper, TODAY).run(spec, task_id="t-pii")
    assert res["status"] == "done", res
    sent = _json.dumps([c[0] for c in client.calls], ensure_ascii=False) + " ".join(seen)
    stored = A.TaskStore("t-pii").path.read_text()
    first_state = _json.dumps(client.calls[0][0], ensure_ascii=False)
    for bad in PII:
        assert bad not in sent and bad not in stored, bad
    for good in KEEP:
        assert good in first_state, good
    assert "account menu" in first_state and "[email]" in first_state and "[phone]" in first_state


# ---------------------------------------------------------------- review run 4 (Codex): requirements, verified comparison

CHEAP_GOAL = "Find round-trip nonstop flights Istanbul to London on 20 October 2026 and open the cheapest option"
CHEAP_REQS = [{"text": "nonstop only", "kind": "page"}, {"text": "cheapest option opened", "kind": "compare_cheapest"}]
not_eligible = lambda text: 0.1 if ("1 stop" in text or "Oct 21" in text) else 0.9  # noqa: E731


async def test_pick_cheapest_opens_the_cheapest_eligible_option(browser, base_url):
    pol = lambda st, q: {"op": "PICK_CHEAPEST"} if "results" in st["title"] else {"op": "WAIT"}  # noqa: E731
    spec = TaskSpec(goal=CHEAP_GOAL, end_condition={"checks": [{"url_contains": "s45_detail"}]},
                    start_url=f"{base_url}/s41_results.html")
    client = FakeClient(pol, elig=not_eligible)
    res = await AgentV4(browser, client, FakeHelper(reqs=CHEAP_REQS), TODAY).run(spec)
    assert res["status"] == "done", res
    assert "Option%20A" in res["evidence"]["url"]        # 15,122: B (12,000, 1 stop) and E (14,500, Oct 21) excluded
    comp = res["evidence"]["comparisons"][0]
    assert comp["eligible"] == 3 and comp["chosen"]["price"] == 15122.0 and comp["chosen"]["currency"] == "TRY"
    assert "PICK_CHEAPEST" in client.calls[0][1]["operation"].criteria


async def test_pick_cheapest_needs_three_eligible_options(browser, base_url):
    calls = {"n": 0}

    def pol(st, q):
        calls["n"] += 1
        return {"op": "PICK_CHEAPEST"} if calls["n"] == 1 else {"op": "ASK"}
    spec = TaskSpec(goal=CHEAP_GOAL, end_condition={"checks": [{"url_contains": "ok.html"}]},
                    start_url=f"{base_url}/s41_results.html")
    only_a = lambda text: 0.9 if "15122" in text else 0.1  # noqa: E731
    res = await AgentV4(browser, FakeClient(pol, elig=only_a), FakeHelper(reqs=CHEAP_REQS), TODAY).run(spec,
                                                                                                     task_id="t-few")
    assert res["status"] == "needs_help" and "s41_results" in (await browser.info())["url"]
    comp = [r for r in A.TaskStore("t-few").records() if r["kind"] == "comparison"][0]
    assert comp["chosen"] is None and "3 needed" in comp["reason"]


async def test_pick_cheapest_is_offered_only_with_three_priced_options(browser, base_url):
    client = FakeClient(lambda st, q: {"op": "ASK"})
    spec = TaskSpec(goal="Open the cheapest PlayStation 5 Pro console", end_condition={},
                    start_url=f"{base_url}/s24_results.html")          # prices are not in the links' own names
    await AgentV4(browser, client, FakeHelper(), TODAY).run(spec)
    assert "PICK_CHEAPEST" not in client.calls[0][1]["operation"].criteria


async def test_missing_requirement_blocks_done_even_when_checks_pass(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console, nonstop only", end_condition={"checks": [{"url_contains": "#pro2"}]},
                    start_url=f"{base_url}/ok.html#pro2")
    reqs = [{"text": "nonstop only", "kind": "page"}]
    client = FakeClient(lambda st, q: {"op": "DONE", "done": 0.95, "req": 0.1})
    res = await AgentV4(browser, client, FakeHelper(reqs=reqs), TODAY).run(spec)
    assert res["status"] == "needs_help", res
    assert "requirements not met" in res["help"]["question"] or any(
        "requirements not met" in str(t.get("action", "")) for t in res["trace"])
    last_state = client.calls[-1][0]
    assert last_state["requirements"] == [{"text": "nonstop only", "status": "missing"}]
    ok = await AgentV4(browser, FakeClient(lambda st, q: {"op": "DONE", "done": 0.95, "req": 0.95}),
                       FakeHelper(reqs=reqs), TODAY).run(spec)
    assert ok["status"] == "done", ok


# ---------------------------------------------------------------- review run 5 (Codex): privacy of state/URL, totals,
# verified opening, goal-bound comparison, kept field values

async def test_state_and_url_are_redacted_before_leaving(browser, base_url):
    import json as _json
    client = FakeClient(lambda st, q: {"op": "ASK"})
    spec = TaskSpec(goal="Look at the receipt option", end_condition={},
                    start_url=f"{base_url}/s42_reject_field.html?user=jane.public%40example.com")
    await AgentV4(browser, client, FakeHelper(), TODAY).run(spec, task_id="t-pii2")
    sent = _json.dumps([c[0] for c in client.calls], ensure_ascii=False)
    stored = A.TaskStore("t-pii2").path.read_text()
    for bad in ("jane.public", "%40example"):
        assert bad not in sent and bad not in stored, bad
    assert "[email]" in sent


async def test_a_field_that_does_not_keep_the_value_is_reported(browser, base_url):
    helper = FakeHelper({"Return": {"field": "textbox: Return", "value": "2026-10-27", "role_in_goal": "return date",
                                    "goal_span": "27 October 2026"}})
    client = FakeClient(lambda st, q: {"op": "TYPE", "target": "Return"} if not st["last_actions"] else {"op": "ASK"})
    spec = TaskSpec(goal="Return on 27 October 2026", end_condition={}, start_url=f"{base_url}/s42_reject_field.html")
    res = await AgentV4(browser, client, helper, TODAY).run(spec)
    typed = [t for t in res["trace"] if str(t.get("action", "")).startswith("TYPE")]
    assert typed and typed[0]["ok"] is False and "did not keep" in typed[0]["error"], res["trace"]
    assert "did not keep" in _last_actions_text(client)


def _last_actions_text(client):
    return " ".join(str(a) for st, _ in client.calls if "last_actions" in st for a in st["last_actions"])


TOTAL_GOAL = "For 2 adults, compare the options and open the one with the lowest total price"


async def test_comparison_uses_totals_not_the_first_number(browser, base_url):
    pol = lambda st, q: {"op": "PICK_CHEAPEST"} if "results" in st["title"] else {"op": "WAIT"}  # noqa: E731
    spec = TaskSpec(goal=TOTAL_GOAL, end_condition={"checks": [{"url_contains": "s45_detail"}]},
                    start_url=f"{base_url}/s43_totals.html")
    res = await AgentV4(browser, FakeClient(pol), FakeHelper(reqs=[{"text": "cheapest", "kind": "compare_cheapest"}]),
                        TODAY).run(spec)
    assert res["status"] == "done", res
    assert "Option%20Y" in res["evidence"]["url"]   # total 300 < 320 < 350 < 400; W (per person only) excluded
    comp = res["evidence"]["comparisons"][0]
    w = next(r for r in comp["candidates"] if r["label"].startswith("Option W"))
    assert w["price"] is None and comp["chosen"]["price"] == 300.0 and comp["open_evidence"]["url_changed"]


async def test_opening_is_verified_on_the_next_observation(browser, base_url):
    calls = {"n": 0}

    def pol(st, q):
        calls["n"] += 1
        return {"op": "PICK_CHEAPEST"} if calls["n"] == 1 else {"op": "ASK"}
    spec = TaskSpec(goal=TOTAL_GOAL, end_condition={}, start_url=f"{base_url}/s44_dead_links.html")
    await AgentV4(browser, FakeClient(pol), FakeHelper(reqs=[{"text": "cheapest", "kind": "compare_cheapest"}]),
                  TODAY).run(spec, task_id="t-dead")
    comps = [r for r in A.TaskStore("t-dead").records() if r["kind"] == "comparison"]
    assert comps[-1]["chosen"]["price"] == 400.0 and comps[-1]["opened"] is False   # the click changed nothing


async def test_a_comparison_counts_only_for_its_goal_and_conditions(browser, base_url):
    ag = AgentV4(browser, FakeClient(lambda st, q: {"op": "ASK"}), FakeHelper(), TODAY)
    store = A.TaskStore("t-cmp")
    store.add("comparison", goal="goal A", opened=True, conditions_met=True)
    ag._goal = "goal A"
    assert ag._comparison_ok(store)
    ag._goal = "goal A. Clarification: other dates"          # a new goal revision
    assert not ag._comparison_ok(store)
    store.add("comparison", goal=ag._goal, opened=True, conditions_met=False)   # compared before the filters held
    assert not ag._comparison_ok(store)


# ---------------------------------------------------------------- product round (Codex): outcomes, nav threshold

async def test_a_final_outcome_does_not_block_the_comparison(browser, base_url):
    reqs = [{"text": "nonstop only", "kind": "page"}, {"text": "cheapest opened", "kind": "compare_cheapest"},
            {"text": "details of the chosen option are shown", "kind": "outcome"}]
    calls = {"n": 0}

    def pol(st, q):
        calls["n"] += 1
        return {"op": "PICK_CHEAPEST", "req": 0.95} if calls["n"] == 2 else {"op": "WAIT", "req": 0.95}
    spec = TaskSpec(goal=CHEAP_GOAL, end_condition={"checks": [{"url_contains": "s45_detail"}]},
                    start_url=f"{base_url}/s41_results.html")
    client = FakeClient(pol, elig=not_eligible)

    class Outcome(FakeClient):  # the outcome requirement stays missing until the detail page
        async def system_one(self, state, questions):
            r = await client.system_one(state, questions)
            for k in questions:
                if k == "req2" and "S41" in state.get("title", ""):
                    r.nouls[k] = NS(noul=0.05)
            return r
    res = await AgentV4(browser, Outcome(pol), FakeHelper(reqs=reqs), TODAY).run(spec, task_id="t-outc")
    comps = [r for r in A.TaskStore("t-outc").records() if r["kind"] == "comparison"]
    assert comps[-1]["conditions_met"] and comps[-1]["opened"], comps[-1]
    assert res["status"] == "done", res


async def test_an_open_outcome_blocks_done(browser, base_url):
    reqs = [{"text": "return flight chosen and itinerary shown", "kind": "outcome"}]
    spec = TaskSpec(goal="Open the renewed console", end_condition={"checks": [{"url_contains": "#pro2"}]},
                    start_url=f"{base_url}/ok.html#pro2")
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "DONE", "done": 0.95, "req": 0.1}),
                        FakeHelper(reqs=reqs), TODAY).run(spec)
    assert res["status"] == "needs_help", res


async def test_nav_threshold_lets_low_confidence_navigation_act_but_bounded(browser, base_url):
    spec = TaskSpec(goal="Open the renewed console", end_condition={"checks": [{"url_contains": "#pro2"}]},
                    start_url=f"{base_url}/s24_results.html", limits={"steps": 20, "seconds": 60, "nav_threshold": 0.3})
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "CLICK", "target": "Renewed", "p": 0.35}),
                        FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done", res                       # p 0.35 ≥ 0.30 for a reversible click
    spec2 = TaskSpec(goal="Scroll", end_condition={"checks": [{"url_contains": "#never"}]},
                     start_url=f"{base_url}/s24_shop.html", limits={"steps": 20, "seconds": 60, "nav_threshold": 0.3})
    res2 = await AgentV4(browser, FakeClient(lambda st, q: {"op": "SCROLL_DOWN", "p": 0.35}), FakeHelper(),
                         TODAY).run(spec2)
    assert res2["status"] == "needs_help" and res2["metrics"]["steps"] <= 3, res2   # no change twice → normal threshold


def test_opening_is_identified_by_route_and_airline_summary():
    from jev.v4.agent import _identifies
    chosen = {"label": "From 15122 Turkish Lira round trip total. Nonstop flight with AJet. Leaves Sabiha Gökçen"}
    c = Control("j1", "link", "a", "", "x", full=chosen["label"] + " at 8:45 AM on Tuesday, October 20 and arrives at "
                "London Stansted Airport at 10:50 AM", card="8:45 AM – 10:50 AM AJet 4 hr 5 min SAW–STN Nonstop")
    assert _identifies(chosen, c, "Returning flights ... button: SAW–STN Change ... AJet")           # summary
    assert _identifies(chosen, c, "Departing 8:45 AM – 10:50 AM")                        # normalised times
    assert not _identifies(chosen, c, "Returning flights 3:40 PM – 10:35 PM Pegasus STN–SAW")       # another flight


def test_a_clarification_with_the_same_requirements_keeps_the_comparison():
    from jev.v4.agent import _req_key
    reqs = [{"text": "nonstop only", "kind": "page"}, {"text": "cheapest", "kind": "compare_cheapest"}]
    assert _req_key(reqs, "goal") == _req_key(reqs, "goal. Clarification: pick the return flight")
    assert _req_key(reqs, "goal") != _req_key(reqs + [{"text": "2 adults", "kind": "page"}], "goal")
    # outcomes are checked on the final page; adding one does not void the comparison of the eligible options
    assert _req_key(reqs, "goal") == _req_key(reqs + [{"text": "total for 2 adults shown", "kind": "outcome"}], "goal")


async def test_a_booking_click_needs_approval_even_below_the_nav_threshold(browser, base_url):
    spec = TaskSpec(goal="Show the booking options; do not book", end_condition={},
                    start_url=f"{base_url}/s46_booking.html", limits={"steps": 10, "seconds": 60, "nav_threshold": 0.3})
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "CLICK", "target": "Continue", "p": 0.32}),
                        FakeHelper(), TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "approve", res
    assert "s46_booking" in (await browser.info())["url"]


# ---------------------------------------------------------------- outcome contract (Codex decision)

OUTCOMES = [{"text": "both flights are shown with dates, airports and times", "kind": "outcome"},
            {"text": "total price for 2 adults and its currency are shown", "kind": "outcome"}]


async def test_outcome_contract_finishes_without_done_p(browser, base_url):
    spec = TaskSpec(goal="Show the chosen round trip's details", start_url=f"{base_url}/ok.html#pro2",
                    end_condition={"checks": [{"url_contains": "#pro2"}], "semantic": "details shown",
                                   "outcome_contract": True})
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "CLICK", "done": 0.4, "req": 0.9}),
                        FakeHelper(reqs=OUTCOMES), TODAY).run(spec)
    assert res["status"] == "done" and res["evidence"]["done_by"] == "outcome contract", res


async def test_outcome_contract_does_not_finish_with_the_return_flight_missing(browser, base_url):
    spec = TaskSpec(goal="Show the chosen round trip's details", start_url=f"{base_url}/ok.html#pro2",
                    end_condition={"checks": [{"url_contains": "#pro2"}], "semantic": "details shown",
                                   "outcome_contract": True})
    client = FakeClient(lambda st, q: {"op": "ASK", "done": 0.95, "req": 0.9})

    class ReturnMissing(FakeClient):
        async def system_one(self, state, questions):
            r = await client.system_one(state, questions)
            if "req0" in r.nouls:
                r.nouls["req0"] = NS(noul=0.2)       # "both flights shown": only the outbound is there
            return r
    res = await AgentV4(browser, ReturnMissing(lambda st, q: {}), FakeHelper(reqs=OUTCOMES), TODAY).run(spec)
    assert res["status"] == "needs_help", res


async def test_all_caller_requirements_are_tracked_and_the_tenth_gates_done(browser, base_url):
    # run 14: 10 caller requirements were cut to 8, dropping the airports/times and 2-adult total outcomes
    reqs = [f"search condition {i} holds" for i in range(7)] + OUTCOMES + [
        {"text": "the total price for 2 adults and its currency are shown " + "in full " * 40, "kind": "outcome"}]
    spec = TaskSpec(goal="Show the chosen round trip's details", start_url=f"{base_url}/ok.html#pro2",
                    end_condition={"checks": [{"url_contains": "#pro2"}], "semantic": "details shown",
                                   "requirements": reqs, "outcome_contract": True})
    client = FakeClient(lambda st, q: {"op": "ASK", "done": 0.95, "req": 0.9})

    class TenthMissing(FakeClient):
        async def system_one(self, state, questions):
            r = await client.system_one(state, questions)
            if "req9" in r.nouls:
                r.nouls["req9"] = NS(noul=0.2)
            return r
    res = await AgentV4(browser, TenthMissing(lambda st, q: {}), FakeHelper(), TODAY).run(spec, task_id="t-ten")
    assert res["status"] != "done", res
    recs = A.TaskStore("t-ten").records()
    items = [r for r in recs if r["kind"] == "requirements"][-1]["items"]
    assert len(items) == 10 and items[9]["text"].endswith("in full ")
    assert all(len(r["status"]) == 10 for r in recs if r["kind"] == "req_status")


def test_redactor_hides_secret_url_parameters():
    from jev.v4.privacy import Redactor
    u = Redactor().url("chrome-extension://x/connect.html?mcpRelayUrl=ws%3A&token=AbC123_secretvalue&client=1")
    assert "AbC123" not in u and "token=[redacted]" in u and "client=1" in u


def test_control_line_uses_the_full_name_and_drops_a_foreign_row_context():
    from jev.v4.agent import _line
    mk = lambda **k: Control(**{"jid": "j1", "role": "button", "tag": "button", "type": "", "text": "", **k})
    done = mk(jid="j398", text="Done. Search for round trip flights, departing on October 20, 2026 and returning",
              full="Done. Search for round trip flights, departing on October 20, 2026 and returning on October 27, 2026")
    select = mk(jid="j50", text="Select flight", context="Learn more about contrails")
    learn = mk(jid="j52", text="Learn more about contrails")
    edit = mk(jid="j60", text="Edit", context="Spring campaign")          # a real row label stays
    inview = [done, select, learn, edit]
    assert "returning on October 27, 2026" in _line(done, inview)
    assert "contrails" not in _line(select, inview) and "Select flight" in _line(select, inview)
    assert "(row: Spring campaign)" in _line(edit, inview)


async def test_an_empty_observation_is_reported_as_an_observation_failure(browser, base_url):
    spec = TaskSpec(goal="Show the flight details", end_condition={"checks": [{"url_contains": "#ok"}]},
                    start_url=f"{base_url}/s47_blank.html", limits={"steps": 5, "seconds": 60, "pilot": True})
    res = await AgentV4(browser, FakeClient(lambda st, q: {"op": "SCROLL_DOWN", "p": 0.9}), FakeHelper(), TODAY).run(
        spec, task_id="t-empty")
    assert res["status"] == "needs_help" and res["help"]["kind"] == "observation_empty", res
    assert "does not mean the site has no data" in res["help"]["question"]


async def test_content_that_renders_late_is_observed_after_the_bounded_wait(browser, base_url):
    seen = []
    spec = TaskSpec(goal="Open the flight", end_condition={"checks": [{"url_contains": "#ok"}]},
                    start_url=f"{base_url}/s48_late_content.html", limits={"steps": 5, "seconds": 60, "pilot": True})

    def policy(st, q):
        seen.append(st["visible_text"])
        return {"op": "CLICK", "target": "Open", "p": 0.9}
    res = await AgentV4(browser, FakeClient(policy), FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done", res
    assert "15,122" in seen[0]


# ---------------------------------------------------------------- task stage pilot (caller itinerary + evidence)

ITIN = {"type": "round trip", "legs": [{"id": "outbound", "from": "Istanbul", "to": "London", "date": "2026-10-20"},
                                       {"id": "return", "from": "London", "to": "Istanbul", "date": "2026-10-27"}]}


def _scripted(steps):
    seen = []

    def policy(st, q):
        seen.append(st.get("task_stage"))
        return steps[min(len(seen) - 1, len(steps) - 1)]
    return policy, seen


async def test_task_stage_follows_verified_selections_not_opened_details(browser, base_url):
    policy, seen = _scripted([{"op": "CLICK", "target": "Flight details 8:45"},
                              {"op": "CLICK", "target": "Select 8:45 AM AJet"},
                              {"op": "CLICK", "target": "Select flight"},
                              {"op": "ASK"}])
    spec = TaskSpec(goal="Choose the flights", start_url=f"{base_url}/s49_out.html",
                    end_condition={"checks": [{"url_contains": "s49_book"}], "itinerary": ITIN},
                    limits={"steps": 6, "seconds": 60})
    res = await AgentV4(browser, FakeClient(policy), FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done", res
    assert seen[0]["selected"] == [] and seen[0]["current_leg"].startswith("outbound")
    assert seen[1]["selected"] == [], "opening details in place is not a selection"
    assert [s["leg"] for s in seen[2]["selected"]] == ["outbound"] and seen[2]["current_leg"].startswith("return")
    assert "Select" not in json.dumps(seen[2]["current_leg"])          # no target or next click in the block


async def test_task_stage_one_way_has_no_invented_return(browser, base_url):
    one = {"type": "one way", "legs": [ITIN["legs"][0]]}
    policy, seen = _scripted([{"op": "CLICK", "target": "Select 8:45 AM AJet"}, {"op": "ASK"}])
    spec = TaskSpec(goal="Choose the flight", start_url=f"{base_url}/s49_out.html",
                    end_condition={"checks": [{"url_contains": "s49_book"}], "itinerary": one},
                    limits={"steps": 3, "seconds": 60})
    await AgentV4(browser, FakeClient(policy), FakeHelper(), TODAY).run(spec, task_id="t-oneway")
    recs = [r for r in A.TaskStore("t-oneway").records() if r["kind"] == "selection_check"]
    assert seen[1]["current_leg"] == "all legs selected" and len(seen[1]["trip"]["legs"]) == 1, recs
    assert "return" not in json.dumps(seen[1]).lower()


async def test_task_stage_change_back_to_the_list_undoes_the_selection(browser, base_url):
    policy, seen = _scripted([{"op": "CLICK", "target": "Select 8:45 AM AJet"}, {"op": "CLICK", "target": "Change"},
                              {"op": "ASK"}])
    spec = TaskSpec(goal="Choose the flights", start_url=f"{base_url}/s49_out.html",
                    end_condition={"checks": [{"url_contains": "s49_book"}], "itinerary": ITIN},
                    limits={"steps": 4, "seconds": 60})
    await AgentV4(browser, FakeClient(policy), FakeHelper(), TODAY).run(spec)
    assert seen[1]["current_leg"].startswith("return")
    assert seen[2]["selected"] == [] and seen[2]["current_leg"].startswith("outbound")


def test_task_stage_ignores_calendar_cells_and_other_leg_dates():
    from jev.v4.stage import selections
    r = lambda desc, a, b, **t: {"kind": "result", "ok": True, "option": "CLICK", "option_desc": desc, "target": t,
                                 "evidence": {"before": {"url": a}, "after": {"url": b}}}
    recs = [r("CLICK button: 27 ₺10.6K (row: October 2026-10-27)", "u1", "u2"),               # calendar cell
            r("CLICK link: TRY 16,627 Tue, Oct 27", "u2", "u3", text="TRY 16,627 Tue, Oct 27"),  # names the return date
            r("CLICK link: Search", "u3", "u4")]                                                # not priced
    assert selections(ITIN, recs) == []


def test_pilot_asks_the_observed_blocking_conditions():
    from jev.v4.agent import BLOCKED_OBSERVED, build_questions
    ops = {"CLICK": "click"}
    assert build_questions(ops, {}, [], None, [], observed_blocker=True)["blocked"].criteria == BLOCKED_OBSERVED
    assert build_questions(ops, {}, [], None, [])["blocked"].criteria != BLOCKED_OBSERVED


def test_a_priced_sort_tab_or_an_unverified_click_is_not_a_selection():
    from jev.v4.stage import selections
    r = lambda desc, a, b, **t: {"kind": "result", "ok": True, "option": "CLICK", "option_desc": desc, "target": t,
                                 "evidence": {"before": {"url": a}, "after": {"url": b}}}
    tab = r("CLICK tab: Cheapest from TRY 15,122", "u1", "u2", text="Cheapest from TRY 15,122")
    pick = r("CLICK link: 8:45 AM – 10:50 AM SAW–STN TRY 15,122", "u2", "u3", text="8:45 AM – 10:50 AM SAW–STN TRY 15,122")
    assert selections(ITIN, [tab]) == []
    assert selections(ITIN, [pick, {"kind": "selection_check", "result": 0, "verified": False, "at": 1}]) == []
    ok = selections(ITIN, [pick, {"kind": "selection_check", "result": 0, "verified": True, "at": 1}])
    assert [s["leg"] for s in ok] == ["outbound"]


async def test_pilot_stores_every_step_with_the_same_id_as_its_decision(browser, base_url):
    policy, _ = _scripted([{"op": "CLICK", "target": "Select 8:45 AM AJet"}, {"op": "ASK"}])
    spec = TaskSpec(goal="Choose the flight", start_url=f"{base_url}/s49_out.html",
                    end_condition={"checks": [{"url_contains": "s49_book"}], "itinerary": ITIN},
                    limits={"steps": 3, "seconds": 60, "pilot": True})
    await AgentV4(browser, FakeClient(policy), FakeHelper(), TODAY).run(spec, task_id="t-steps")
    recs = A.TaskStore("t-steps").records()
    steps = [r for r in recs if r["kind"] == "step_obs"]
    decisions = [r for r in recs if r["kind"] == "decision"]
    assert steps and [s["step"] for s in steps] == [d["step"] for d in decisions]
    assert "operation" in steps[0]["questions"] and "controls" in steps[0]["state"] and steps[0]["targets"]
    assert steps[0]["response"]["operation"]["choice"] == "CLICK"


async def test_hybrid_fallback_decides_an_uncertain_step_and_falls_back_to_help(browser, base_url, monkeypatch):
    spec = TaskSpec(goal="Choose the flight", start_url=f"{base_url}/s49_out.html",
                    end_condition={"checks": [{"url_contains": "s49_ret"}]},
                    limits={"steps": 4, "seconds": 60, "fallback": True})
    uncertain = FakeClient(lambda st, q: {"op": "SCROLL_DOWN", "p": 0.1})

    async def good(self, spec, store, state, q, targets, timeout=90.0):
        return "CLICK", next(c.cid for c in targets["CLICK"] if "8:45 AM AJet" in c.text), None
    monkeypatch.setattr(AgentV4, "_fallback", good)
    res = await AgentV4(browser, uncertain, FakeHelper(), TODAY).run(spec)
    assert res["status"] == "done", res

    async def fails(self, spec, store, state, q, targets, timeout=90.0):
        return None
    monkeypatch.setattr(AgentV4, "_fallback", fails)
    res = await AgentV4(browser, uncertain, FakeHelper(), TODAY).run(spec)
    assert res["status"] == "needs_help" and res["help"]["kind"] == "choose", res



def _cli(monkeypatch, answer):
    """Fake `claude -p` JSON output around a model answer text."""
    import subprocess
    out = json.dumps({"result": answer, "total_cost_usd": 0.01})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: NS(stdout=out, returncode=0))


async def test_real_fallback_parses_the_cli_answer_and_validates_target_and_scroll_area(monkeypatch):
    from typesafe_sdk import Choice
    ag = AgentV4(None, FakeClient(lambda st, q: {}), FakeHelper(), TODAY)
    store = A.TaskStore("t-fb")
    c1 = Control(jid="j1", role="link", tag="a", type="", text="Hotel A")
    q = {"operation": Choice(instructions="op", criteria={"CLICK": "click", "SCROLL_DOWN": "scroll", "DONE": "done"}),
         "click_target": Choice(instructions="t", criteria={"j1": "j1 link: Hotel A"}),
         "scroll_target": Choice(instructions="s", criteria={"page": "page", "c2": "results panel"})}
    spec = TaskSpec(goal="g", end_condition={}, limits={})
    _cli(monkeypatch, 'Sure: {"operation": "CLICK", "target": "j1", "scroll_target": null} done')
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) == ("CLICK", "j1", None)
    _cli(monkeypatch, '{"operation": "SCROLL_DOWN", "target": null, "scroll_target": "c2"}')
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) == ("SCROLL_DOWN", None, "c2")
    _cli(monkeypatch, '{"operation": "SCROLL_DOWN", "target": null, "scroll_target": "nope"}')
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) is None           # invalid area
    _cli(monkeypatch, '{"operation": "CLICK", "target": "click_target"}')
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) is None           # not an offered target
    _cli(monkeypatch, '{"operation": "DONE", "target": null}')
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) is None           # never DONE from the fallback
    _cli(monkeypatch, "no json at all")
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}) is None
    assert await ag._fallback(spec, store, {}, q, {"CLICK": [c1]}, timeout=2) is None  # no time left


async def test_cheapest_needs_distinct_listings_with_a_shown_rating(browser, base_url):
    spec = TaskSpec(goal="Find hotels in Tbilisi with a guest rating of 4.5 or higher and open the one with the lowest "
                         "price", start_url=f"{base_url}/s50_hotels.html",
                    end_condition={"checks": [{"url_contains": "#h"}],
                                   "requirements": ["hotels in Tbilisi", "guest rating 4.5 or higher",
                                                    {"text": "open the lowest price", "kind": "compare_cheapest"}]},
                    limits={"steps": 3, "seconds": 60})
    await AgentV4(browser, FakeClient(lambda st, q: {"op": "PICK_CHEAPEST", "p": 0.9}), FakeHelper(), TODAY).run(
        spec, task_id="t-hotels")
    comp = [r for r in A.TaskStore("t-hotels").records() if r["kind"] == "comparison"][0]
    assert comp["need_rating"] == 4.5 and comp["chosen"] and "Hotel Beta" in comp["chosen"]["label"], comp


def test_listing_key_keeps_one_letter_names():
    """Root cause of the S43/S44 failures: `Option X` and `Option Y` collapsed into one listing."""
    from jev.v4.prices import listing_key
    assert listing_key("Option X Seaside Resort: ₺100 per person, total ₺400") != \
        listing_key("Option Y Seaside Resort: ₺150 per person, total ₺300")
    assert listing_key("Deal A: total ₺500") != listing_key("Deal B: total ₺400")
    assert listing_key("Hotel Beta TRY 1,300") == listing_key("Hotel Beta TRY 1,250")   # same listing, other price
