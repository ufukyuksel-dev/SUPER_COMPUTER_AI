"""MCP server (stdio). stdout is reserved for the protocol; all logs go to stderr."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import os
import time

from mcp.server.mcpserver import MCPServer

from jev import env, runlog
from jev.brain import BRAKE, Brain, run, text_window
from jev import paths
from jev.browser import SENSITIVE_HINTS, Browser, Element

log = logging.getLogger("jev.mcp")

# Told up front (not only in refusals) so the agent does not have to discover the rule by trial.
JEV_FIRST_NOTE = (
    " This server runs in jev-first mode: for every action call jev_do first. jev_click/jev_type/jev_hover are refused "
    "until jev_do has returned stuck/needs_you/max_steps; then up to 2 of them are allowed, each with `reason`."
)
server = MCPServer(
    "jev",
    instructions=(
        "Browser control where TypeSafe Jev picks which on-page element to click and Chrome clicks it. "
        "For a whole task use jev_task (Jev runs every step; answer its needs_help with jev_help). "
        "Use jev_open to load a page, jev_do to pursue a navigation goal, jev_look to see the current page, "
        "jev_read to read the page text (Jev itself cannot read text). "
        "To search, put the search phrase in jev_do's `text` argument, not only in `goal`: "
        "jev_do(goal='Search for Bosphorus Bridge and open its article', text='Bosphorus Bridge'). "
        "When jev_do returns stuck/low confidence, the calling agent may take over one step with jev_click/jev_type "
        "(element ids from jev_look; pass `reason`: why Jev could not do it) and then call jev_do again. "
        "status 'done' is only Jev's opinion; verify the returned url/title."
    ) + (JEV_FIRST_NOTE if "--jev-first" in sys.argv else ""),
)
_browser = None  # Browser (own Chrome window) or ExtensionBrowser (user's Chrome)
_brain: Brain | None = None
_last: dict[str, Element] = {}

# --jev-first: takeover actions are only allowed after a jev_do that did not finish, and need a reason.
TAKEOVERS_PER_STUCK = 2  # e.g. jev_hover to reveal a menu, then jev_click
_policy = {"jev_first": False, "budget": 0, "last_jev_do": None}


def takeover_log():
    """Resolved at call time so JEV_STATE_DIR from the .env loaded at startup applies."""
    return paths.state_dir() / "takeovers.jsonl"


def _log_takeover(rec: dict) -> None:
    path = takeover_log()
    paths.ensure_dir(path.parent)
    with path.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")


def takeover_gate(tool: str, element: str, reason: str) -> str | None:
    """Why a takeover action must be refused under --jev-first, or None (and one unit of budget is used)."""
    if not _policy["jev_first"]:
        return None
    why = None
    if _policy["budget"] <= 0:
        why = ("jev-first: call jev_do for this step first; takeover is only allowed after jev_do returns "
               "stuck/needs_you/max_steps")
    elif not reason.strip():
        why = "jev-first: give `reason` (why Jev could not do this step)"
    _log_takeover({"tool": tool, "element": element, "reason": reason, "allowed": why is None,
                   "after_jev_do": _policy["last_jev_do"], "refusal": why})
    if why is None:
        _policy["budget"] -= 1
    return why

# Clicks the agent may only make after the user explicitly approved that exact action.
NEEDS_APPROVAL = re.compile(BRAKE.pattern + r"|\b(save|kaydet|confirm|onayla|apply|uygula|launch|başlat)\b", re.I)


async def _get():
    global _brain
    await _browser.start()
    if _brain is None:
        _brain = Brain()
    return _browser, _brain


def check_takeover(el: Element | None, *, typing: bool = False, user_approved: bool = False) -> str | None:
    """Why an agent-chosen click/type must not run, or None if it may."""
    if el is None:
        return "unknown element id; call jev_look first"
    if typing:
        haystack = f"{el.text} {el.hint} {el.type}".lower()
        if el.type in ("password", "email", "tel") or any(w in haystack for w in SENSITIVE_HINTS):
            return f"'{el.text}' looks like a sensitive field; the user must type into it"
    elif NEEDS_APPROVAL.search(el.text) and not user_approved:
        return f"'{el.text}' changes or submits something; ask the user, then call again with user_approved=true"
    return None


@server.tool()
async def jev_open(url: str) -> dict:
    """Open a URL in the Jev-controlled Chrome tab."""
    browser, _ = await _get()
    await browser.open(url)
    _policy["budget"] = 0
    return await browser.info()


@server.tool()
async def jev_do(goal: str, text: str | None = None, max_steps: int = 10, expect: str | None = None) -> dict:
    """Pursue a navigation goal on the current page: Jev picks an element each step, Chrome clicks it.

    text: the text to type once into a search field. Jev is only offered search fields when `text` is set, so a
    search phrase written only inside `goal` is never typed. Example:
    jev_do(goal="Search for Bosphorus Bridge and open its article", text="Bosphorus Bridge").
    expect: optional URL/title substring of the real destination, used only to log whether it was actually reached.
    """
    browser, brain = await _get()
    t0, n0, ms0 = time.monotonic(), brain.decide_count, brain.decide_ms_total
    result = await run(browser, brain, goal, text=text, max_steps=max(1, min(max_steps, 20)))
    # Counters, not the bounded `decisions` trace (which keeps only the last 50 entries).
    result["timing"] = {"total_ms": int((time.monotonic() - t0) * 1000),
                        "decide_ms": brain.decide_ms_total - ms0, "decisions": brain.decide_count - n0}
    result["reached"] = runlog.record(goal, result, expect)["reached"]
    _policy["last_jev_do"] = result["status"]
    _policy["budget"] = 0 if result["status"] == "done" else TAKEOVERS_PER_STUCK
    return result


@server.tool()
async def jev_task(goal: str, end_condition: dict | None = None, start_url: str | None = None,
                   inputs: dict | None = None, select: dict | None = None, max_steps: int = 15, max_seconds: int = 240,
                   task_id: str | None = None, engine: str | None = None) -> dict:
    """Run a whole browser task with Jev (preferred over jev_do). Jev plans each step from the full page view; you
    only help when it returns status "needs_help" (answer with jev_help).

    end_condition (required): {"checks": [...], "semantic": "what the final page/answer must show"}. Checks:
      {"url_contains": "..."} | {"new_page_title_contains": "..."} |
      {"element_state": {"ref_text": "...", "state": "checked" | "selected:<v>" | "value:<v>"}} |
      {"answer_kind": "price|number|date|text"}
    inputs: every value Jev may type, e.g. {"query": "PlayStation 5 Pro console"}. Jev never invents text.
    select: pick among listing cards in code, e.g. {"item": "PlayStation 5 Pro console", "order_by": "price_asc",
      "max_price": 550} (prices are parsed and compared in code, never guessed by Jev).
    Returns {task_id, status: done|needs_help|failed|budget_exhausted, answer?, evidence, trace, help?}.

    engine="v4" (or env JEV_ENGINE=v4): viewport view + operation/target heads; values are written by a text helper
    and checked in code (inputs/select are not needed; give the whole task in `goal`). Read questions finish with an
    answer whose quote is on the page. end_condition is optional in v4; without checks an action task ends with a
    confirm_done help request.
    """
    from jev.agent import Agent, TaskSpec

    browser, brain = await _get()
    spec = TaskSpec(goal=goal, end_condition=end_condition or {}, start_url=start_url, inputs=inputs or {},
                    select=select, limits={"steps": max(1, min(max_steps, 40)), "seconds": max(30, max_seconds)})
    if (engine or os.environ.get("JEV_ENGINE", "v3")) == "v4":
        from jev.v4.agent import AgentV4
        return await AgentV4(browser, brain.client).run(spec, task_id)
    return await Agent(browser, brain.client).run(spec, task_id)


@server.tool()
async def jev_help(task_id: str, help_id: str, page_version: int, reply: dict) -> dict:
    """Answer a jev_task help request, then Jev continues where it stopped.

    reply: {"pick": "<oid from help.options>"} | {"clarify": "sub-goal or missing fact"} |
           {"approve": "<oid>"} (only after the user explicitly approved that exact action) | {"skip": true}.
    v4 also: {"text": "<value>"} (value for the asked field; still checked), {"takeover_done": true} (you did the step
    yourself; Jev re-reads the page), {"confirm": true} (for kind confirm_done, after you verified the page).
    A help_id can be used once; if the page changed, Jev re-validates the element and asks again instead of acting.
    """
    from jev.agent import Agent, TaskStore

    browser, brain = await _get()
    recs = TaskStore(task_id).records()
    if any(r.get("engine") == "v4" for r in recs if r["kind"] == "spec"):
        from jev.v4.agent import AgentV4
        return await AgentV4(browser, brain.client).help(task_id, help_id, page_version, reply)
    return await Agent(browser, brain.client).help(task_id, help_id, page_version, reply)


@server.tool()
async def jev_look(limit: int = 80) -> dict:
    """Current URL, title and clickable elements as 'id role: text' (ids are valid for jev_click/jev_type)."""
    browser, _ = await _get()
    elements = await browser.read_elements()
    _last.clear()
    _last.update({e.id: e for e in elements})
    return {
        **await browser.info(),
        "popup_open": getattr(browser, "popup_open", False),
        "elements": [f"{e.id} {e.label}" for e in elements[: max(1, min(limit, 300))]],
        "total_elements": len(elements),
    }


@server.tool()
async def jev_read(max_chars: int = 4000, near_text: str | None = None) -> dict:
    """Visible text of the current page (read-only; no click, no Jev call). Use it to read values Jev cannot see.

    near_text: return the part of the page around the first match of this text, e.g. near_text="opened".
    """
    browser, _ = await _get()
    text = await browser.read_text()
    part, truncated = text_window(text, max(200, min(max_chars, 20000)), near_text)
    return {**await browser.info(), "text": part, "total_chars": len(text), "truncated": truncated}


@server.tool()
async def jev_click(element_id: str, user_approved: bool = False, reason: str = "") -> dict:
    """Agent takeover: click one element from the last jev_look (use when Jev is stuck or unsure).

    Clicks that save/submit/pay/publish/delete are refused unless the user explicitly approved that exact action
    in the conversation (then pass user_approved=true). reason: why Jev could not do this step (required when the
    server runs with --jev-first).
    """
    browser, _ = await _get()
    el = _last.get(element_id)
    if why := check_takeover(el, user_approved=user_approved):
        return {"status": "refused", "reason": why}
    if why := takeover_gate("jev_click", el.label, reason):
        return {"status": "refused", "reason": why}
    if not await browser.still_same(el):
        return {"status": "stale", "reason": "page changed since jev_look; call jev_look again"}
    await browser.click(el)
    log.info("agent takeover click: %s (approved=%s)", el.label, user_approved)
    return {"status": "clicked", "element": el.label, **await browser.info()}


@server.tool()
async def jev_hover(element_id: str, reason: str = "") -> dict:
    """Agent takeover: move the mouse over one element from the last jev_look (reveals hover-only buttons, e.g. row
    Edit buttons). Call jev_look afterwards to see the new elements. reason: required with --jev-first."""
    browser, _ = await _get()
    el = _last.get(element_id)
    if el is None:
        return {"status": "refused", "reason": "unknown element id; call jev_look first"}
    if why := takeover_gate("jev_hover", el.label, reason):
        return {"status": "refused", "reason": why}
    await browser.hover(el)
    return {"status": "hovered", "element": el.label, **await browser.info()}


@server.tool()
async def jev_type(element_id: str, text: str, submit: bool = False, reason: str = "") -> dict:
    """Agent takeover: type text into one field from the last jev_look (e.g. a date). Never for password/card fields.
    reason: required with --jev-first."""
    browser, _ = await _get()
    el = _last.get(element_id)
    if why := check_takeover(el, typing=True):
        return {"status": "refused", "reason": why}
    if why := takeover_gate("jev_type", el.label, reason):
        return {"status": "refused", "reason": why}
    if not await browser.still_same(el):
        return {"status": "stale", "reason": "page changed since jev_look; call jev_look again"}
    if hasattr(browser, "type"):
        await browser.type(el, text, submit=submit)
    else:
        await el.handle.fill(text, timeout=5000)
        if submit:
            await el.handle.press("Enter")
    log.info("agent takeover type into %s (submit=%s)", el.label, submit)
    return {"status": "typed", "element": el.label, **await browser.info()}


def main() -> None:
    global _browser
    ap = argparse.ArgumentParser(prog="jev-mcp")
    ap.add_argument("--profile", default="mcp")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--backend", choices=["own", "extension"], default="own",
                    help="own: separate Chrome window; extension: the user's Chrome via the Playwright extension")
    ap.add_argument("--jev-first", action="store_true",
                    help="refuse jev_click/jev_type/jev_hover until a jev_do has returned stuck/needs_you/max_steps")
    args = ap.parse_args()
    _policy["jev_first"] = args.jev_first
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(name)s %(message)s")
    env.load()
    if args.backend == "extension":
        from jev.ext_browser import ExtensionBrowser

        _browser = ExtensionBrowser()
    else:
        _browser = Browser(profile=args.profile, headless=args.headless)
    server.run("stdio")


if __name__ == "__main__":
    main()
