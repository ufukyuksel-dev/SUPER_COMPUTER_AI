"""Chrome control: launch, read clickable elements as text, click/fill by ElementHandle."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import BrowserContext, ElementHandle, Page, Playwright, async_playwright

log = logging.getLogger("jev.browser")

from jev import paths
MAX_TEXT = 80
SENSITIVE_TYPES = ("password", "email", "tel", "number")
SENSITIVE_HINTS = ("cc-", "card", "kart", "password", "şifre", "parola", "current-password", "new-password", "one-time-code")

# Shared by both backends: which dialogs really block the page (see _FIND_JS and ExtensionBrowser.read_elements).
# A dialog blocks only if it has something to click and the viewport centre is inside it or under a full-screen
# backdrop. A backdrop has nothing clickable outside the dialog, so a full-screen app shell does not count.
_BLOCKING_JS = """
const DIALOG_SEL = 'dialog[open], [role=dialog], [role=alertdialog]';
const blocking = (d, shown, sel) => {
  if (!shown(d) || !d.querySelector(sel)) return false;
  const hit = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  if (!hit) return false;
  if (d.contains(hit)) return true;
  for (let e = hit; e && e !== document.body; e = e.parentElement) {
    const st = getComputedStyle(e), r = e.getBoundingClientRect();
    if ((st.position === 'fixed' || st.position === 'absolute') &&
        r.width * r.height >= 0.9 * innerWidth * innerHeight &&
        ![...e.querySelectorAll(sel)].some(x => !d.contains(x))) return true;
  }
  return false;
};
"""

# Extension backend: is the page blocked by a popup? (same rule, run via Playwright MCP browser_evaluate)
BLOCKED_JS = """
() => {""" + _BLOCKING_JS + """
  const sel = 'a[href], button, input:not([type=hidden]), textarea, select, summary, [role=button], [role=link], ' +
              '[role=tab], [role=menuitem], [role=checkbox], [role=radio], [role=switch], [role=option]';
  const shown = el => {
    const r = el.getBoundingClientRect(), st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  return [...document.querySelectorAll(DIALOG_SEL)].some(d => blocking(d, shown, sel));
}
"""

# Returns the visible, enabled, not-covered interactive elements of the document, in DOM order.
# If a blocking popup is open, only the elements inside the topmost one are returned (the rest is blocked anyway).
_FIND_JS = """
() => {""" + _BLOCKING_JS + """
  // every standard HTML control and WAI-ARIA widget role (see design note plan-universal-widgets.md (private))
  const sel = 'a[href], button, input:not([type=hidden]), textarea, select, summary, ' +
              '[contenteditable=""], [contenteditable=true], ' +
              '[role=button], [role=link], [role=tab], [role=menuitem], [role=menuitemcheckbox], ' +
              '[role=menuitemradio], [role=searchbox], [role=textbox], [role=checkbox], [role=radio], [role=switch], ' +
              '[role=option], [role=combobox], [role=slider], [role=spinbutton], [role=treeitem], [role=gridcell]';
  const shown = el => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  // Open shadow roots are searched too; elementFromPoint must be asked on the element's own root.
  const all = (root, out = []) => {
    for (const el of root.querySelectorAll(sel)) out.push(el);
    for (const host of root.querySelectorAll('*')) if (host.shadowRoot) all(host.shadowRoot, out);
    return out;
  };
  // Toasters, banners and empty/hidden dialogs do not scope the page.
  const modals = [...document.querySelectorAll(DIALOG_SEL)].filter(d => blocking(d, shown, sel));
  const root = modals.length ? modals[modals.length - 1] : document;
  const out = [];
  for (const el of all(root)) {
    if (!shown(el)) continue;
    if (el.disabled || el.getAttribute('aria-hidden') === 'true') continue;
    // Skip elements covered by an overlay: the element at their centre must be the element itself (or inside it).
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    // Sliders are often invisible range inputs under a custom thumb: keep them even when "covered"
    const isSlider = el.type === 'range' || el.getAttribute('role') === 'slider';
    if (!isSlider && cx >= 0 && cy >= 0 && cx < innerWidth && cy < innerHeight) {
      const hit = el.getRootNode().elementFromPoint(cx, cy);
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) continue;
    }
    out.push(el);
  }
  return {elements: out, popup: modals.length > 0};
}
"""

_COVERED_JS = """
(el) => {
  const r = el.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  if (cx < 0 || cy < 0 || cx >= innerWidth || cy >= innerHeight) return false;
  const hit = el.getRootNode().elementFromPoint(cx, cy);
  return !!hit && hit !== el && !el.contains(hit) && !hit.contains(el);
}
"""

# Describes one element; used both when reading and when re-checking before an action.
_DESCRIBE_JS = """
(el) => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute('type') || '').toLowerCase();
  let role = el.getAttribute('role') || '';
  if (!role) {
    if (tag === 'a') role = 'link';
    else if (tag === 'button' || (tag === 'input' && ['submit', 'button', 'reset'].includes(type))) role = 'button';
    else if (tag === 'input' && ['checkbox', 'radio'].includes(type)) role = type;
    else if (tag === 'input' && type === 'range') role = 'slider';
    else if (tag === 'input' && type === 'number') role = 'spinbutton';
    else if (tag === 'input' && type === 'file') role = 'file';
    else if (tag === 'input' && type === 'search') role = 'searchbox';
    else if (el.isContentEditable && tag !== 'input' && tag !== 'textarea') role = 'textbox';
    else if (tag === 'input' || tag === 'textarea') role = 'textbox';
    else if (tag === 'select') role = 'combobox';
    else role = tag;
  }
  let name = el.getAttribute('aria-label') || '';
  const lb = el.getAttribute('aria-labelledby');
  if (!name && lb) name = lb.split(/\\s+/).map(id => document.getElementById(id)?.innerText || '').join(' ');
  // <label for=...> and a wrapping <label>; never the field's own value.
  if (!name && el.labels && el.labels.length) name = [...el.labels].map(l => l.innerText).join(' ');
  if (!name && tag !== 'input' && tag !== 'textarea' && tag !== 'select') name = el.innerText;
  // Icon-only buttons/links: the icon's own accessible text.
  if (!name) { const ic = el.querySelector('svg title, img[alt]'); if (ic) name = ic.getAttribute('alt') || ic.textContent; }
  if (!name) name = el.getAttribute('title') || el.getAttribute('alt') || el.getAttribute('placeholder') || '';
  // Only button-like inputs show their value as a label; never read what the user typed into a field.
  if (!name && tag === 'input' && ['submit', 'button', 'reset'].includes(type)) name = el.value || '';
  if (!name && (tag === 'input' || tag === 'button')) name = el.getAttribute('name') || '';
  name = clean(name);
  // Row context, so identical buttons ("Edit") in a table row or list item can be told apart.
  let context = '';
  const row = el.closest('tr, [role=row], li');
  if (row) {
    // The row's first link (e.g. the campaign name), else its first non-empty cell / item text that is not `el`.
    const cand = [...row.querySelectorAll('a[href]'),
                  ...row.querySelectorAll('td, th, [role=cell], [role=gridcell], [role=rowheader]'),
                  ...(row.tagName === 'LI' ? [...row.children] : [])];
    const pick = cand.find(c => c !== el && !c.contains(el) && !el.contains(c) && clean(c.innerText));
    if (pick) context = clean(pick.innerText);
  }
  if (context === name) context = '';
  // Card details (price, stock, ...): text of the nearest ancestor that says more than the element itself.
  let details = '';
  if (['link', 'button', 'option'].includes(role)) {
    for (let a = el.parentElement, i = 0; a && a !== document.body && i < 8; a = a.parentElement, i++) {
      const t = clean(a.innerText);
      if (t.length > 400) break;
      if (t.length > name.length + 15) { details = clean(t.replace(name, ' ')); break; }
    }
  }
  // widget state shown to Jev (never what the user typed into a text field)
  const st = [];
  if (el.checked || el.getAttribute('aria-checked') === 'true' || el.getAttribute('aria-pressed') === 'true') st.push('checked');
  if (['checkbox', 'radio', 'switch'].includes(role) && !st.length) st.push('unchecked');
  if (el.getAttribute('aria-selected') === 'true') st.push('selected');
  if (el.getAttribute('aria-expanded') === 'true') st.push('expanded');
  if (el.getAttribute('aria-expanded') === 'false' || el.getAttribute('aria-haspopup')) st.push('has popup');
  if (role === 'slider' || role === 'spinbutton') st.push('value ' + (el.getAttribute('aria-valuetext') || el.getAttribute('aria-valuenow') || el.value || ''));
  if (tag === 'select') st.push('selected ' + clean((el.selectedOptions[0] || {}).text || ''));
  return {
    role, tag, type,
    state: st.join(', ').slice(0, 60),
    text: name.slice(0, %d),
    hint: clean([el.getAttribute('name'), el.getAttribute('placeholder'), el.getAttribute('autocomplete')].join(' ')),
    context: context.slice(0, 60),
    details: details.slice(0, 200),
  };
}
""" % MAX_TEXT


# Current shown value of a slider / spinbutton (what a person reads next to it)
# aria-valuetext if the site sets it; otherwise the price/number text shown next to the slider (e.g. Amazon shows
# "$42 – $670+" beside two range inputs whose raw values are step indexes): last text for the upper/max slider,
# first for the lower/min one; raw value as the last resort.
WIDGET_VALUE_JS = """e => {
  const t = e.getAttribute('aria-valuetext');
  if (t) return t;
  const isSlider = e.getAttribute('role') === 'slider' || e.type === 'range';
  if (isSlider) {
    const re = /(?:[$€£₺]\s?\d[\d.,]*\+?)|(?:\d[\d.,]*\+?\s?(?:TL|€|USD|EUR))/g;
    for (let a = e.parentElement, i = 0; a && i < 5; a = a.parentElement, i++) {
      const found = (a.innerText || '').match(re);
      if (found && found.length) {
        const sliders = [...a.querySelectorAll('input[type=range],[role=slider]')];
        const upper = sliders.length > 1 && sliders.indexOf(e) === sliders.length - 1;
        return upper ? found[found.length - 1] : found[0];
      }
    }
  }
  return e.getAttribute('aria-valuenow') || e.value || '';
}"""

# Options of a native <select>: role "option", handle = the <select>, hint = option value, context = select name.
SELECT_OPTION = "select-option"
_OPTIONS_JS = """
(s) => [...s.options].filter(o => !o.disabled && !o.hidden)
  .map(o => ({text: (o.label || o.text || '').replace(/\\s+/g, ' ').trim().slice(0, %d), value: o.value}))
