"""Jev request + decision, and the step loop (one action per step)."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from rapidfuzz import fuzz
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

from jev.browser import Browser, Element

log = logging.getLogger("jev.brain")

MAX_ELEMENTS = 150
DONE_THRESHOLD = 0.8
TARGET_MIN_CONF = 0.4
FIELD_MIN_CONF = 0.5

# Heuristic brake only; guarantees nothing.
BRAKE = re.compile(
    r"\b(buy|pay|purchase|checkout|publish|delete|submit|save|confirm|satın al|öde|ödeme|yayınla|sil|gönder|kaydet|onayla)\b",
    re.IGNORECASE,
)


def text_window(text: str, max_chars: int, near_text: str | None = None) -> tuple[str, bool]:
    """Cut page text to `max_chars`, centred on the first match of `near_text` if given. Returns (text, truncated)."""
    max_chars = max(1, max_chars)
    if len(text) <= max_chars:
        return text, False
    start = 0
    # re.IGNORECASE instead of str.lower(): "İ".lower() is two characters, so "istanbul" would miss "İstanbul"
    # and indexes into the lowered string would drift.
    if near_text and (m := re.search(re.escape(near_text), text, re.IGNORECASE)):
        start = max(0, min(m.start() - max_chars // 3, len(text) - max_chars))
    return text[start:start + max_chars], True


def rank(goal: str, elements: list[Element], limit: int = MAX_ELEMENTS) -> list[Element]:
    """Keep the elements whose text is most similar to the goal (stable for ties)."""
    if len(elements) <= limit:
        return elements
    scored = sorted(
        enumerate(elements),
        key=lambda ie: (-fuzz.token_set_ratio(goal.lower(), ie[1].label.lower()), ie[0]),
    )
    keep = {i for i, _ in scored[:limit]}
    return [e for i, e in enumerate(elements) if i in keep]


def _describe(e: Element) -> str:
    """Choice option text: the label plus the element's card details (e.g. price), so Jev can compare cards."""
    return f"{e.label} — {e.details[:160]}" if e.details else e.label


@dataclass
class Decision:
    kind: str  # "done" | "click" | "type" | "stuck" | "needs_you"
    element: Element | None = None
    p: float = 0.0
    done_p: float = 0.0
    options: list[dict] = field(default_factory=list)
    reason: str = ""


class Brain:
    def __init__(self, client: AsyncTypeSafeClient | None = None, model: str = "jev-latest"):
        self.client = client or AsyncTypeSafeClient(model=model)
        # Per decision: what Jev was offered and what it chose (for tracing failures; newest last, bounded).
        self.decisions: list[dict] = []
        # Unbounded totals for timing (the `decisions` trace above is capped).
        self.decide_count = 0
        self.decide_ms_total = 0

    async def decide(
        self, goal: str, page: dict, elements: list[Element], history: list[str], text: str | None,
        popup_open: bool = False, failed: list[str] | None = None,
    ) -> Decision:
        # Text fields are never click targets; they are only used via the `field` question when text is given.
        clickable = [e for e in elements if not e.is_text_field()]
        candidates = rank(goal, clickable)
        by_id = {e.id: e for e in candidates}
        search_fields = [e for e in elements if e.is_search_field()] if text else []
        by_id.update({e.id: e for e in search_fields})

        state = {
            "goal": goal,
            "url": page["url"],
            "title": page["title"],
            "elements": [{"id": e.id, "role": e.role, "text": e.text, **({"row": e.context} if e.context else {}),
                          **({"details": e.details} if e.details else {})}
                         for e in candidates + search_fields],
            "last_clicks": history[-5:],
        }
        if text:
            state["text_to_type"] = text
        if popup_open:
            state["popup_open"] = True
        if failed:
            state["could_not_click"] = failed
        target_instructions = "Which element in `elements` should be clicked next to get closer to `goal`?"
        if failed:
            target_instructions += (
                " `could_not_click` lists elements whose click just failed, usually because a banner, cookie bar or "
                "popup covers them. If one of them is needed for `goal`, pick the element that closes, rejects or "
                "accepts that covering element."
            )
        if popup_open:
            target_instructions = (
                "A popup (`popup_open`) covers the page and `elements` are the popup's buttons. Which element should "
                "be clicked next to get closer to `goal`? If the popup does not serve `goal`, pick the element that "
                "closes or dismisses it (e.g. close, got it, not now); do not start tours or new flows."
            )
        questions = {
            "done": Noul(
                instructions="Does the current page (`url`, `title`, `elements`) already show what `goal` describes?",
                criteria={
                    "true": "The page is the destination the goal asks for. If the goal asks to click, press, "
                            "open, select or turn on something, that action is already in `last_clicks`.",
                    "false": "The goal still needs more navigation, or it asks for an action (click, press, open, "
                             "select, turn on) that is not in `last_clicks` yet; seeing the control is not enough.",
                },
            ),
            "target": Choice(
                instructions=target_instructions,
                criteria={**{e.id: _describe(e) for e in candidates}, "none": "No listed element helps reach the goal."},
            ),
        }
        if search_fields:
            questions["field"] = Choice(
                instructions="Into which search field in `elements` should `text_to_type` be typed to get closer to `goal`?",
                criteria={**{e.id: e.label for e in search_fields}, "none": "None of these fields fits."},
            )

        t0 = time.monotonic()
        resp = await self.client.system_one(state=state, questions=questions)
        ms = int((time.monotonic() - t0) * 1000)
        self.decide_count += 1
        self.decide_ms_total += ms
        done_p = resp.nouls["done"].noul
        tgt = resp.choices["target"]
        if "field" in resp.choices:
            fa = resp.choices["field"]
            log.info("jev field=%s conf=%.2f", fa.choice, fa.confidence)
        top = sorted(tgt.probabilities.items(), key=lambda kv: -kv[1])[:3]
        options = [{"id": k, "text": by_id[k].label if k in by_id else k, "p": round(v, 3)} for k, v in top]
        log.info("jev %dms done=%.2f target=%s conf=%.2f top=%s", ms, done_p, tgt.choice, tgt.confidence, options)
        fld_ans = resp.choices.get("field")
        self.decisions = self.decisions[-49:] + [{
            "url": page["url"], "offered": [by_id[e["id"]].label for e in state["elements"]],
            "target": by_id[tgt.choice].label if tgt.choice in by_id else tgt.choice,
            "target_p": round(tgt.confidence, 3), "done_p": round(done_p, 3), "ms": ms,
            **({"field": by_id[fld_ans.choice].label if fld_ans.choice in by_id else fld_ans.choice,
                "field_p": round(fld_ans.confidence, 3)} if fld_ans else {}),
        }]

        if done_p >= DONE_THRESHOLD:
            return Decision("done", done_p=done_p, options=options)

        if text:
            fld = resp.choices.get("field")
            if fld and fld.choice != "none" and fld.confidence >= FIELD_MIN_CONF:
                return Decision("type", element=by_id[fld.choice], p=fld.probabilities[fld.choice], done_p=done_p)
            if not search_fields:
                return Decision("needs_you", done_p=done_p, options=options, reason="text given but no search field")

        if tgt.choice == "none" or tgt.choice not in by_id or tgt.confidence < TARGET_MIN_CONF:
            reason = "low confidence" if tgt.choice in by_id else "Jev: no listed element helps"
            return Decision("stuck", done_p=done_p, options=options, reason=reason)
        el = by_id[tgt.choice]
        if BRAKE.search(el.text):
            return Decision("needs_you", element=el, done_p=done_p, options=options,
                            reason=f"'{el.text}' looks like a risky action; click it yourself")
        return Decision("click", element=el, p=tgt.probabilities[tgt.choice], done_p=done_p, options=options)


