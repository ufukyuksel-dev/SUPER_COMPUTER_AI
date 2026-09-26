"""Actions on `[data-jev=...]` selectors for both backends, with per-operation readiness (plan v4 §4.5)."""

from __future__ import annotations

import asyncio
import json
import time

from jev.browser import WIDGET_VALUE_JS
from jev.v4.snapshot import Control, fingerprint

NAV_CAP, SAME_PAGE_CAP, COMBO_CAP, LOADING_CAP = 8.0, 1.5, 0.8, 8.0
# Visible, task-relevant loading evidence (review run 4). Ignored: hidden or screen-reader-only elements (tiny boxes),
# anything in header/nav/footer, determinate progress bars, small busy widgets, and long text that merely mentions
# loading.
LOADING_JS = r"""() => {
  const vis = e => { if (!e || !e.checkVisibility || !e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
                       return false;
                     const r = e.getBoundingClientRect();
                     return r.width >= 16 && r.height >= 8 && r.bottom > 0 && r.top < innerHeight; };
  const chrome = e => e.closest('header, nav, footer, [role=banner], [role=navigation], [role=contentinfo]');
  for (const e of document.querySelectorAll('[aria-busy=true]')) {
    const r = e.getBoundingClientRect();
    if (vis(e) && !chrome(e) && r.width * r.height >= 0.05 * innerWidth * innerHeight) return 'aria-busy region';
  }
  for (const e of document.querySelectorAll('[role=progressbar], progress')) {
    const indeterminate = e.tagName === 'PROGRESS' ? !e.hasAttribute('value') : !e.hasAttribute('aria-valuenow');
    const r = e.getBoundingClientRect();
    // a small spinner inside a control (a tab's "fetching price", a button) is that widget's own state, not the
    // page loading its results
    if (e.closest('button, a, [role=tab], [role=button], [role=option], [role=link]')) continue;
    if (r.width < 20 && r.height < 20) continue;
    if (indeterminate && vis(e) && !chrome(e)) return 'indeterminate progress indicator';
  }
  const re = /^(loading|loading results|fetching results|searching|please wait|updating results|yükleniyor|aranıyor|lütfen bekleyin)[\s.…]*$/i;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = (n.textContent || '').trim();
    if (!t || t.length > 40 || !re.test(t)) continue;
    const p = n.parentElement;
    if (p && vis(p) && !chrome(p) && !p.closest('script, style, template')) return 'status text: ' + t;
  }
  return '';
}"""
_OPTIONS_OPEN_JS = ("() => [...document.querySelectorAll('[role=option],[role=listbox] *,[role=menuitem]')]"
                    ".some(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })")


def ext_value(txt: str):
    """Typed value of a Playwright MCP `browser_evaluate` answer (the JSON in its `### Result` section)."""
    from jev.ext_browser import _RESULT
    body = m.group("body").strip() if (m := _RESULT.search(txt)) else txt.strip()
    try:
        return json.loads(body)
    except ValueError:
        return body


