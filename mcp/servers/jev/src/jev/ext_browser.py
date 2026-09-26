"""Browser backend that drives the user's own Chrome through the Playwright extension (@playwright/mcp --extension).

Same interface as `jev.browser.Browser`, so `jev.brain.run` works unchanged. Elements come from the Playwright MCP
accessibility snapshot; an element's handle is its snapshot `ref`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from types import SimpleNamespace

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from jev.browser import BLOCKED_JS, SELECT_OPTION, WIDGET_VALUE_JS, Element

log = logging.getLogger("jev.ext_browser")

PLAYWRIGHT_MCP = "@playwright/mcp@0.0.82"
_REFLESS_TARGETABLE = {"slider", "spinbutton", "textbox", "searchbox", "checkbox", "radio", "switch"}
ACTIONABLE_ROLES = {  # every WAI-ARIA widget role the snapshot can show (design note plan-universal-widgets.md (private))
    "link", "button", "tab", "menuitem", "menuitemcheckbox", "menuitemradio", "option", "checkbox", "radio",
    "switch", "textbox", "searchbox", "combobox", "spinbutton", "slider", "treeitem", "gridcell",
}
_LINE = re.compile(r'^\s*- (?P<role>[\w-]+)(?: "(?P<name>(?:[^"\\]|\\.)*)")?(?P<attrs>(?: \[[^\]]*\])*)(?::\s*(?P<tail>.*))?$')
_REF = re.compile(r"\[ref=([^\]]+)\]")
_MODAL_STATE = re.compile(r"^### Modal state\s*\n(?P<body>(?:- .*\n?)+)", re.M)
_URL = re.compile(r"^- Page URL: (.+)$", re.M)
_TITLE = re.compile(r"^- Page Title: (.*)$", re.M)
_RESULT = re.compile(r"^### Result\s*\n(?P<body>.*?)(?=^### |\Z)", re.M | re.S)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _modal_lines(lines: list[str]) -> list[str] | None:
    """Lines of the last (topmost) dialog subtree that has something to click, or None.

    Empty dialogs (e.g. Amazon keeps an empty `- dialog [ref=..]` in the page) are skipped.
    """
    starts = [i for i, ln in enumerate(lines) if re.match(r"^\s*- (dialog|alertdialog)\b", ln)]
    for i in reversed(starts):
        base = _indent(lines[i])
        end = i + 1
        while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > base):
            end += 1
        if any(_is_actionable(ln) for ln in lines[i + 1:end]):
            return lines[i:end]
    return None


def _is_actionable(line: str) -> bool:
    m = _LINE.match(line)
    return bool(m and _REF.search(m["attrs"] or "") and
                (m["role"] in ACTIONABLE_ROLES or "[cursor=pointer]" in (m["attrs"] or "")))


def parse_snapshot(text: str, blocked: bool | None = None) -> list[Element]:
    """Actionable elements (known roles, or anything marked cursor=pointer) with their refs.

    blocked: whether a popup really blocks the page (checked in the browser, see `BLOCKED_JS`). If true (or unknown,
    None), only the topmost non-empty dialog's elements are returned; if false, dialogs such as toasters do not hide
    the rest of the page.
    """
    lines = text.splitlines()
    if blocked is not False:
        lines = _modal_lines(lines) or lines
    parsed = [(i, _indent(ln), m) for i, ln in enumerate(lines) if (m := _LINE.match(ln))]
    words = [_line_text(m) for _, _, m in parsed]
    out: list[Element] = []
    # Table rows / list items: remember the first link name (else the first cell / text) so identical buttons
    # ("Edit") can be told apart. Each entry: [indent, link name, fallback name].
    rows: list[list] = []
    selects: list[tuple[int, str, str]] = []  # open combobox subtrees: (indent, ref, name)
    for k, (_, ind, m) in enumerate(parsed):
        while rows and ind <= rows[-1][0]:
            rows.pop()
        role = m["role"]
        name = (m["name"] or "").replace('\\"', '"')
        tail = (m["tail"] or "").strip().strip('"')
        if role in ("row", "listitem"):
            rows.append([ind, "", ""])
        elif rows:
            if role == "link" and name and not rows[-1][1]:
                rows[-1][1] = name
            elif not rows[-1][2] and ((role in ("cell", "gridcell", "rowheader") and name) or (role == "text" and tail)):
                rows[-1][2] = name or tail
        ref = _REF.search(m["attrs"] or "")
        while selects and ind <= selects[-1][0]:
            selects.pop()
        if role == "combobox" and ref:
            selects.append((ind, ref.group(1), name))
        if not ref and role in _REFLESS_TARGETABLE and name:
            # The snapshot gives no ref for some real controls (e.g. invisible range inputs under a custom slider
            # thumb). Target them by role + accessible name, a Playwright selector the MCP tools accept.
            sel = f'role={role}[name="{name.replace(chr(34), chr(92) + chr(34))}"]'
            typ = {"searchbox": "search", "slider": "range", "spinbutton": "number"}.get(role, "")
            out.append(Element(id=f"e{len(out)}", role=role, tag="input", type=typ, text=name[:80], hint="",
                               handle=sel, state=(f"value {tail}" if role in ("slider", "spinbutton") else "")[:60]))
            continue
        if not ref:
            if role == "option" and name and selects and "[disabled]" not in (m["attrs"] or ""):
                # Options of a native <select> have no ref; offer them, selected via the combobox's ref.
                out.append(Element(id=f"e{len(out)}", role="option", tag="option", type=SELECT_OPTION,
                                   text=name[:80], hint=name, handle=selects[-1][1], context=selects[-1][2][:60]))
            continue
        pointer = "[cursor=pointer]" in (m["attrs"] or "")
        if role not in ACTIONABLE_ROLES and not pointer:
            continue
        text_ = name or tail
        if not text_:
            # Icon-only link/button: use the first named descendant (e.g. `img "Profil"`).
            for _, cind, cm in parsed[k + 1:]:
                if cind <= ind:
                    break
                if cm["name"]:
                    text_ = cm["name"].replace('\\"', '"')
                    break
        text_ = text_[:80]
        context = ""
        if rows:
            context = rows[-1][1] or rows[-1][2]
            if context == text_:
                context = ""
        is_input = role in ("textbox", "searchbox", "combobox", "spinbutton", "slider")
        details = _card_details(parsed, words, k, text_) if role in ("link", "button", "option") else ""
        attrs = m["attrs"] or ""
        st = [w for w in ("checked", "selected", "expanded", "pressed") if f"[{w}]" in attrs or f"[{w}=true]" in attrs]
        if role in ("checkbox", "radio", "switch") and "checked" not in st:
            st.append("unchecked")
        if role in ("slider", "spinbutton") or (role == "combobox" and tail):
            st.append(("value " if role != "combobox" else "selected ") + tail)
        typ = {"searchbox": "search", "slider": "range", "spinbutton": "number"}.get(role, "")
        out.append(Element(id=f"e{len(out)}", role=role, tag="input" if is_input else role,
                           type=typ, text=text_, hint="", handle=ref.group(1),
                           context=context[:60], details=details, state=", ".join(st)[:60]))
    return out


def _line_text(m) -> str:
    """Visible words of one snapshot line (its name and inline text), without refs/attributes."""
    name = (m["name"] or "").replace('\\"', '"')
    tail = (m["tail"] or "").strip().strip('"')
    if m["role"].startswith("/"):  # `- /url: ...`
        return ""
    return " ".join(x for x in (name, tail) if x)


def _card_details(parsed, words, k: int, own: str) -> str:
    """Text of the nearest ancestor subtree that says more than the element itself (price, stock, ...), like the
    own-Chrome backend's card details. Empty if that subtree is larger than a card (> 400 chars)."""
    ind = parsed[k][1]
    for _ in range(8):
        j = next((j for j in range(k - 1, -1, -1) if parsed[j][1] < ind), None)
        if j is None:
            return ""
        ind = parsed[j][1]
        end = j + 1
        while end < len(parsed) and parsed[end][1] > ind:
            end += 1
        seen, parts = set(), []
        for w in words[j:end]:
            if w and w not in seen:
                seen.add(w); parts.append(w)
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if len(text) > 400:
            return ""
        if len(text) > len(own) + 15:
            return re.sub(r"\s+", " ", text.replace(own, " ")).strip()[:200]
        k = j
    return ""


