"""Page view: the whole visible page as regions (cards, rows, dialogs, text blocks) with their elements.

This is what Jev sees in `jev_task` (design: design note plan-jev-chrome-agent.md (private) §3). Regions carry their visible text, so
facts next to a link (price, stock, "redirected from", table values) reach Jev without per-site code.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from jev.browser import Element

REGION_TEXT_CAP = 300      # chars of region text shown per step (rest via read_more)
REGION_FULL_CAP = 6000     # chars kept per region for read_more
CHARS_PER_TOKEN = 3.5      # estimate before sending; corrected from `usage` by the agent


@dataclass
class Region:
    rid: str
    kind: str
    text: str                       # full visible text (capped at REGION_FULL_CAP)
    eids: list[str] = field(default_factory=list)

    @property
    def truncated(self) -> bool:
        return len(self.text) > REGION_TEXT_CAP


@dataclass
class PageView:
    url: str
    title: str
    regions: list[Region]
    elements: dict[str, Element]    # eid -> element (ids from read_elements)
    popup_open: bool = False
    flags: list[str] = field(default_factory=list)

    def region_of(self, eid: str) -> Region | None:
        return next((r for r in self.regions if eid in r.eids), None)

    def fingerprint(self) -> str:
        return hashlib.sha1((self.url + "|" + "|".join(r.text[:200] for r in self.regions)).encode()).hexdigest()[:12]


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- own backend (Playwright ElementHandles)

_REGIONS_JS = """
(els) => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const REG = 'dialog,[role=dialog],[role=alertdialog],li,tr,[role=row],[role=listitem],article,[role=article],' +
              'form,nav,[role=navigation],header,footer,[data-component-type],[data-asin]';
  const shown = el => { const r = el.getBoundingClientRect(), st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
  const kindOf = r => r.matches('dialog,[role=dialog],[role=alertdialog]') ? 'dialog'
    : r.matches('tr,[role=row]') ? 'row' : r.matches('form') ? 'form'
    : r.matches('nav,[role=navigation],header') ? 'nav' : r.matches('footer') ? 'footer' : 'card';
  const regionFor = el => {
    const own = clean(el.innerText || el.getAttribute('aria-label') || '');
    let r = el.parentElement && el.parentElement.closest(REG);
    // a tiny match (e.g. a star-rating <li>) is not the card; climb one more matching ancestor
    if (r && clean(r.innerText).length < own.length + 5 && r.parentElement) r = r.parentElement.closest(REG) || r;
    if (r && clean(r.innerText).length <= 1500) return r;
    // card heuristic: nearest ancestor that says more than the element, but not a whole page section
    for (let a = el.parentElement, i = 0; a && a !== document.body && i < 8; a = a.parentElement, i++) {
      const t = clean(a.innerText).length;
      if (t > 1500) break;
      if (t >= own.length + 5) return a;
    }
    return null;
  };
  const regions = [], index = new Map(), elRegion = [];
  for (const el of els) {
    if (!el) { elRegion.push(-1); continue; }
    const r = regionFor(el);
    if (!r) { elRegion.push(-1); continue; }
    if (!index.has(r)) { index.set(r, regions.length); regions.push({kind: kindOf(r), text: clean(r.innerText).slice(0, %d)}); }
    elRegion.push(index.get(r));
  }
  // text-only blocks outside those regions (headings, paragraphs, table cells): facts without a link
  const covered = [...index.keys()];
  const blocks = [];
  for (const b of document.querySelectorAll('h1,h2,h3,[role=heading],p,dd,dt,caption,table')) {
    if (blocks.length >= 80 || !shown(b) || covered.some(r => r.contains(b) || b.contains(r))) continue;
    if (blocks.some(x => x.el.contains(b))) continue;
    const t = clean(b.innerText);
    if (t.length >= 2) blocks.push({el: b, kind: b.matches('table') ? 'table' : 'text', text: t.slice(0, %d)});
  }
  return {regions, elRegion, blocks: blocks.map(b => ({kind: b.kind, text: b.text})),
          canvas: [...document.querySelectorAll('canvas')].some(c => c.width * c.height > 200000 && shown(c)),
          textLen: clean(document.body ? document.body.innerText : '').length};
}
""" % (REGION_FULL_CAP, REGION_FULL_CAP)


async def build_own(browser, elements: list[Element]) -> PageView:
    main = browser.page.main_frame
    handles = []
    for e in elements:
        try:
            same_frame = await e.handle.owner_frame() == main
        except Exception:
            same_frame = False
        handles.append(e.handle if same_frame else None)
    data = await browser.page.evaluate(_REGIONS_JS, handles)
    regions = [Region(rid=f"r{i}", kind=r["kind"], text=r["text"]) for i, r in enumerate(data["regions"])]
    loose = Region(rid="r_page", kind="page", text="")
    for e, ri in zip(elements, data["elRegion"]):
        (regions[ri] if ri >= 0 else loose).eids.append(e.id)
    base = len(regions)
    regions += [Region(rid=f"r{base + i}", kind=b["kind"], text=b["text"]) for i, b in enumerate(data["blocks"])]
    if loose.eids:
        regions.append(loose)
    info = await browser.info()
    flags = (["canvas_or_image_ui"] if data["canvas"] else []) + (["text_empty"] if data["textLen"] < 50 else [])
    if any(f != main for f in browser.page.frames if f.url and not f.url.startswith(("about:", "data:"))
           and _origin(f.url) != _origin(info["url"])):
        flags.append("iframe_cross_origin")
    return PageView(info["url"], info["title"], regions, {e.id: e for e in elements},
                    getattr(browser, "popup_open", False), flags)


def _origin(url: str) -> str:
    m = re.match(r"^(\w+://[^/]+)", url or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------- extension backend (Playwright MCP snapshot)

_LINE = re.compile(r'^(?P<ind>\s*)- (?P<role>[\w/-]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?(?P<attrs>(?: \[[^\]]*\])*)'
                   r'(?::\s*(?P<tail>.*))?$')
_REF = re.compile(r"\[ref=([^\]]+)\]")
_REGION_ROLES = {"dialog": "dialog", "alertdialog": "dialog", "listitem": "card", "row": "row", "article": "card",
                 "form": "form", "navigation": "nav", "banner": "nav", "contentinfo": "footer", "search": "form"}
_TEXT_ROLES = {"heading", "paragraph", "text", "cell", "columnheader", "rowheader", "term", "definition", "caption"}


def _parse(snap: str):
    nodes = []
    for ln in snap.splitlines():
        m = _LINE.match(ln)
        if m:
            name = (m["name"] or "").replace('\\"', '"')
            tail = (m["tail"] or "").strip().strip('"')
            ref = _REF.search(m["attrs"] or "")
            nodes.append({"ind": len(m["ind"]), "role": m["role"], "ref": ref.group(1) if ref else None,
                          "words": "" if m["role"].startswith("/") else " ".join(x for x in (name, tail) if x)})
    stack: list[int] = []  # parent index and subtree end in one linear pass
    for i, n in enumerate(nodes):
        while stack and nodes[stack[-1]]["ind"] >= n["ind"]:
            nodes[stack.pop()]["end"] = i
        n["parent"] = stack[-1] if stack else -1
        stack.append(i)
    for i in stack:
        nodes[i]["end"] = len(nodes)
    return nodes


def _subtree_text(nodes, i) -> str:
    seen, parts = set(), []
    for n in nodes[i:nodes[i]["end"]]:
        w = n["words"]
        if w and w not in seen:
            seen.add(w)
            parts.append(w)
    return clean(" ".join(parts))


async def build_ext(browser, elements: list[Element]) -> PageView:
    snap = await browser.snapshot()
    nodes = _parse(snap)
    by_ref = {n["ref"]: i for i, n in enumerate(nodes) if n["ref"]}
    regions: list[Region] = []
    reg_of_node: dict[int, int] = {}
    loose = Region(rid="r_page", kind="page", text="")

    def region_node(i: int) -> int | None:
        own = len(nodes[i]["words"])
        j, steps = nodes[i]["parent"], 0
        while j >= 0 and steps < 12:
            steps += 1
            t = len(_subtree_text(nodes, j))
            if t > 1500:
                return None
            if t >= own + 5:
                return j  # nearest ancestor that says more than the element: its card / row / dialog
            j = nodes[j]["parent"]
        return None

    by_role_name = {}
    for i, n in enumerate(nodes):
        if not n["ref"] and n["role"] in ("slider", "spinbutton", "textbox", "searchbox", "checkbox", "radio", "switch"):
            by_role_name.setdefault((n["role"], n["words"]), i)
    for e in elements:
        i = by_ref.get(e.handle) if isinstance(e.handle, str) else None
        if i is None and isinstance(e.handle, str) and e.handle.startswith("role="):
            # ref-less control targeted by role+name: find its line (its words start with the name)
            i = next((j for (role, words), j in by_role_name.items()
                      if role == e.role and words.startswith(e.text)), None)
        j = region_node(i) if i is not None else None
        if j is None:
            loose.eids.append(e.id)
            continue
        if j not in reg_of_node:
            kind = _REGION_ROLES.get(nodes[j]["role"], "card")
            reg_of_node[j] = len(regions)
            regions.append(Region(rid=f"r{len(regions)}", kind=kind, text=_subtree_text(nodes, j)[:REGION_FULL_CAP]))
        regions[reg_of_node[j]].eids.append(e.id)
    # text-only blocks not inside an element region
    covered = [(j, nodes[j]["end"]) for j in reg_of_node]
    blocks = 0
    for i, n in enumerate(nodes):
        if blocks >= 80 or n["role"] not in _TEXT_ROLES or not n["words"]:
            continue
        if any(a <= i < b for a, b in covered):
            continue
        if n["role"] == "text" and len(n["words"]) < 2:
            continue
        regions.append(Region(rid=f"r{len(regions)}", kind="text", text=_subtree_text(nodes, i)[:REGION_FULL_CAP]))
        covered.append((i, n["end"]))
        blocks += 1
    if loose.eids:
        regions.append(loose)
    info = await browser.info()
    text_len = sum(len(n["words"]) for n in nodes)
    return PageView(info["url"], info["title"], regions, {e.id: e for e in elements},
                    getattr(browser, "popup_open", False), ["text_empty"] if text_len < 50 else [])


async def build(browser) -> PageView:
    elements = await browser.read_elements()
    if hasattr(browser, "snapshot"):
        return await build_ext(browser, elements)
    return await build_own(browser, elements)


# ---------------------------------------------------------------- budget fit

def estimate_tokens(obj) -> int:
    return int(len(str(obj)) / CHARS_PER_TOKEN) + 1


def fit(view: PageView, goal: str, budget_tokens: int, pinned: set[str] = frozenset(),
        read_more: dict[str, tuple[int, str]] | None = None) -> tuple[list[dict], list[dict]]:
    """Choose regions for this step within the token budget.

    Returns (shown regions as state dicts in page order, omitted groups [{gid, kinds, count, rids}]).
    Dialogs, pinned regions (show_more) and regions with an open read_more chunk are always kept; the rest are ranked
    by similarity to the goal. read_more: rid -> (offset, chunk text) to show instead of the first 300 chars.
    """
    read_more = read_more or {}
    must = {r.rid for r in view.regions if r.kind == "dialog" or r.rid in pinned or r.rid in read_more}
    ranked = sorted(view.regions, key=lambda r: (r.rid not in must,
                                                 -fuzz.token_set_ratio(goal.lower(), r.text.lower()[:400])))
    kept, used = set(), 0
    for r in ranked:
        cost = estimate_tokens(_region_state(view, r, read_more))
        if r.rid in must or used + cost <= budget_tokens:
            kept.add(r.rid)
            used += cost
    shown = [_region_state(view, r, read_more) for r in view.regions if r.rid in kept]
    rest = [r for r in view.regions if r.rid not in kept]
    groups = []
    if rest:
        size = max(1, -(-len(rest) // 4))  # at most 4 groups, in page order
        for g in range(0, len(rest), size):
            chunk = rest[g:g + size]
            groups.append({"gid": f"g{len(groups)}", "kinds": sorted({r.kind for r in chunk}), "count": len(chunk),
                           "rids": [r.rid for r in chunk],
                           "preview": clean(" | ".join(r.text[:40] for r in chunk[:3]))})
    return shown, groups


def _region_state(view: PageView, r: Region, read_more: dict[str, tuple[int, str]]) -> dict:
    if r.rid in read_more:
        offset, chunk = read_more[r.rid]
        text, truncated = chunk, offset + len(chunk) < len(r.text)
    else:
        text, truncated = r.text[:REGION_TEXT_CAP], r.truncated
    d = {"rid": r.rid, "kind": r.kind, "text": text}
    if truncated:
        d["truncated"] = True
    if r.eids:
        d["elements"] = [f"{eid} {view.elements[eid].label}" + (f" ({view.elements[eid].state})"
                         if view.elements[eid].state else "") for eid in r.eids if eid in view.elements][:40]
    return d


def next_chunk(region: Region, offset: int, budget_chars: int) -> tuple[str, int | None]:
    """read_more: the next chunk after `offset` that fits `budget_chars`; returns (chunk, next_offset or None)."""
    chunk = region.text[offset:offset + budget_chars]
    nxt = offset + len(chunk)
    return chunk, (nxt if nxt < len(region.text) else None)