class Executor:
    def __init__(self, browser):
        self.b = browser
        self.ext = hasattr(browser, "_call")

    # ---- low level
    async def _eval(self, fn: str, sel: str | None = None):
        """Evaluate on either backend and return the JS value with its type (ext answers with text: a JS `false` must
        not come back as the truthy string "false")."""
        if self.ext:
            args = {"function": fn}
            if sel:
                args.update(element=sel, target=sel)
            return ext_value(await self.b._call("browser_evaluate", args))
        if sel:
            return await self.b.page.locator(sel).first.evaluate(fn)
        return await self.b.page.evaluate(fn)

    async def click(self, c: Control) -> None:
        if c.type == "select-option":
            if self.ext:
                await self.b._call("browser_select_option", {"element": c.context or "select", "target": c.selector,
                                                             "values": [c.hint]})
            else:
                await self.b.page.locator(c.selector).first.select_option(value=c.hint, timeout=5000)
            return
        # One click, chosen before acting: a proxy control (covered only by its own label/prompt, see snapshot) is
        # clicked at its centre / by DOM click; any error is raised to the caller and never retried (it may have
        # happened).
        if self.ext:
            before = await self.b._tab_list()
            if c.proxy:
                await self._eval("e => e.click()", c.selector)
            else:
                await self.b._call("browser_click", {"element": c.label, "target": c.selector})
            await self.b._follow_new_tab(before)
            return
        await self.b.page.locator(c.selector).first.click(timeout=5000, force=c.proxy)

    async def hover(self, c: Control) -> None:
        if self.ext:
            await self.b._call("browser_hover", {"element": c.label, "target": c.selector})
        else:
            await self.b.page.locator(c.selector).first.hover(timeout=5000)

    async def fill(self, c: Control, text: str, submit: bool) -> None:
        if self.ext:
            await self.b._call("browser_type", {"element": c.label, "target": c.selector, "text": text,
                                                "submit": submit})
            return
        loc = self.b.page.locator(c.selector).first
        if c.tag in ("input", "textarea"):
            await loc.fill(text, timeout=5000)
        else:  # contenteditable / custom textbox
            await loc.click(timeout=5000)
            await self.b.page.keyboard.press("ControlOrMeta+A")
            await self.b.page.keyboard.insert_text(text)
        if submit:
            await loc.press("Enter")

    async def press(self, key: str, c: Control | None = None) -> None:
        if self.ext:
            if c is not None:
                await self.focus(c)
            await self.b._call("browser_press_key", {"key": key})
        elif c is not None:
            await self.b.page.locator(c.selector).first.press(key)
        else:
            await self.b.page.keyboard.press(key)

    async def focus(self, c: Control) -> None:
        await self._eval("e => e.focus()", c.selector)

    async def field_value(self, c: Control) -> str:
        """The value a field holds now (read locally to check that the site kept what was typed; never stored)."""
        v = await self._eval("e => (e.value !== undefined ? e.value : (e.innerText || '')).toString()", c.selector)
        return str(v or "")

    async def widget_value(self, c: Control) -> str:
        return str(await self._eval(f"({WIDGET_VALUE_JS})", c.selector))

    async def scroll(self, container_jid: str, down: bool = True) -> None:
        sign = "" if down else "-"
        if container_jid == "page":
            await self._eval(f"() => window.scrollBy(0, {sign}Math.round(innerHeight * 0.85))")
        else:
            await self._eval(f"() => {{ const e = document.querySelector('[data-jev=\"{container_jid}\"]'); "
                             f"if (e) e.scrollBy(0, {sign}Math.round(e.clientHeight * 0.85)); }}")

    async def back(self) -> None:
        if self.ext:
            await self.b._call("browser_navigate_back", {})
        else:
            await self.b.page.go_back(wait_until="domcontentloaded")

    async def url(self) -> str:
        return (await self.b.info())["url"]

    async def loading(self) -> str:
        """Why the page is still loading ('' when it is not): visible, task-relevant loading evidence only."""
        try:
            return str(await self._eval(LOADING_JS) or "")
        except Exception:  # noqa: BLE001 - navigation in progress counts as loading
            return "navigating"

    async def wait_loading(self, cap: float = LOADING_CAP) -> tuple[bool, str, bool]:
        """Wait while the page shows a loading signal, at most `cap` seconds.
        Returns (cleared, last reason, waited at all)."""
        t0 = time.monotonic()
        why = await self.loading()
        waited = bool(why)
        while why:
            if time.monotonic() - t0 >= cap:
                return False, why, True
            await asyncio.sleep(0.1)
            why = await self.loading()
        return True, "", waited

    # ---- readiness (bounded). Returns (ready, fingerprint after); ready False = cap reached without a settled change
    # or a loading signal that did not clear (self.loading_timeout says which). A stable fingerprint never overrides
    # an active loading signal.
    async def ready_after(self, op: str, before_fp: str, before_url: str, combo: bool = False,
                          loading_cap: float = LOADING_CAP) -> tuple[bool, str]:
        self.loading_timeout = ""
        t0 = time.monotonic()
        if op == "TYPE" and combo:
            while time.monotonic() - t0 < COMBO_CAP:
                if await self._eval(_OPTIONS_OPEN_JS):
                    break
                await asyncio.sleep(0.05)
            return True, await fingerprint(self.b)  # no suggestion list: nothing to wait for
        last, stable, cap, ready, fp = None, 0, SAME_PAGE_CAP, False, None
        while True:
            try:
                url = await self.url()
                if url != before_url:
                    cap = NAV_CAP
                    if not self.ext:
                        await self.b.page.wait_for_load_state("domcontentloaded",
                                                              timeout=max(1, int((NAV_CAP - (time.monotonic() - t0)) * 1000)))
                fp = await fingerprint(self.b)
            except Exception:  # noqa: BLE001 - navigation in progress
                fp = None
            if fp is not None and fp != before_fp:
                stable = stable + 1 if fp == last else 0
                if stable >= 1:
                    ready = True
                    break
            last = fp
            if time.monotonic() - t0 > cap:
                ready = fp is not None and fp != before_fp
                break
            await asyncio.sleep(0.05)
        cleared, why, waited = await self.wait_loading(loading_cap)
        if not cleared:
            self.loading_timeout = why
            return False, await fingerprint(self.b)
        if waited:  # the page changed while loading: settle on the loaded state
            return True, await fingerprint(self.b)
        return ready, fp or ""
