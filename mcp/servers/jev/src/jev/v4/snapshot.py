"""One atomic page snapshot per step (plan v4 §4.1), same JS for both backends.

Every control gets a stable `data-jev` id, so both backends act on the selector `[data-jev="jN"]`.
Generic observation rules (no per-site code):
- standard HTML controls + all WAI-ARIA widget roles + contenteditable (as jev.browser);
- pointer-styled clickables: the outermost element with `cursor: pointer`, `onclick` or a positive tabindex that is
  not inside/around another control (custom buttons such as <span class=close>KAPAT</span>);
- proxy controls: a control whose centre is covered by a non-control inside its own small wrapper (opacity-0 native
  <select> under a styled prompt, <input> under its label span) is kept; a real overlay still hides it;
- a nameless control takes the short text of its wrapper (Amazon "Dismiss" / "Change Address");
- a blocking popup is a dialog (role/element) or any fixed/absolute layer that covers ≥ 90 % of the viewport at its
  centre and contains a control; then only its controls are offered.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from jev.browser import MAX_TEXT, SENSITIVE_HINTS, _DESCRIBE_JS, Element

TEXT_CAP = 4000        # visible text shown per step; the rest is reachable with READ_MORE (same screen)
TEXT_FULL_CAP = 24000  # visible text kept for READ_MORE and answers

SNAPSHOT_JS = r"""
() => {
  const describe = """ + _DESCRIBE_JS.strip() + r""";
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const W = window.__jev ||= {ids: new WeakMap(), next: 1,
                              doc: Date.now().toString(36) + Math.random().toString(36).slice(2, 8)};
  const jid = e => { if (!W.ids.has(e)) W.ids.set(e, 'j' + (W.next++)); const id = W.ids.get(e);
                     if (e.getAttribute('data-jev') !== id) e.setAttribute('data-jev', id); return id; };
  const SEL = 'a[href], button, input:not([type=hidden]), textarea, select, summary, ' +
              '[contenteditable=""], [contenteditable=true], ' +
              '[role=button], [role=link], [role=tab], [role=menuitem], [role=menuitemcheckbox], ' +
              '[role=menuitemradio], [role=searchbox], [role=textbox], [role=checkbox], [role=radio], [role=switch], ' +
              '[role=option], [role=combobox], [role=slider], [role=spinbutton], [role=treeitem], [role=gridcell]';
  const box = e => e.getBoundingClientRect();
  const shown = e => { const r = box(e), st = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none'; };
  const all = (root, sel, out = []) => {
    for (const e of root.querySelectorAll(sel)) out.push(e);
    for (const h of root.querySelectorAll('*')) if (h.shadowRoot) all(h.shadowRoot, sel, out);
    return out;
  };
  const standard = new Set(all(document, SEL));
  // pointer-styled clickables (outermost pointer element, not inside or around a standard control)
  const custom = [];
  for (const e of all(document, 'body *')) {
    if (standard.has(e) || e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
    const tabbable = e.hasAttribute('tabindex') && e.tabIndex >= 0;
    const st = getComputedStyle(e);
    if (!(st.cursor === 'pointer' || e.hasAttribute('onclick') || tabbable)) continue;
    const p = e.parentElement;
    if (p && getComputedStyle(p).cursor === 'pointer' && !e.hasAttribute('onclick')) continue;
    if (e.closest(SEL) || e.querySelector(SEL)) continue;
    const t = clean(e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '');
    if (!t || t.length > 80) continue;
    custom.push(e);
  }
  // blocking popup: a dialog, or a fixed/absolute layer covering >= 90% of the viewport at its centre
  const hitC = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  let modal = null;
  for (const d of document.querySelectorAll('dialog[open], [role=dialog], [role=alertdialog], [aria-modal=true]'))
    if (shown(d) && hitC && d.contains(hitC) && d.querySelector(SEL + ', [style*=cursor]')) modal = d;
  if (!modal && hitC) for (let e = hitC; e && e !== document.body && e !== document.documentElement; e = e.parentElement) {
    const st = getComputedStyle(e), r = box(e);
    if ((st.position === 'fixed' || st.position === 'absolute') && r.width * r.height >= 0.9 * innerWidth * innerHeight) {
      const inside = [...standard, ...custom].filter(c => e.contains(c) && shown(c)).length;
      const outside = [...standard, ...custom].filter(c => !e.contains(c) && shown(c)).length;
      if (inside > 0 && outside > 0) modal = e;
    }
  }
  const wrapperOf = e => { let w = e.parentElement;
    for (let i = 0; w && i < 3; i++, w = w.parentElement) if (clean(w.innerText).length <= 80 && w.parentElement) return w;
    return e.parentElement; };
  // 'clear' | 'proxy' (covered only by a non-control inside its own small wrapper: its label/prompt/thumb) | 'covered'
  const cover = e => {
    const r = box(e), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    if (cx < 0 || cy < 0 || cx >= innerWidth || cy >= innerHeight) return 'clear';   // off-screen: not covered
    const hit = e.getRootNode().elementFromPoint(cx, cy);
    if (!hit || hit === e || e.contains(hit) || hit.contains(e)) return 'clear';
    const w = wrapperOf(e);
    if (w && w.contains(hit) && !standard.has(hit) && !hit.closest(SEL)) return 'proxy';
    return 'covered';
  };
  const out = [];
  const add = (e, extra) => out.push({...extra});
  const inView = r => r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
  const cands = [...standard, ...custom].filter(e => !modal || modal.contains(e));
  for (const e of cands) {
    if (!shown(e) || e.disabled || e.getAttribute('aria-hidden') === 'true' || e.closest('[aria-hidden=true],[inert]')) continue;
    // every control, sliders and selects included, is hidden by a real overlay; only its own wrapper may cover it
    const cv = cover(e);
    if (cv === 'covered') continue;
    // a grid cell that wraps a real control (calendar day button) is offered once, as that control
    if (e.getAttribute('role') === 'gridcell' && e.querySelector(SEL)) continue;
    let d;
    if (standard.has(e)) d = describe(e);
    else d = {role: 'button', tag: e.tagName.toLowerCase(), type: '', state: '', hint: '', context: '', details: '',
              text: clean(e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').slice(0, 80)};
    if (!d.text && ['button', 'link', 'menuitem', 'tab', 'option'].includes(d.role)) {
      const w = wrapperOf(e); const t = w ? clean(w.innerText) : '';
      if (t && t.length <= 60) d.text = t;
    }
    // grid cells (calendars, tables): the group label (e.g. the month) and a date-like attribute become the context,
    // so "20" in October is not "20" in September
    const cell = e.closest('[role=gridcell], td, [role=cell]');
    if (cell) {
      let iso = '';
      for (const x of [e, cell]) for (const at of x.attributes) if (/^\d{4}-\d{2}-\d{2}/.test(at.value)) iso = at.value.slice(0, 10);
      let grp = '';
      for (let a = cell.parentElement, i = 0; a && i < 6; a = a.parentElement, i++) {
        const lab = clean(a.getAttribute('aria-label') || '') || clean((a.innerText || '').split('\n')[0]);
        if (/[A-Za-zÀ-ÿçğıöşüÇĞİÖŞÜ]{3,}/.test(lab) && lab.length <= 40) { grp = lab; break; }
      }
      const ctx = [grp, iso].filter(Boolean).join(' ');
      if (ctx) { d.context = ctx.slice(0, 60); d.details = ''; }
    }
    // current value of a non-sensitive text/date field, so Jev sees what the form holds (redacted before use)
    if (['textbox', 'searchbox', 'combobox', 'spinbutton'].includes(d.role) && ['input', 'textarea'].includes(d.tag)) {
      const hay = ((e.getAttribute('autocomplete') || '') + ' ' + (e.name || '') + ' ' + d.text + ' ' + d.hint).toLowerCase();
      const sensitive = ['password', 'email', 'tel', 'file', 'hidden'].includes(e.type) ||
        /(pass|parola|şifre|card|kart|cvv|cvc|iban|e-?mail|e-?posta|phone|telefon|one-time|otp|cc-)/.test(hay);
      const v = clean(e.value || '');
      if (!sensitive) d.state = [d.state, v ? 'value ' + v.slice(0, 60) : 'empty'].filter(Boolean).join(', ').slice(0, 90);
    }
    // result cards: the full accessible name and the card's text (prices, times, stops) for code-side comparison
    if (['link', 'button'].includes(d.role)) {
      const full = clean(e.getAttribute('aria-label') || '');
      if (full.length > (d.text || '').length) d.full = full.slice(0, 400);
      const card = e.closest('li, [role=listitem], article, tr, [role=row]');
      if (card) d.card = clean(card.innerText).slice(0, 400);
    }
    const r = box(e);
    const id = jid(e);
    out.push({jid: id, ...d, in_view: inView(r), top: Math.round(r.top + scrollY), custom: !standard.has(e),
              proxy: cv === 'proxy'});
    if (e.tagName === 'SELECT')
      for (const [oi, o] of [...e.options].entries()) if (!o.disabled && !o.hidden)
        out.push({jid: id, oi, role: 'option', tag: 'option', type: 'select-option', text: clean(o.label || o.text).slice(0, 80),
                  hint: o.value, context: d.text, details: '', state: o.selected ? 'selected' : '', in_view: inView(r),
                  top: Math.round(r.top + scrollY), custom: false});
  }
  // scroll containers: the page plus visible inner panels that scroll
  const containers = [{jid: 'page', label: 'page', y: Math.round(scrollY), h: innerHeight,
                       H: document.documentElement.scrollHeight}];
  for (const e of all(document, 'body *')) {
    const st = getComputedStyle(e);
    if (!/(auto|scroll)/.test(st.overflowY) || e.scrollHeight <= e.clientHeight + 40 || e.clientHeight < 150) continue;
    if (!shown(e) || !inView(box(e)) || (modal && !modal.contains(e))) continue;
    const lab = clean(e.getAttribute('aria-label') || (e.querySelector('h1,h2,h3,h4,legend') || {}).innerText || '').slice(0, 40);
    containers.push({jid: jid(e), label: lab || 'panel', y: Math.round(e.scrollTop), h: e.clientHeight, H: e.scrollHeight});
    if (containers.length > 8) break;
  }
  // visible text of the viewport (inside the popup if one blocks the page)
  const words = [], walker = document.createTreeWalker(modal || document.body, NodeFilter.SHOW_TEXT), range = document.createRange();
  let n, len = 0;
  while ((n = walker.nextNode()) && len < """ + str(TEXT_FULL_CAP) + r""") {
    const v = clean(n.textContent), p = n.parentElement;
    if (!v || !p || p.closest('script,style,noscript,template') || !shown(p)) continue;
    range.selectNodeContents(n); const r = range.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && inView(r)) { words.push(v); len += v.length + 1; }
  }
  const frames = [...document.querySelectorAll('iframe')].filter(f => shown(f) && box(f).width * box(f).height > 20000).length;
  const canvas = [...document.querySelectorAll('canvas')].some(c => shown(c) && box(c).width * box(c).height > 0.2 * innerWidth * innerHeight);
  return JSON.stringify({url: location.href, title: document.title, controls: out, containers, text: words.join('\n'),
                         popup: !!modal, frames, canvas, fp: FP_EXPR_HERE, doc: W.doc});
}
"""

FP_EXPR = ("location.href + '|' + document.title + '|' + (document.body ? document.body.innerText.length : 0) + '|' + "
           "document.querySelectorAll('*').length + '|' + Math.round(scrollY) + '|' + "
           "((document.activeElement && document.activeElement.value) || '').length")
FINGERPRINT_JS = "() => " + FP_EXPR
SNAPSHOT_JS = SNAPSHOT_JS.replace("FP_EXPR_HERE", FP_EXPR)


@dataclass
class Control:
    jid: str
    role: str
    tag: str
    type: str
    text: str
    hint: str = ""
    context: str = ""
    details: str = ""
    state: str = ""
    in_view: bool = True
    top: int = 0
    custom: bool = False
    proxy: bool = False   # covered by its own label/prompt: clicked at its centre (decided before acting)
    oi: int = -1          # index of a native <select> option (its id never contains the option value)
    full: str = ""        # untruncated accessible name (links/buttons), e.g. a result's price sentence
    card: str = ""        # text of the list item / row / article the control is in

    @property
    def cid(self) -> str:
        """Unique id of this choice: the jid, plus the option value for native <select> options."""
        return f"{self.jid}:o{self.oi}" if self.type == "select-option" else self.jid

    @property
    def selector(self) -> str:
        return f'[data-jev="{self.jid}"]'

    def element(self) -> Element:
        """As a jev.browser.Element (handle = selector) to reuse the widget predicates."""
        return Element(id=self.cid, role=self.role, tag=self.tag, type=self.type, text=self.text, hint=self.hint,
                       handle=self.selector, context=self.context, details=self.details, state=self.state)

    @property
    def label(self) -> str:
        return self.element().label

    def line(self) -> str:
        s = f"{self.cid} {self.label}"
        if self.state:
            s += f" ({self.state})"
        if self.details and self.role in ("link", "button", "option"):
            s += f" — {self.details[:100]}"
        return s

    @property
    def sensitive(self) -> bool:
        hay = f"{self.text} {self.hint} {self.context}".lower()
        return self.type in ("password", "email", "tel", "file") or any(w in hay for w in SENSITIVE_HINTS) or \
            bool(re.search(r"\b(e-?mail|e-?posta|phone|telefon|cvv|cvc|iban)\b", hay))


@dataclass
class Snapshot:
    url: str
    title: str
    controls: list[Control]
    containers: list[dict]
    text: str
    popup: bool = False
    frames: int = 0
    canvas: bool = False
    flags: list[str] = field(default_factory=list)
    fp: str = ""  # cheap page fingerprint (same formula as FINGERPRINT_JS) at snapshot time
    real_url: str = ""  # unredacted URL, local only (page identity, url checks); `url` is the display form
    doc: str = ""  # identity of the document (new after navigation/reload; kept by history.replaceState)

    def by_cid(self, cid: str) -> Control | None:
        return next((c for c in self.controls if c.cid == cid), None)

    def fingerprint(self) -> str:
        key = self.url + "|" + self.text[:3000] + "|" + "|".join(f"{c.cid}{c.state}" for c in self.controls if c.in_view)
        return hashlib.sha1(key.encode()).hexdigest()[:12]


def parse(raw: str | dict) -> Snapshot:
    d = json.loads(raw) if isinstance(raw, str) else raw
    ctls = [Control(**{k: c.get(k, "") for k in ("jid", "role", "tag", "type", "text", "hint", "context", "details",
                                                    "state")},
                    in_view=bool(c.get("in_view")), top=int(c.get("top") or 0), custom=bool(c.get("custom")),
                    proxy=bool(c.get("proxy")), full=c.get("full", "") or "", card=c.get("card", "") or "",
                    oi=int(c["oi"]) if c.get("oi") is not None else -1)
            for c in d["controls"]]
    for c in ctls:
        c.text = c.text[:MAX_TEXT]
    flags = (["iframe"] if d.get("frames") else []) + (["canvas"] if d.get("canvas") else [])
    import hashlib
    fp_raw = str(d.get("fp", ""))
    fp_hash = hashlib.sha1(fp_raw.encode()).hexdigest()[:16] if fp_raw else ""  # same as fingerprint()
    return Snapshot(d["url"], d["title"], ctls, d["containers"], d["text"][:TEXT_FULL_CAP], bool(d.get("popup")),
                    int(d.get("frames") or 0), bool(d.get("canvas")), flags, fp=fp_hash, real_url=d["url"],
                    doc=str(d.get("doc", "")))


async def take(browser) -> Snapshot:
    """One evaluate on either backend."""
    if hasattr(browser, "_call"):  # ext: Playwright MCP
        from jev.ext_browser import parse_evaluate
        txt = parse_evaluate(await browser._call("browser_evaluate", {"function": SNAPSHOT_JS}))
        raw = json.loads(txt) if txt.strip().startswith('"') else txt
        return parse(raw)
    await browser.start()
    return parse(await browser.page.evaluate(SNAPSHOT_JS))


async def fingerprint(browser) -> str:
    """Hash of the cheap page fingerprint (it contains the URL, which may hold personal data)."""
    import hashlib
    if hasattr(browser, "_call"):
        from jev.ext_browser import parse_evaluate
        raw = parse_evaluate(await browser._call("browser_evaluate", {"function": FINGERPRINT_JS}))
    else:
        raw = await browser.page.evaluate(FINGERPRINT_JS)
    return hashlib.sha1((raw or "").encode()).hexdigest()[:16] if raw else ""
