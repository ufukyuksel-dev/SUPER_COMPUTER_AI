"""jev_task / jev_help: Jev drives a whole Chrome task; the caller (Claude/Codex) only helps when Jev asks.

Design: design note plan-jev-chrome-agent.md (private) (v3.1). Code owns the loop, the page view, execution, evidence, the done rule
and comparisons; Jev (TypeSafe System One) makes the judgments: next action, done, blocked, which input value, and
which cards match the item.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import asdict, dataclass, field

from typesafe_sdk import Choice, Noul

from jev.brain import BRAKE
from jev import paths
from jev.browser import SENSITIVE_HINTS, Element
from jev.pageview import PageView, build, clean, estimate_tokens, fit, next_chunk

log = logging.getLogger("jev.agent")

T_NEXT = 0.5          # below: ask for help instead of acting
T_DONE = 0.8
MAX_OPTIONS = 255     # TypeSafe Choice limit (action options incl. generic ones)
BUDGET_TOKENS = 6000  # page view budget per step (estimate; actual usage logged)
BLOCKED = {
    "nothing": "Nothing blocks the task on this page.",
    "login": "The page asks to sign in / create an account before the goal can continue.",
    "captcha": "A captcha, robot check or 'verify you are human' page blocks the goal.",
    "error": "An error page (not found, access denied, server error) is shown instead of content.",
    "data_not_available": "The page is right but the information the goal needs is not shown (e.g. prices hidden, "
                          "'see options', 'currently unavailable' for everything).",
}
PRICE = re.compile(r"(?:(?P<cur1>US\$|\$|€|£|TRY|TL|₺|USD|EUR)\s?(?P<a>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?))"
                   r"|(?:(?P<b>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s?(?P<cur2>TL|₺|TRY|€|USD|EUR))")


# ---------------------------------------------------------------- task spec, results, store

@dataclass
class TaskSpec:
    goal: str
    end_condition: dict                      # {"checks": [...], "semantic": "..."}
    start_url: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    select: dict | None = None               # {"item": "...", "order_by": "price_asc|price_desc", "max_price": 550}
    extract: dict | None = None              # {"pattern": "temperature|number|price", "fields": {"high": "..."}}
    limits: dict = field(default_factory=lambda: {"steps": 15, "seconds": 240})


def tasks_dir():
    """Resolved at call time so JEV_STATE_DIR from the .env loaded at startup applies."""
    return paths.state_dir() / "tasks"


class TaskStore:
    """Append-only record: spec, intent (before an action), result (after), help, help_reply."""

    def __init__(self, task_id: str):
        self.path = paths.ensure_dir(tasks_dir()) / f"{task_id}.jsonl"

    def add(self, kind: str, **data) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "kind": kind, **data}, ensure_ascii=False) + "\n")

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


def parse_price(text: str) -> tuple[float, str] | None:
    m = PRICE.search(text or "")
    if not m:
        return None
    raw = m.group("a") or m.group("b")
    cur = m.group("cur1") or m.group("cur2")
    # 1,234.56 / 1.234,56 / 32.450 -> float
    if re.search(r"[.,]\d{1,2}$", raw) and len(re.split(r"[.,]", raw)[-1]) <= 2 and raw.count(",") + raw.count(".") >= 1:
        dec = raw[-3] if raw[-3] in ".," else raw[-2]
        whole, frac = raw[:raw.rfind(dec)], raw[raw.rfind(dec) + 1:]
        value = float(re.sub(r"[.,]", "", whole) + "." + frac)
    else:
        value = float(re.sub(r"[.,]", "", raw))
    return value, cur


# ---------------------------------------------------------------- options

@dataclass
class Option:
    oid: str
    kind: str                 # click | type | hover | scroll | back | wait | none | ask | show_more | read_more
    eid: str | None = None
    target: str | None = None  # gid / rid
    desc: str = ""
    snapshot: dict | None = None  # element identity for re-validation


def build_options(view: PageView, shown: list[dict], groups: list[dict], inputs: dict,
                  truncated_rids: list[str], allowed: set[tuple[str, str]] | None = None) -> list[Option]:
    """Action options for the `next` Choice; ≤ MAX_OPTIONS including generic ones (design §4.1)."""
    generic = [Option("scroll", "scroll", desc="scroll down to load/see more of the page"),
               Option("back", "back", desc="go back to the previous page"),
               Option("wait", "wait", desc="wait for the page to finish loading"),
               Option("none", "none", desc="no listed action helps reach the goal"),
               Option("ask", "ask", desc="the goal is ambiguous or needs a decision from the caller"),
               Option("press:Enter", "press", target="Enter", desc="press Enter (submit the focused field/form)"),
               Option("press:Escape", "press", target="Escape", desc="press Escape (close a menu or popup)")]
    generic += [Option(f"show_more:{g['gid']}", "show_more", target=g["gid"],
                       desc=f"show {g['count']} hidden page parts ({', '.join(g['kinds'])}): {g['preview'][:80]}")
                for g in groups[:4]]
    generic += [Option(f"read_more:{rid}", "read_more", target=rid, desc=f"read the rest of region {rid}")
                for rid in truncated_rids[:4]]
    room = MAX_OPTIONS - len(generic)
    out: list[Option] = []
    shown_rids = {r["rid"] for r in shown}
    for r in view.regions:
        if r.rid not in shown_rids:
            continue
        for eid in r.eids:
            el = view.elements.get(eid)
            if not el:
                continue
            snap = {"role": el.role, "text": el.text, "context": el.context, "rid_text": r.text[:120]}
            state = f" ({el.state})" if el.state else ""
            if el.is_text_field() or el.is_value_field():
                # one option per (field, input value) that the field–value gate allowed: place and value together
                verb = "set" if el.is_value_field() else "type"
                for key, value in inputs.items():
                    if allowed is not None and (eid, key) not in allowed:
                        continue
                    out.append(Option(f"{verb}:{eid}={key}", verb, eid=eid, target=key,
                                      desc=f"{verb} inputs.{key} ('{value}') into {el.label}{state} [{r.rid}]",
                                      snapshot=snap))
                if el.tag != "select":
                    continue
            if el.tag == "select" or el.role == "file":
                continue  # native select: its options are offered as elements; file inputs: user only
            # the region text is in the state; the option only names the element and its region (keeps tokens low)
            out.append(Option(f"click:{eid}", "click", eid=eid, desc=f"click {el.label}{state} [{r.rid}]",
                              snapshot=snap))
            if r.kind == "nav" and el.role in ("button", "menuitem", "link") or "has popup" in el.state:
                out.append(Option(f"hover:{eid}", "hover", eid=eid, desc=f"hover {el.label} [{r.rid}] (open its menu)",
                                  snapshot=snap))
    return out[:room] + generic


# ---------------------------------------------------------------- the agent

class Agent:
    def __init__(self, browser, client):
        self.browser = browser
        self.client = client          # TypeSafe AsyncTypeSafeClient (or a fake in tests)
        self.usage_ratio = 1.0        # actual/estimated input tokens, corrected after each call

    async def ask(self, state: dict, questions: dict):
        est = estimate_tokens(state) + sum(estimate_tokens(getattr(q, "criteria", "")) +
                                           estimate_tokens(getattr(q, "instructions", "")) for q in questions.values())
        resp = await self.client.system_one(state=state, questions=questions)
        usage = getattr(resp, "usage", None)
        actual = getattr(usage, "input_tokens", None) if usage else None
        if actual:
            self.usage_ratio = 0.7 * self.usage_ratio + 0.3 * (actual / max(est, 1))
        return resp, est, actual

    # ---- public API

    async def run(self, spec: TaskSpec, task_id: str | None = None) -> dict:
        task_id = task_id or uuid.uuid4().hex[:10]
        store = TaskStore(task_id)
        recs = store.records()
        if not recs:
            store.add("spec", spec=asdict(spec))
            if spec.start_url:
                await self.browser.open(spec.start_url)
        else:
            spec = TaskSpec(**next(r["spec"] for r in recs if r["kind"] == "spec"))
            pending = _pending_intent(recs)
            if pending:  # process died between intent and result: never retry automatically
                view = await build(self.browser)
                return self._help(store, task_id, view, "clarify",
                                  f"The last action ({pending['option']}) may or may not have happened. Check the page "
                                  "and reply with clarify or pick.", [], _version(recs))
        return await self._loop(spec, store, task_id)

    async def help(self, task_id: str, help_id: str, page_version: int, reply: dict) -> dict:
        store = TaskStore(task_id)
        recs = store.records()
        if not recs:
            return {"task_id": task_id, "status": "failed", "reason": "unknown task_id"}
        done_reply = next((r for r in recs if r["kind"] == "help_reply" and r["help_id"] == help_id), None)
        if done_reply:  # single use: return the stored outcome, do nothing again
            return {"task_id": task_id, "status": "rejected", "reason": "help_id already used",
                    "outcome": done_reply.get("outcome")}
        req = next((r for r in recs if r["kind"] == "help" and r["help_id"] == help_id), None)
        if not req:
            return {"task_id": task_id, "status": "rejected", "reason": "unknown help_id"}
        spec = TaskSpec(**next(r["spec"] for r in recs if r["kind"] == "spec"))
        if "clarify" in reply:
            spec.goal = f"{spec.goal}. Clarification: {reply['clarify']}"
            store.add("spec", spec=asdict(spec))
            store.add("help_reply", help_id=help_id, reply=reply, outcome="goal clarified")
            return await self._loop(spec, store, task_id)
        if "skip" in reply:
            store.add("help_reply", help_id=help_id, reply=reply, outcome="skipped")
            return {"task_id": task_id, "status": "failed", "reason": "caller skipped"}
        ref = reply.get("pick") or reply.get("approve")
        opt = next((o for o in req["options"] if o["oid"] == ref), None)
        if not opt:
            return {"task_id": task_id, "status": "rejected", "reason": f"{ref} is not one of the offered options"}
        view = await build(self.browser)
        el = _revalidate(view, opt)
        if opt.get("eid") and el is None:
            store.add("help_reply", help_id=help_id, reply=reply, outcome="stale")
            return self._help(store, task_id, view, "choose",
                              "The page changed; the picked element is no longer the same. Pick again.",
                              [], _version(recs))
        o = Option(opt["oid"], opt["kind"], eid=el.id if el else None, target=opt.get("target"), desc=opt["desc"])
        store.add("help_reply", help_id=help_id, reply=reply, outcome="applied")
        await self._execute(store, spec, view, o, approved="approve" in reply)
        return await self._loop(spec, store, task_id)

    # ---- loop

    async def _loop(self, spec: TaskSpec, store: TaskStore, task_id: str) -> dict:
        t0 = time.monotonic()
        recs = store.records()
        steps_done = sum(1 for r in recs if r["kind"] == "result")
        pinned: set[str] = set()
        cursors: dict[str, int] = {}
        read_more: dict[str, tuple[int, str]] = {}
        last_key, repeats, failures = None, 0, 0
        selected_on: set[str] = set()
        answer = None
        while True:
            if steps_done >= spec.limits.get("steps", 15) or time.monotonic() - t0 > spec.limits.get("seconds", 240):
                return self._result(store, task_id, "budget_exhausted", None, answer)
            view = await build(self.browser)
            budget = int(BUDGET_TOKENS / 2 / max(self.usage_ratio, 0.5))  # other half: options/criteria
            # regions with input-capable controls are always shown (max 10): Jev must see where values can go
            field_rids = [r.rid for r in view.regions
                          if any(view.elements[e].is_text_field() or view.elements[e].is_value_field()
                                 for e in r.eids if e in view.elements)][:10]
            shown, groups = fit(view, spec.goal, budget, pinned | set(field_rids), read_more)
            groups_by_id = {g["gid"]: g for g in groups}
            truncated = [r["rid"] for r in shown if r.get("truncated")]
            typed_now = {r.get("value_key") for r in store.records() if r["kind"] == "result" and r.get("value_key")}
            open_inputs = {k: v for k, v in spec.inputs.items() if k not in typed_now}
            allowed = await self._gate(view, shown, open_inputs, store)
            options = build_options(view, shown, groups, open_inputs, truncated, allowed)
            by_oid = {o.oid: o for o in options}
            recs_now = store.records()
            history = [r["option_desc"] for r in recs_now if r["kind"] == "result"][-6:]
            typed = {r.get("value_key") for r in recs_now if r["kind"] == "result" and r.get("value_key")}
            pending = [k for k in spec.inputs if k not in typed]
            state = {"goal": spec.goal, "url": view.url, "title": view.title, "regions": shown,
                     "hidden_parts": [{k: g[k] for k in ("gid", "kinds", "count")} for g in groups],
                     "last_actions": history, **({"inputs": spec.inputs} if spec.inputs else {}),
                     **({"inputs_pending": pending} if pending else {}),
                     **({"selected": answer["item"]} if answer else {}),
                     **({"popup_open": True} if view.popup_open else {}),
                     **({"page_flags": view.flags} if view.flags else {})}
            questions = {
                "next": Choice(instructions="Which action should be done next to get closer to `goal`? Regions are "
                                            "parts of the page with their text; element ids are inside them. "
                                            "`inputs_pending` lists values not typed yet: a search or submit button "
                                            "is useless before its field is filled, so type the value first.",
                               criteria={o.oid: o.desc for o in options}),
                "done": Noul(instructions="Is `goal` fully achieved on this page, given `last_actions` (and "
                                          "`selected`, the listing chosen for the goal, if present)?",
                             criteria={"true": spec.end_condition.get("semantic") or
                                       "The page shows exactly what the goal asks for, and any action the goal "
                                       "asks for is already in `last_actions`.",
                                       "false": "The goal still needs more steps, or the page shows something "
                                                "else than the goal asks for."}),
                "blocked": Choice(instructions="Does something on this page block `goal`?", criteria=BLOCKED),
            }
            resp, est, actual = await self.ask(state, questions)
            nxt = resp.choices["next"]
            done_p = resp.nouls["done"].noul
            blocked = resp.choices["blocked"].choice
            decision = {"url": view.url, "next": nxt.choice, "next_p": round(nxt.confidence, 3),
                        "top": _top(nxt), "done_p": round(done_p, 3), "blocked": blocked,
                        "tokens_est": est, "tokens": actual, "regions": len(shown), "hidden": len(groups)}
            store.add("decision", **decision)

            # -- read tasks: Jev picks each asked value among spans code found on the page (design §3.3)
            if spec.extract and blocked == "nothing":
                got = await self._extract(spec, view, shown, store)
                if got:
                    answer = got
                    checks_ok, evidence = await self._checks(view, spec.end_condition)
                    if checks_ok or not spec.end_condition.get("checks"):
                        return self._result(store, task_id, "done", evidence, answer)

            # -- the single done rule (design §5)
            checks_ok, evidence = await self._checks(view, spec.end_condition)
            if checks_ok and blocked == "nothing":
                semantic = spec.end_condition.get("semantic")
                if not semantic or done_p >= T_DONE:
                    return self._result(store, task_id, "done", evidence, answer)
                if spec.end_condition.get("checks"):
                    return self._help(store, task_id, view, "choose",
                                      "The end checks pass but Jev is not sure this is the target. Is it?",
                                      _help_opts(nxt, by_oid), _version(store.records()), decision)

            # -- code-side selection: "cheapest <item>" (design §3.3/§5)
            if spec.select and view.url not in selected_on:
                picked = await self._select(spec, view, store)
                if picked and picked.get("status") == "needs_help":
                    return picked
                if picked and picked.get("option"):
                    selected_on.add(view.url)
                    answer = picked["answer"]
                    await self._execute(store, spec, view, picked["option"])
                    steps_done += 1
                    continue
                selected_on.add(view.url)

            opt_pre = by_oid.get(nxt.choice)
            can_act = opt_pre is not None and opt_pre.kind not in ("none", "ask") and nxt.confidence >= T_NEXT
            # login/captcha/error always stop; "data not available" only when Jev sees no confident next step
            # (it may still reach the data, e.g. via a filter or hidden page parts)
            if blocked != "nothing" and resp.choices["blocked"].confidence >= T_NEXT and \
                    (blocked != "data_not_available" or not can_act):
                return self._help(store, task_id, view, "login" if blocked == "login" else "blocked",
                                  f"Blocked: {BLOCKED[blocked]}", _help_opts(nxt, by_oid),
                                  _version(store.records()), decision)

            opt = by_oid.get(nxt.choice)
            if opt is None or opt.kind in ("none", "ask") or nxt.confidence < T_NEXT:
                q = "No action helps" if opt and opt.kind == "none" else \
                    "The goal needs a decision" if opt and opt.kind == "ask" else "Jev is not sure what to do next"
                return self._help(store, task_id, view, "choose", q, _help_opts(nxt, by_oid),
                                  _version(store.records()), decision)
            key = (view.fingerprint(), opt.oid)
            repeats = repeats + 1 if key == last_key else 0
            last_key = key
            if repeats >= 1:
                return self._help(store, task_id, view, "choose", "No progress: the same action on the same page",
                                  _help_opts(nxt, by_oid), _version(store.records()), decision)
            if opt.kind == "show_more":
                pinned |= set(groups_by_id.get(opt.target, {}).get("rids", []))
                store.add("result", option=opt.oid, option_desc=opt.desc, ok=True, evidence={"url": view.url})
                steps_done += 1
                continue
            if opt.kind == "read_more":
                region = next(r for r in view.regions if r.rid == opt.target)
                start = cursors.get(opt.target, 0)
                chunk, nxt_off = next_chunk(region, start, int(budget * 3.5 / 3))
                read_more[opt.target] = (start, chunk)
                cursors[opt.target] = nxt_off if nxt_off is not None else len(region.text)
                store.add("result", option=opt.oid, option_desc=opt.desc, ok=True,
                          evidence={"rid": opt.target, "offset": start, "next_offset": nxt_off})
                steps_done += 1
                continue
            el = view.elements.get(opt.eid) if opt.eid else None
            if el is not None and (BRAKE.search(el.text) or _typing_sensitive(el, opt)):
                return self._help(store, task_id, view, "approve",
                                  f"'{el.text}' changes, submits or pays for something (or is a sensitive field). "
                                  "Approve only after the user explicitly agreed.",
                                  [{"oid": opt.oid, "kind": opt.kind, "eid": opt.eid, "desc": opt.desc,
                                    "snapshot": opt.snapshot, "p": round(nxt.confidence, 3)}],
                                  _version(store.records()), decision)
            ok = await self._execute(store, spec, view, opt,
                                     value_key=opt.target if opt.kind in ("type", "set") else None)
            steps_done += 1
            failures = 0 if ok else failures + 1
            if failures >= 2:
                return self._help(store, task_id, view, "choose", "Two actions failed in a row",
                                  _help_opts(nxt, by_oid), _version(store.records()), decision)

    # ---- execution with intent/result records

    async def _execute(self, store: TaskStore, spec: TaskSpec, view: PageView, opt: Option,
                       value_key: str | None = None, approved: bool = False) -> bool:
        el = view.elements.get(opt.eid) if opt.eid else None
        store.add("intent", option=opt.oid, option_desc=opt.desc)
        before = {"url": view.url, "title": view.title}
        ok, err, typed_key = True, None, None
        try:
            if opt.kind == "click" and el is not None:
                await self.browser.click(el)
            elif opt.kind == "hover" and el is not None:
                await self.browser.hover(el)
            elif opt.kind == "type" and el is not None:
                key = value_key or opt.target
                typed_key = key
                if key not in spec.inputs:
                    raise RuntimeError("no input value to type")
                await self.browser.type_text(el, spec.inputs[key], submit=el.is_search_field())
            elif opt.kind == "set" and el is not None:
                key = value_key or opt.target
                typed_key = key
                if key not in spec.inputs:
                    raise RuntimeError("no input value to set")
                if el.role == "slider" or el.type == "range":
                    reached = await set_slider(self.browser, el, spec.inputs[key])
                    store.add("slider", eid=el.id, target=spec.inputs[key], reached=reached)
                else:
                    await self.browser.type_text(el, spec.inputs[key], submit=False)
            elif opt.kind == "press":
                await self.browser.press(opt.target)
            elif opt.kind == "scroll":
                await self.browser.scroll()
            elif opt.kind == "back":
                await self.browser.back()
            elif opt.kind == "wait":
                await asyncio.sleep(1.5)
        except Exception as e:  # noqa: BLE001 - recorded, the loop decides
            ok, err = False, (str(e).splitlines() or [type(e).__name__])[0][:200]
        info = await self.browser.info()
        store.add("result", option=opt.oid, option_desc=opt.desc, ok=ok, error=err, approved=approved,
                  evidence={"before": before, "after": info},
                  **({"value_key": typed_key} if opt.kind in ("type", "set") and ok else {}))
        return ok

    # ---- end condition checks (deterministic)

    async def _checks(self, view: PageView, cond: dict) -> tuple[bool, dict]:
        evidence, ok = {"url": view.url, "title": view.title}, True
        checks = cond.get("checks") or []
        if not checks:
            return False, evidence  # without checks only an explicit help/answer path can finish
        for c in checks:
            if "url_contains" in c:
                r = c["url_contains"].lower() in view.url.lower()
            elif "new_page_title_contains" in c:
                r = c["new_page_title_contains"].lower() in view.title.lower()
            elif "element_state" in c:
                spec = c["element_state"]
                el = next((e for e in view.elements.values() if spec["ref_text"].lower() in e.label.lower()), None)
                st = await self.browser.element_state(el) if el else {}
                want = spec["state"]
                r = bool(st) and ((want == "checked" and st.get("checked")) or
                                  (want.startswith(("selected:", "value:")) and
                                   want.split(":", 1)[1].lower() in str(st.get("value", "")).lower()))
                evidence[f"state:{spec['ref_text']}"] = st
            elif "answer_kind" in c:
                r = True  # proves only the type of an answer; the value is checked semantically (design §5)
            else:
                r = False
            evidence[json.dumps(c, ensure_ascii=False)] = bool(r)
            ok = ok and bool(r)
        return ok, evidence

    # ---- read tasks: select values among code-extracted spans (never generated)

    async def _extract(self, spec: TaskSpec, view: PageView, shown: list[dict], store: TaskStore) -> dict | None:
        pat = {"temperature": r"-?\d{1,2}\s?°\s?C?", "price": PRICE.pattern,
               "number": r"-?\d+(?:[.,]\d+)?"}.get(spec.extract.get("pattern", "number"), spec.extract.get("pattern"))
        rx = re.compile(pat)
        shown_rids = {r["rid"] for r in shown}
        cands = []
        for r in view.regions:
            if r.rid not in shown_rids:
                continue
            for m in rx.finditer(r.text):
                a, b = max(0, m.start() - 70), min(len(r.text), m.end() + 30)
                cands.append({"value": m.group(0).strip(), "context": clean(r.text[a:b]), "rid": r.rid})
                if len(cands) >= 200:
                    break
        if not cands:
            return None
        fields = spec.extract["fields"]
        questions = {name: Choice(instructions=f"Which candidate in `candidates` is: {desc}? Use each candidate's "
                                               "`context` (the page text around it). Pick none if it is not on the page.",
                                  criteria={**{f"v{i}": f"{c['value']} — …{c['context']}…" for i, c in enumerate(cands)},
                                            "none": "The asked value is not among the candidates."})
                     for name, desc in fields.items()}
        state = {"goal": spec.goal, "url": view.url, "title": view.title, "candidates": cands}
        resp, est, actual = await self.ask(state, questions)
        out, ok = {}, True
        for name in fields:
            c = resp.choices[name]
            if c.choice == "none" or c.confidence < T_NEXT:
                ok = False
                out[name] = {"value": None, "p": round(c.confidence, 3)}
            else:
                cand = cands[int(c.choice[1:])]
                out[name] = {"value": cand["value"], "p": round(c.confidence, 3), "source": cand["context"],
                             "region": cand["rid"]}
        store.add("extract", url=view.url, candidates=len(cands), result=out, tokens=actual)
        return {**out, "page": view.url} if ok else None

    # ---- field–value gate (design note plan-universal-widgets.md (private))

    async def _gate(self, view: PageView, shown: list[dict], inputs: dict, store: TaskStore) -> set[tuple[str, str]]:
        """Which (field, input) pairs make sense: one Noul per pair, cached per page + field label + key."""
        if not inputs:
            return set()
        cache = self.__dict__.setdefault("gate_cache", {})
        shown_rids = {r["rid"] for r in shown}
        fields = [(eid, r) for r in view.regions if r.rid in shown_rids for eid in r.eids
                  if eid in view.elements and (view.elements[eid].is_text_field() or view.elements[eid].is_value_field())]
        page = view.url.split("#")[0]
        todo, allowed = [], set()
        for eid, r in fields[:30]:
            el = view.elements[eid]
            for key in inputs:
                ck = (page, el.label, key)
                if ck in cache:
                    if cache[ck] >= 0.5:
                        allowed.add((eid, key))
                else:
                    todo.append((eid, r, key, ck))
        if todo:
            questions = {f"f{i}": Noul(
                instructions=f"Should `pairs[{i}].value` be entered into the field `pairs[{i}].field` to reach `goal`?",
                criteria={"true": "This field is the place for this value (e.g. a price value in a price/max field, a "
                                  "search phrase in a search box).",
                          "false": "This value does not belong in this field (e.g. a price in a search box)."})
                for i in range(len(todo))}
            state = {"goal": store.records()[0]["spec"]["goal"] if store.records() else "",
                     "pairs": [{"field": f"{view.elements[e].label} ({view.elements[e].state})".strip(),
                                "field_region": r.text[:160], "value": f"inputs.{k} = '{inputs[k]}'"}
                               for e, r, k, _ in todo]}
            resp, est, actual = await self.ask(state, questions)
            for i, (eid, r, key, ck) in enumerate(todo):
                p = resp.nouls[f"f{i}"].noul
                cache[ck] = p
                if p >= 0.5:
                    allowed.add((eid, key))
            store.add("gate", url=view.url, pairs=[{"field": view.elements[e].label, "key": k,
                                                    "p": round(resp.nouls[f"f{i}"].noul, 3)}
                                                   for i, (e, r, k, _) in enumerate(todo)], tokens=actual)
        return allowed

    # ---- selection among cards, comparison in code

    async def _select(self, spec: TaskSpec, view: PageView, store: TaskStore) -> dict | None:
        cards = [r for r in view.regions if r.kind == "card" and len(r.text) > 20 and
                 any(view.elements[e].role == "link" for e in r.eids if e in view.elements)]
        words = set(re.findall(r"\w+", spec.select["item"].lower()))
        need = max(1, len(words) - 1)

        def hits(text: str) -> int:
            return len(words & set(re.findall(r"\w+", text.lower())))
        # only cards naming the item by whole words (all but one), best matches first: a listing page, not menus
        cards = sorted((c for c in cards if hits(c.text) >= need), key=lambda c: -hits(c.text))
        if len(cards) < 2:
            return None
        cards = cards[:40]
        item = spec.select["item"]
        questions = {f"c{i}": Noul(instructions=f"Is `cards[{i}]` a listing of: {item}?",
                                   criteria={"true": f"The card is exactly a {item}.",
                                             "false": "The card is something else (an accessory, a different model, "
                                                      "a bundle or unrelated item)."})
                     for i in range(len(cards))}
        state = {"goal": spec.goal, "item": item, "cards": [c.text[:300] for c in cards]}
        resp, est, actual = await self.ask(state, questions)
        rel = [(c, resp.nouls[f"c{i}"].noul) for i, c in enumerate(cards)]
        relevant = [c for c, p in rel if p >= 0.5]
        store.add("select", url=view.url, cards=len(cards), relevant=len(relevant),
                  probs=[round(p, 3) for _, p in rel], tokens_est=est, tokens=actual)
        if not relevant:
            return None
        priced = [(c, parse_price(c.text)) for c in relevant]
        with_price = [(c, p) for c, p in priced if p]
        if not with_price:
            return self._help(store, store.path.stem, view, "blocked",
                              f"{len(relevant)} listings match '{item}', but none shows a price on this page "
                              "(e.g. 'See options' / hidden for the delivery country).",
                              [{"oid": f"click:{_title_link(view, c).id}", "kind": "click",
                                "eid": _title_link(view, c).id, "desc": clean(c.text[:120]),
                                "snapshot": _snap(view, _title_link(view, c), c), "p": None}
                               for c in relevant[:3] if _title_link(view, c)],
                              _version(store.records()))
        cap = spec.select.get("max_price")
        within = [(c, p) for c, p in with_price if cap is None or p[0] <= float(cap)]
        if not within:
            return self._help(store, store.path.stem, view, "blocked",
                              f"{len(with_price)} matching listings show a price, but none is at or below the "
                              f"maximum {cap} (lowest seen: {min(p[0] for _, p in with_price)} "
                              f"{with_price[0][1][1]}).", [], _version(store.records()))
        reverse = spec.select.get("order_by") == "price_desc"
        best, (value, cur) = sorted(within, key=lambda cp: cp[1][0], reverse=reverse)[0]
        link = _title_link(view, best)
        if link is None:
            return None
        answer = {"item": clean(best.text[:160]), "price": value, "currency": cur,
                  "scope": f"{'highest' if reverse else 'lowest'} among {len(within)} matching listings with a "
                           f"visible price{f' ≤ {cap}' if cap is not None else ''} on this page; "
                           f"{len(with_price) - len(within)} matching listings were above the maximum; "
                           f"{len(relevant) - len(with_price)} matching listings had no visible price; "
                           f"{len(cards) - len(relevant)} cards did not match"}
        return {"option": Option(f"click:{link.id}", "click", eid=link.id, desc=f"open {link.label} (selected: "
                                                                                f"{answer['scope']})"),
                "answer": answer}

    # ---- help / result

    def _help(self, store: TaskStore, task_id: str, view: PageView, kind: str, question: str, options: list[dict],
              version: int, decision: dict | None = None) -> dict:
        help_id = uuid.uuid4().hex[:8]
        store.add("help", help_id=help_id, page_version=version, question=question, help_kind=kind, options=options)
        return {"task_id": task_id, "status": "needs_help",
                "help": {"help_id": help_id, "page_version": version, "kind": kind, "question": question,
                         "options": [{k: o.get(k) for k in ("oid", "desc", "p")} for o in options],
                         "page": {"url": view.url, "title": view.title}},
                **({"last_decision": decision} if decision else {}), "trace": _trace(store)}

    def _result(self, store: TaskStore, task_id: str, status: str, evidence, answer) -> dict:
        store.add("end", status=status)
        return {"task_id": task_id, "status": status, "evidence": evidence, "answer": answer, "trace": _trace(store)}


# ---------------------------------------------------------------- helpers

def _num(text: str) -> float | None:
    m = re.search(r"-?\d[\d.,]*", text or "")
    if not m:
        return None
    raw = m.group(0).rstrip(".,")
    if re.search(r"[.,]\d{1,2}$", raw):
        return float(re.sub(r"[.,]", "", raw[:-3]) + "." + raw[-2:]) if raw[-3] in ".," else \
            float(re.sub(r"[.,]", "", raw[:-2]) + "." + raw[-1:])
    return float(re.sub(r"[.,]", "", raw))


async def set_slider(browser, el: Element, target: str, max_presses: int = 400) -> str:
    """Move any slider (native range or ARIA) with the keyboard, reading the value a person sees
    (aria-valuetext / value), to the largest value ≤ target. Works when the shown value is not the raw number
    (e.g. index 12 shown as "$550"). Returns the value text it ended on."""
    goal = _num(str(target))
    if goal is None:
        raise RuntimeError(f"not a number: {target}")
    await browser.focus(el)
    cur_txt = await browser.widget_value(el)
    cur = _num(cur_txt)
    if cur is None:
        raise RuntimeError(f"slider value not readable: {cur_txt!r}")
    same = 0
    for _ in range(max_presses):
        if cur > goal:
            key = "ArrowLeft"
        else:
            await browser.press("ArrowRight", el)
            nxt_txt = await browser.widget_value(el)
            nxt = _num(nxt_txt)
            if nxt is None or nxt == cur:  # at the end
                break
            if nxt > goal:                 # one step too far: back to the last value ≤ goal
                await browser.press("ArrowLeft", el)
                cur_txt = await browser.widget_value(el)
                break
            cur, cur_txt = nxt, nxt_txt
            continue
        await browser.press(key, el)
        nxt_txt = await browser.widget_value(el)
        nxt = _num(nxt_txt)
        same = same + 1 if nxt == cur else 0
        if nxt is None or same >= 3:
            break
        cur, cur_txt = nxt, nxt_txt
        if cur <= goal:
            break
    return cur_txt

def _pending_intent(recs: list[dict]) -> dict | None:
    last = None
    for r in recs:
        if r["kind"] == "intent":
            last = r
        elif r["kind"] == "result":
            last = None
    return last


def _version(recs: list[dict]) -> int:
    """Increments with every navigation recorded (url change in a result)."""
    v, url = 0, None
    for r in recs:
        if r["kind"] == "result":
            u = (r.get("evidence") or {}).get("after", {}).get("url")
            if u and u != url:
                v, url = v + 1, u
    return v


def _top(ch) -> list:
    return [(k, round(p, 3)) for k, p in sorted(ch.probabilities.items(), key=lambda kv: -kv[1])[:3]]


def _help_opts(ch, by_oid: dict[str, Option]) -> list[dict]:
    out = []
    for k, p in sorted(ch.probabilities.items(), key=lambda kv: -kv[1]):
        o = by_oid.get(k)
        if o and o.kind not in ("none", "ask"):
            out.append({"oid": o.oid, "kind": o.kind, "eid": o.eid, "target": o.target, "desc": o.desc,
                        "snapshot": o.snapshot, "p": round(p, 3)})
        if len(out) == 3:
            break
    return out


def _value_choice(resp) -> str | None:
    v = resp.choices.get("value") if hasattr(resp.choices, "get") else None
    return v.choice if v and v.choice != "none" else None


def _revalidate(view: PageView, opt: dict) -> Element | None:
    """Same role, text, row context and region text as when offered (design §6)."""
    snap = opt.get("snapshot")
    if not opt.get("eid") or not snap:
        return None
    for e in view.elements.values():
        if e.role == snap["role"] and e.text == snap["text"] and e.context == snap["context"]:
            r = view.region_of(e.id)
            if r is None or r.text[:120] == snap["rid_text"] or snap["rid_text"][:60] in r.text:
                return e
    return None


def _typing_sensitive(el: Element, opt: Option) -> bool:
    if opt.kind != "type":
        return False
    hay = f"{el.text} {el.hint} {el.type}".lower()
    return el.type in ("password", "email", "tel") or any(w in hay for w in SENSITIVE_HINTS)


def _title_link(view: PageView, region) -> Element | None:
    links = [view.elements[e] for e in region.eids if e in view.elements and view.elements[e].role == "link"]
    return max(links, key=lambda e: len(e.text), default=None)


def _snap(view: PageView, el: Element | None, region) -> dict | None:
    if el is None:
        return None
    return {"role": el.role, "text": el.text, "context": el.context, "rid_text": region.text[:120]}


def _trace(store: TaskStore) -> list[dict]:
    out = []
    for r in store.records():
        if r["kind"] == "decision":
            out.append({"decision": {k: r[k] for k in ("url", "next", "next_p", "done_p", "blocked", "tokens")}})
        elif r["kind"] == "result":
            out.append({"action": r["option_desc"][:120], "ok": r["ok"],
                        "url": (r.get("evidence") or {}).get("after", {}).get("url")})
        elif r["kind"] == "select":
            out.append({"select": {k: r[k] for k in ("cards", "relevant", "tokens")}})
        elif r["kind"] == "extract":
            out.append({"extract": {k: r[k] for k in ("url", "candidates", "result")}})
        elif r["kind"] in ("help", "help_reply"):
            out.append({r["kind"]: {k: r.get(k) for k in ("help_id", "question", "outcome")}})
    return out[-40:]