""" % MAX_TEXT
_HAS_OPTION_JS = "(s, v) => s.isConnected && [...s.options].some(o => o.value === v && !o.disabled)"


@dataclass
class Element:
    id: str
    role: str
    tag: str
    type: str
    text: str
    hint: str
    handle: ElementHandle = field(repr=False)
    context: str = ""  # e.g. the table row / list item the element is in; shown in `label`, not part of `text`
    details: str = ""  # short text of the element's card (price, stock, ...); given to Jev, not part of `label`
    state: str = ""    # checked / selected / slider value / expanded — shown to Jev, not part of identity

    @property
    def label(self) -> str:
        base = f"{self.role}: {self.text}" if self.text else self.role
        return f"{base} (row: {self.context})" if self.context else base

    def is_text_field(self) -> bool:
        """A field Jev may *type* into (free text)."""
        if self.type in ("submit", "button", "reset", "checkbox", "radio", "range", "file", "image") or \
                self.role in ("slider", "spinbutton", "file", "combobox") and self.tag == "select":
            return False
        if self.is_value_field():
            return False
        return self.tag in ("input", "textarea") or self.role in ("searchbox", "textbox")

    def is_value_field(self) -> bool:
        """A field that takes one exact value: slider/range, number/spinbutton, date/time/colour inputs."""
        return self.role in ("slider", "spinbutton") or self.type in (
            "range", "number", "date", "time", "month", "week", "datetime-local", "color")

    def is_search_field(self) -> bool:
        # Sensitive signals win over any search role/type.
        if self.type in SENSITIVE_TYPES:
            return False
        haystack = f"{self.text} {self.hint}".lower()
        if any(w in haystack for w in SENSITIVE_HINTS):
            return False
        if self.role == "searchbox" or self.type == "search":
            return True
        if self.tag not in ("input", "textarea"):
            return False
        return any(w in haystack for w in ("search", "ara", "query"))


def profile_dir(profile: str) -> Path:
    return paths.ensure_dir(paths.state_dir() / f"chrome-profile-{profile}")


class Browser:
    def __init__(self, profile: str = "cli", headless: bool = False, channel: str | None = "chrome"):
        self.profile = profile
        self.headless = headless
        self.channel = channel
        self._pw: Playwright | None = None
        self._ctx: BrowserContext | None = None
        self.page: Page | None = None
        self.popup_open = False
        # Native alert/confirm/prompt seen since the last check; they are dismissed, never accepted.
        self.pending_dialog: str | None = None

    async def start(self) -> None:
        if self._ctx:
            return
        self._pw = await async_playwright().start()
        user_dir = profile_dir(self.profile)
        user_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = await self._pw.chromium.launch_persistent_context(
            str(user_dir), channel=self.channel, headless=self.headless, no_viewport=not self.headless,
        )
        self._ctx.on("page", self._on_new_page)
        self.page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        self._watch_dialogs(self.page)
        log.info("chrome started (profile=%s, headless=%s)", user_dir, self.headless)

    def _on_new_page(self, page: Page) -> None:
        # Links with target=_blank open a new tab; follow it.
        self.page = page
        self._watch_dialogs(page)

    def _watch_dialogs(self, page: Page) -> None:
        async def on_dialog(dialog) -> None:
            self.pending_dialog = f"{dialog.type}: {dialog.message}"[:200]
            log.info("native dialog dismissed: %s", self.pending_dialog)
            await dialog.dismiss()

        page.on("dialog", on_dialog)

    def take_dialog(self) -> str | None:
        msg, self.pending_dialog = self.pending_dialog, None
        return msg

    async def close(self) -> None:
        if self._ctx:
            await self._ctx.close()
        if self._pw:
            await self._pw.stop()
        self._ctx = self._pw = self.page = None

    async def open(self, url: str) -> None:
        await self.start()
        await self.page.goto(url, wait_until="domcontentloaded")
        await self._settle()

    async def info(self) -> dict:
        return {"url": self.page.url, "title": await self.page.title()}

    async def read_text(self) -> str:
        """Visible text of the page (read-only)."""
        return await self.page.evaluate("() => document.body ? document.body.innerText : ''")

    async def read_elements(self) -> list[Element]:
        # The page may still be navigating (redirects, client-side routing); wait and read again.
        # Client-rendered pages (e.g. TikTok) may show nothing right after DOMContentLoaded; wait a bit.
        elements: list[Element] = []
        for attempt in range(6):
            try:
                elements = await self._read_elements()
            except PlaywrightError as e:
                if "context was destroyed" not in str(e) and "navigat" not in str(e) or attempt == 5:
                    raise
                log.info("page navigated while reading; retrying")
                await self._settle()
                continue
            if elements:
                return elements
            await asyncio.sleep(1.0)
        return elements

    async def _read_elements(self) -> list[Element]:
        elements: list[Element] = []
        self.popup_open = False
        # Main frame first, then child frames (iframes); a modal in the main frame blocks the frames behind it.
        for frame in self.page.frames:
            if frame is not self.page.main_frame and (self.popup_open or frame.is_detached()):
                continue
            try:
                found = await frame.evaluate_handle(_FIND_JS)
            except PlaywrightError:
                if frame is self.page.main_frame:
                    raise
                log.info("frame %s not readable; skipped", frame.url)
                continue
            if frame is self.page.main_frame:
                self.popup_open = await (await found.get_property("popup")).json_value()
            arr = await found.get_property("elements")
            for jsh in (await arr.get_properties()).values():
                handle = jsh.as_element()
                if handle is None:
                    continue
                d = await handle.evaluate(_DESCRIBE_JS)
                elements.append(Element(id=f"e{len(elements)}", handle=handle, **d))
                if d["tag"] == "select":
                    # Native options have no layout box, so they are never found above; offer each one as an
                    # element Jev can pick. Clicking it selects that option (see `click`).
                    for o in await handle.evaluate(_OPTIONS_JS):
                        elements.append(Element(id=f"e{len(elements)}", role="option", tag="option",
                                                type=SELECT_OPTION, text=o["text"], hint=o["value"],
                                                handle=handle, context=d["text"]))
            await arr.dispose()
            await found.dispose()
        return elements

    async def still_same(self, el: Element) -> bool:
        """The handle is still attached, visible, and describes the same as when read."""
        if el.type == SELECT_OPTION:
            try:
                return await el.handle.evaluate(_HAS_OPTION_JS, el.hint) and await el.handle.is_visible()
            except Exception:
                return False
        try:
            if not await el.handle.evaluate("e => e.isConnected") or not await el.handle.is_visible():
                return False
            d = await el.handle.evaluate(_DESCRIBE_JS)
        except Exception:
            return False
        # type/hint too: a field must not turn into a password/card field between decision and fill.
        # context too: "Edit" must still be in the same row (e.g. the list re-sorted under the chosen button).
        if not all(d[k] == getattr(el, k) for k in ("text", "role", "type", "hint", "context")):
            return False
        # Something (e.g. a popup that opened meanwhile) must not cover it.
        return not await el.handle.evaluate(_COVERED_JS)

    async def click(self, el: Element) -> None:
        if el.type == SELECT_OPTION:
            await el.handle.select_option(value=el.hint, timeout=5000)
            await self._settle()
            return
        await el.handle.click(timeout=5000)
        await self._settle()

    async def hover(self, el: Element) -> None:
        await el.handle.hover(timeout=5000)
        await asyncio.sleep(0.5)

    async def type_text(self, el: Element, text: str, submit: bool = False) -> None:
        """Type into any text field (not only search fields)."""
        await el.handle.fill(text, timeout=5000)
        if submit:
            await el.handle.press("Enter")
        await self._settle()

    async def press(self, key: str, el: Element | None = None) -> None:
        if el is not None:
            await el.handle.press(key)
        else:
            await self.page.keyboard.press(key)
        await asyncio.sleep(0.25)

    async def focus(self, el: Element) -> None:
        await el.handle.focus()

    async def widget_value(self, el: Element) -> str:
        return await el.handle.evaluate(WIDGET_VALUE_JS)

    async def scroll(self) -> None:
        await self.page.evaluate("() => window.scrollBy(0, Math.round(innerHeight * 0.9))")
        await asyncio.sleep(0.8)

    async def back(self) -> None:
        await self.page.go_back(wait_until="domcontentloaded")
        await self._settle()

    async def element_state(self, el: Element) -> dict:
        """Evidence for element checks: checked / value / selected option text."""
        try:
            return await el.handle.evaluate("""e => ({checked: !!e.checked || e.getAttribute('aria-checked') === 'true',
              value: e.tagName === 'SELECT' ? (e.selectedOptions[0] || {}).text || '' : (e.value ?? ''),
              expanded: e.getAttribute('aria-expanded') === 'true'})""")
        except Exception:
            return {}

    async def fill_and_submit(self, el: Element, text: str) -> None:
        await el.handle.fill(text, timeout=5000)
        await el.handle.press("Enter")
        await self._settle()

    async def _settle(self) -> None:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        await asyncio.sleep(0.6)