BeforeAct = Callable[[Browser, Decision], Awaitable[None]]


async def run(
    browser: Browser,
    brain: Brain,
    goal: str,
    text: str | None = None,
    max_steps: int = 10,
    before_act: BeforeAct | None = None,
) -> dict:
    """Step loop. `before_act` is a test hook that runs between deciding and acting."""
    steps: list[dict] = []
    history: list[str] = []
    pending_text = text
    status, options, reason, done_p = "max_steps", [], "", 0.0
    last_url = ""
    failures = 0
    # Labels whose action just failed (e.g. covered by a banner): not offered again until another action succeeds.
    failed: set[str] = set()

    for n in range(1, max_steps + 1):
        decision = None
        for attempt in range(2):  # one re-read if the chosen element changed
            elements = [e for e in await browser.read_elements() if e.label not in failed]
            decision = await brain.decide(goal, await browser.info(), elements, history, pending_text,
                                          popup_open=getattr(browser, "popup_open", False), failed=sorted(failed))
            if decision.kind not in ("click", "type"):
                break
            if before_act:
                await before_act(browser, decision)
            if await browser.still_same(decision.element):
                break
            log.info("element %s changed before acting; re-reading", decision.element.id)
            decision = Decision("stuck", reason="chosen element changed", done_p=decision.done_p)

        done_p = decision.done_p
        if decision.kind in ("done", "stuck", "needs_you"):
            status, options, reason = decision.kind, decision.options, decision.reason
            break

        el = decision.element
        if decision.kind == "click" and history and history[-1] == el.label and browser.page.url == last_url:
            status, options, reason = "stuck", decision.options, f"no progress: '{el.text}' clicked twice"
            break
        last_url = browser.page.url
        try:
            if decision.kind == "type":
                await browser.fill_and_submit(el, pending_text)
                pending_text = None
                history.append(f"typed into {el.label}")
            else:
                await browser.click(el)
                history.append(el.label)
            failed.clear()
        except Exception as e:  # e.g. something covered the element; re-read the page on the next step
            first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
            log.info("action on %s failed: %s", el.label, first_line)
            failed.add(el.label)
            history.append(f"failed: {el.label}")
            failures += 1
            if failures >= 2:
                status, options, reason = "stuck", decision.options, f"action failed twice: {first_line}"
                break
            continue
        dialog = browser.take_dialog() if hasattr(browser, "take_dialog") else None
        if dialog:
            status, reason = "needs_you", f"browser dialog appeared and was dismissed (not accepted): {dialog}"
            steps.append({"n": n, "action": decision.kind, "element_text": el.text, "p": round(decision.p, 3),
                          "url_after": browser.page.url})
            break
        step = {"n": n, "action": decision.kind, "element_text": el.text, "p": round(decision.p, 3),
                "url_after": browser.page.url}
        steps.append(step)
        log.info("step %s", step)

    info = await browser.info()
    result = {"status": status, **info, "jev_done_p": round(done_p, 3), "steps": steps}
    if options:
        result["options"] = options
    if reason:
        result["reason"] = reason
    return result