def parse_evaluate(txt: str) -> str:
    """Value of a `browser_evaluate` call: the `### Result` section, JSON-decoded when it is a JSON string."""
    body = m.group("body").strip() if (m := _RESULT.search(txt)) else txt.strip()
    try:
        value = json.loads(body)
    except ValueError:
        return body
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if getattr(c, "text", None))


class ExtensionBrowser:
    def __init__(self, mcp_args: list[str] | None = None) -> None:
        # Default: attach to the user's Chrome. Tests pass e.g. ["--headless", "--isolated"] to drive the same
        # snapshot/click path in a throwaway browser.
        self._mcp_args = mcp_args or ["--extension"]
        self._s: ClientSession | None = None
        self._runner: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.page = SimpleNamespace(url="")
        self._title = ""
        self._last: list[Element] = []
        self.popup_open = False
        self.pending_dialog: str | None = None

    async def start(self) -> None:
        # The MCP client's task group must be entered and exited in the same task. Tool calls of our own MCP server
        # run in short-lived tasks, so the connection lives in one dedicated background task instead.
        if self._s:
            return
        ready: asyncio.Future = asyncio.get_running_loop().create_future()
        self._stop = asyncio.Event()
        self._runner = asyncio.create_task(self._run_connection(ready))
        await ready

    async def _run_connection(self, ready: asyncio.Future) -> None:
        # --timeout-settle 0: Playwright MCP otherwise sleeps a fixed 500 ms after every action tool (browser_evaluate
        # included, ~0.5 s per call); our callers wait for readiness themselves (v3.1: sleeps, v4: executor.ready_after)
        params = StdioServerParameters(command="npx", args=["-y", PLAYWRIGHT_MCP, *self._mcp_args, "--timeout-settle", "0"],
                                       env=dict(os.environ))
        try:
            async with stdio_client(params) as (r, w), ClientSession(r, w) as session:
                await session.initialize()
                self._s = session
                log.info("connected to user's Chrome via Playwright extension")
                ready.set_result(None)
                await self._stop.wait()
        except BaseException as e:
            if not ready.done():
                ready.set_exception(e)
            raise
        finally:
            self._s = None

    async def close(self) -> None:
        if self._s is not None or getattr(self, "_runner", None):
            self._stop.set()
            try:
                await self._runner
            except Exception:
                pass
        self._s = None

    async def _call(self, tool: str, args: dict) -> str:
        await self.start()
        res = await self._s.call_tool(tool, args)
        txt = _text(res)
        if getattr(res, "is_error", False) or getattr(res, "isError", False):
            raise RuntimeError(f"{tool} failed: " + " | ".join(txt.splitlines())[:600])
        self._update_page(txt)
        if (m := _MODAL_STATE.search(txt)) and "dialog" in m["body"].lower() and tool != "browser_handle_dialog":
            # A native alert/confirm/prompt blocks the page: dismiss it (never accept) and report it.
            self.pending_dialog = m["body"].strip()[:200]
            log.info("native dialog dismissed: %s", self.pending_dialog)
            await self._s.call_tool("browser_handle_dialog", {"accept": False})
        return txt

    def take_dialog(self) -> str | None:
        msg, self.pending_dialog = self.pending_dialog, None
        return msg

    def _update_page(self, txt: str) -> None:
        if m := _URL.search(txt):
            self.page.url = m.group(1).strip()
        if m := _TITLE.search(txt):
            self._title = m.group(1).strip()

    async def open(self, url: str) -> None:
        await self._call("browser_navigate", {"url": url})
        await asyncio.sleep(3)

    async def info(self) -> dict:
        return {"url": self.page.url, "title": self._title}

    async def snapshot(self) -> str:
        return await self._call("browser_snapshot", {})

    async def read_text(self) -> str:
        """Visible text of the page (read-only)."""
        txt = await self._call("browser_evaluate", {"function": "() => document.body ? document.body.innerText : ''"})
        return parse_evaluate(txt)

    async def is_blocked(self) -> bool:
        """Does a popup really block the page (same rule as the own-Chrome backend)?"""
        return parse_evaluate(await self._call("browser_evaluate", {"function": BLOCKED_JS})).strip() == "true"

    async def read_elements(self) -> list[Element]:
        for _ in range(6):
            blocked = await self.is_blocked()
            snap = await self.snapshot()
            self.popup_open = blocked and _modal_lines(snap.splitlines()) is not None
            self._last = parse_snapshot(snap, blocked=blocked)
            for e in self._last:  # sliders: show the value a person reads (aria-valuetext), not the raw index
                if e.role == "slider":
                    try:
                        e.state = f"value {await self.widget_value(e)}"[:60]
                    except Exception:  # noqa: BLE001 - keep the snapshot value
                        pass
            if self._last:
                return self._last
            await asyncio.sleep(1.0)
        return self._last

    async def still_same(self, el: Element) -> bool:
        fresh = parse_snapshot(await self.snapshot(), blocked=await self.is_blocked())
        return any(e.handle == el.handle and e.role == el.role and e.text == el.text and e.context == el.context
                   for e in fresh)

    async def click(self, el: Element) -> None:
        if el.type == SELECT_OPTION:
            await self._call("browser_select_option", {"element": f"combobox: {el.context}", "target": el.handle,
                                                        "values": [el.hint]})
            await asyncio.sleep(1)
            return
        before = await self._tab_list()
        await self._call("browser_click", {"element": el.label, "target": el.handle})
        await asyncio.sleep(2)
        await self._follow_new_tab(before)

    async def _tab_list(self) -> list[str]:
        """Open tabs as '<title>](<url>)' strings, in tab order (index and '(current)' marker removed)."""
        txt = await self._call("browser_tabs", {"action": "list"})
        return [re.sub(r"^- \d+: (\(current\) )?", "", ln) for ln in txt.splitlines() if re.match(r"^- \d+: ", ln)]

    async def _follow_new_tab(self, before: list[str]) -> None:
        """A click that opened a new tab (target=_blank) leaves Playwright MCP on the old tab; switch to the new one.

        Only a tab that did not exist before the click is followed; tabs that were already open are left alone.
        The list is read after the wait because the click's own response can come back before the tab exists.
        """
        after = await self._tab_list()
        if len(after) <= len(before):
            return
        remaining = list(before)
        new_idx = None
        for i, tab in enumerate(after):
            if tab in remaining:
                remaining.remove(tab)
            else:
                new_idx = i  # last tab that is not one of the pre-click tabs
        if new_idx is not None:
            await self._call("browser_tabs", {"action": "select", "index": new_idx})
            await self.snapshot()  # `select` does not report the new page's URL/title; the snapshot does
            log.info("followed new tab: %s", after[new_idx])

    async def hover(self, el: Element) -> None:
        await self._call("browser_hover", {"element": el.label, "target": el.handle})
        await asyncio.sleep(1)

    async def type(self, el: Element, text: str, submit: bool = False) -> None:
        await self._call("browser_type", {"element": el.label, "target": el.handle, "text": text, "submit": submit})
        await asyncio.sleep(1)

    async def type_text(self, el: Element, text: str, submit: bool = False) -> None:
        await self.type(el, text, submit=submit)

    async def press(self, key: str, el: Element | None = None) -> None:
        if el is not None:
            await self.focus(el)
        await self._call("browser_press_key", {"key": key})
        await asyncio.sleep(0.3)

    async def focus(self, el: Element) -> None:
        await self._call("browser_evaluate", {"element": el.label, "target": el.handle, "function": "(e) => e.focus()"})

    async def widget_value(self, el: Element) -> str:
        txt = await self._call("browser_evaluate", {"element": el.label, "target": el.handle,
                                                     "function": f"({WIDGET_VALUE_JS})"})
        return parse_evaluate(txt)

    async def scroll(self) -> None:
        await self._call("browser_evaluate", {"function": "() => window.scrollBy(0, Math.round(innerHeight * 0.9))"})
        await asyncio.sleep(1)

    async def back(self) -> None:
        await self._call("browser_navigate_back", {})
        await asyncio.sleep(1.5)

    async def element_state(self, el: Element) -> dict:
        """Evidence from the snapshot line of this ref: checked / selected value (combobox tail) / textbox value."""
        for line in (await self.snapshot()).splitlines():
            if f"[ref={el.handle}]" in line:
                m = _LINE.match(line)
                tail = ((m and m["tail"]) or "").strip().strip('"')
                return {"checked": "[checked]" in line or "[checked=true]" in line, "value": tail,
                        "expanded": "[expanded]" in line}
        return {}

    async def fill_and_submit(self, el: Element, text: str) -> None:
        await self.type(el, text, submit=True)
        await asyncio.sleep(1)
