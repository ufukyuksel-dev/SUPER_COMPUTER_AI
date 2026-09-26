"""Task stage for multi-leg tasks (experimental pilot, Codex plan-stage-runtime-pilot.md).

The caller gives the itinerary once (`end_condition["itinerary"]`: trip type and legs with id, from, to, date); the
runtime has no city or date constants. Which legs are selected comes only from verified browser evidence in the task
records:

- a selection CANDIDATE is a successful CLICK on a link/button item that has a price AND an identity beyond the
  price (its times or a route code), that changed the page address, and whose text does not name another leg's
  date. Opening details in place (same address), date-picker cells (ISO-date context), tabs/radios (e.g. a
  "Cheapest from TRY 15,122" sort tab) are not candidates;
- a candidate counts only when the NEXT observation shows that identity (`selection_check` record written by the
  agent loop); an unverified candidate does not advance the stage. Old task logs without checks accept the
  comparison record's verified opening of the same click;
- going back to the address a selection was made from (BACK, "Change") undoes it and every later one; typing into a
  field after a selection means the search changed and undoes all of them; scrolling changes nothing.

The block never names a target or a next click.
"""
from __future__ import annotations

import datetime as dt
import re

from .prices import find_prices

CAL_CELL = re.compile(r"\(row: [^)]*\d{4}-\d{2}-\d{2}\)|\d{4}-\d{2}-\d{2}")


def _addr(url: str | None) -> str:
    return (url or "").split("#", 1)[0].rstrip("/")


def mentions_date(text: str, iso: str) -> bool:
    """Whether `text` names the calendar date `iso` (month-name, ISO or numeric day/month forms)."""
    try:
        d = dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    month, mon = d.strftime("%B"), d.strftime("%b")
    forms = [rf"\b(?:{month}|{mon})\.? {d.day}\b", rf"\b{d.day} (?:{month}|{mon})\b", re.escape(d.isoformat()),
             rf"\b0?{d.day}[./]0?{d.month}[./]{d.year}\b", rf"\b0?{d.month}/0?{d.day}/{d.year}\b"]
    return any(re.search(f, text or "", re.I) for f in forms)


TIME = re.compile(r"\b\d{1,2}:\d{2}\s?(?:[AP]M)?", re.I)
ROUTE = re.compile(r"\b[A-Z]{3}\s?[–—-]\s?[A-Z]{3}\b")


def _norm(t: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"[–—-]", "-", t or "")).lower()


def identity(text: str) -> dict:
    """What identifies an item beyond its price: its times and route codes."""
    return {"times": sorted({_norm(t) for t in TIME.findall(text or "")}),
            "routes": sorted({_norm(r) for r in ROUTE.findall(text or "")})}


def identity_shown(ident: dict, page: str) -> bool:
    """The item is shown in `page`: ≥ 2 of its times (or its only time), or one of its route codes."""
    hay = _norm(page)
    times, routes = ident.get("times") or [], ident.get("routes") or []
    if times and sum(1 for t in times if t in hay) >= min(2, len(times)):
        return True
    return any(r in hay for r in routes)


def candidate(r: dict, legs: list[dict], n_selected: int) -> dict | None:
    """The selection candidate a result record represents, or None."""
    if r.get("kind") != "result" or not r.get("ok") or r.get("option") != "CLICK" or n_selected >= len(legs):
        return None
    ev = r.get("evidence") or {}
    before, after = _addr((ev.get("before") or {}).get("url")), _addr((ev.get("after") or {}).get("url"))
    desc = r.get("option_desc", "")
    if not before or not after or before == after or not re.match(r"CLICK (link|button):", desc):
        return None
    t = r.get("target") or {}
    if CAL_CELL.search(t.get("context", "")) or CAL_CELL.search(desc):
        return None
    text = " ".join([t.get("text", ""), t.get("card", ""), desc])
    ident = identity(text)
    if not find_prices(text) or not (ident["times"] or ident["routes"]):
        return None
    leg = legs[n_selected]
    if any(mentions_date(text, o.get("date")) for o in legs if o is not leg) and not mentions_date(text, leg.get("date")):
        return None
    return {"leg": leg.get("id"), "option": (t.get("text") or desc)[:160], "from_addr": before, "identity": ident}


def _leg_str(leg: dict) -> str:
    return f"{leg.get('from')} to {leg.get('to')}, {leg.get('date')}"


def selections(itinerary: dict, records: list[dict], current_url: str | None = None) -> list[dict]:
    legs = itinerary.get("legs") or []
    checks = {r.get("result"): r for r in records if r.get("kind") == "selection_check"}
    sel: list[dict] = []
    for k, r in enumerate(records):
        if r.get("kind") != "result" or not r.get("ok"):
            continue
        after = _addr(((r.get("evidence") or {}).get("after") or {}).get("url"))
        for i, s in enumerate(sel):          # back at the address a selection was made from → undone
            if after and after == s["from_addr"]:
                sel = sel[:i]
                break
        if r.get("option") in ("TYPE", "SET"):
            sel = []                         # the search itself changed
            continue
        cand = candidate(r, legs, len(sel))
        if not cand:
            continue
        chk = checks.get(k)
        if chk is not None:
            ok, how = bool(chk.get("verified")), f"result #{k}; next observation shows the item (check #{chk.get('at')})"
        else:                                # old logs: the comparison's verified opening of the same click
            cmp_ = next((c for c in records[k + 1:k + 3] if c.get("kind") == "comparison" and c.get("opened")), None)
            ok, how = cmp_ is not None, f"result #{k}; comparison opening verified (old log, no selection check)"
        if ok:
            sel.append({**cand, "record": k, "evidence": how})
    cur = _addr(current_url)
    for i, s in enumerate(sel):
        if cur and cur == s["from_addr"]:
            sel = sel[:i]
            break
    return sel


def pending_check(itinerary: dict, records: list[dict]) -> tuple[int, dict] | None:
    """The latest result, if it is a selection candidate that has no check yet (checked on the next observation)."""
    legs = itinerary.get("legs") or []
    k = next((i for i in range(len(records) - 1, -1, -1) if records[i].get("kind") == "result"), None)
    if k is None or any(r.get("kind") == "selection_check" and r.get("result") == k for r in records):
        return None
    cand = candidate(records[k], legs, len(selections(itinerary, records[:k])))
    return (k, cand) if cand else None


def task_stage(itinerary: dict | None, records: list[dict], current_url: str | None = None) -> dict | None:
    if not itinerary or not itinerary.get("legs"):
        return None
    legs = itinerary["legs"]
    sel = selections(itinerary, records, current_url)
    done = {s["leg"] for s in sel}
    todo = [l for l in legs if l.get("id") not in done]
    if todo:
        cur = todo[0]
        status = "; ".join(f"{l.get('id')} {'selected' if l.get('id') in done else 'not selected'}" for l in legs)
        current = f"{cur.get('id')} ({_leg_str(cur)}): {status}"
    else:
        current = "all legs selected"
    return {"trip": {"type": itinerary.get("type", ""), "legs": legs},
            "selected": [{k: s[k] for k in ("leg", "option", "evidence")} for s in sel],
            "current_leg": current}
