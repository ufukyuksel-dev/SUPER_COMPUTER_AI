"""Popups: modal dialogs, covering overlays, native alert/confirm, and failing clicks."""

from types import SimpleNamespace as NS

import pytest

from jev.brain import Brain, run
from jev.browser import Browser
from jev.ext_browser import ExtensionBrowser, parse_snapshot

from conftest import fixture_url, needs_jev
from test_unit import FakeClient, LINK


@pytest.fixture
async def browser():
    b = Browser(profile="test", headless=True)
    await b.start()
    yield b
    await b.close()


async def test_modal_limits_elements_to_popup(browser):
    await browser.open(fixture_url("modal.html"))
    labels = [e.label for e in await browser.read_elements()]
    assert labels == ["button: Anladım"] and browser.popup_open


async def test_covered_elements_are_skipped(browser):
    await browser.open(fixture_url("overlay.html"))
    assert await browser.read_elements() == []


async def test_popup_opening_after_decision_blocks_click(browser):
    await browser.open(fixture_url("index.html"))
    link = next(e for e in await browser.read_elements() if e.text == "Reklamlar")
    await browser.page.evaluate("""
      const d = document.createElement('div');
      d.style = 'position:fixed;inset:0;background:#000a';
      document.body.append(d);
    """)
    assert not await browser.still_same(link)


async def test_native_confirm_is_dismissed_and_reported(browser):
    await browser.open(fixture_url("confirm.html"))
    result = await run(browser, Brain(client=FakeClient(target=("e0", 0.9))), "devam et", max_steps=3)
    assert result["status"] == "needs_you" and "Kampanya silinsin mi?" in result["reason"]
    assert await browser.page.title() == "RED"  # dismissed, never accepted


class FailingBrowser:
    def __init__(self):
        self.page = NS(url="file:///x")
        self.clicks = 0

    async def read_elements(self):
        return [LINK]

    async def info(self):
        return {"url": "file:///x", "title": "X"}

    async def still_same(self, el):
        return True

    async def click(self, el):
        self.clicks += 1
        raise TimeoutError("Timeout 5000ms exceeded.")


async def test_failing_click_does_not_crash():
    b = FailingBrowser()
    result = await run(b, Brain(client=FakeClient(target=("e0", 0.9))), "go", max_steps=5)
    # The failed element is not offered again, so Jev has nothing left to pick instead of retrying the same click.
    assert result["status"] == "stuck" and result["reason"] == "Jev: no listed element helps"
    assert b.clicks == 1


class FirstOfferedClient(FakeClient):
    """Picks the first offered element, like a model that keeps preferring the covered button."""

    states: list[dict] = []

    async def system_one(self, state, questions):
        self.states.append(state)
        first = state["elements"][0]["id"] if state["elements"] else "none"
        self.target = (first, 0.9)
        return await super().system_one(state, questions)


class CoveredThenFreeBrowser(FailingBrowser):
    """'Alt düğme' is covered until 'Reddet' (the cookie bar) is clicked."""

    def __init__(self):
        super().__init__()
        self.bar = True
        self.log: list[str] = []
        self.alt = el_(0, "Alt düğme")
        self.reddet = el_(1, "Reddet")

    async def read_elements(self):
        return [self.alt, self.reddet]

    async def click(self, el):
        self.log.append(el.text)
        if el is self.alt and self.bar:
            raise TimeoutError("<div id=cb> intercepts pointer events")
        if el is self.reddet:
            self.bar = False


def el_(i, text):
    from jev.browser import Element
    return Element(id=f"e{i}", role="button", tag="button", type="", text=text, hint="", handle=None)


async def test_failed_element_is_skipped_once_then_retried_after_another_action():
    b = CoveredThenFreeBrowser()
    client = FirstOfferedClient(done=0.1)
    client.states = []
    await run(b, Brain(client=client), "Alt düğmeye bas", max_steps=3)
    assert b.log == ["Alt düğme", "Reddet", "Alt düğme"] and not b.bar
    # Jev is told which click failed (so it can dismiss the covering bar), and only until another action succeeds.
    assert [st.get("could_not_click") for st in client.states] == [None, ["button: Alt düğme"], None]


SNAP = """### Page
- Page URL: https://ads.tiktok.com/x
- Page Title: TikTok Ads
### Snapshot
```yaml
- generic [ref=a1]:
  - link "IOS_TR" [ref=a2] [cursor=pointer]
  - generic [active]:
    - dialog:
      - generic [ref=a3]:
        - generic [ref=a4]: Announcement
        - button "Got it" [ref=a5] [cursor=pointer]
        - button "Take a tour" [ref=a6] [cursor=pointer]
  - link "Android_tr" [ref=a7] [cursor=pointer]
```
"""


def test_snapshot_dialog_scopes_elements():
    assert [e.text for e in parse_snapshot(SNAP)] == ["Got it", "Take a tour"]


def test_snapshot_without_dialog_lists_page():
    no_dialog = SNAP.replace("- dialog:", "- region:")
    assert {"IOS_TR", "Android_tr", "Got it"} <= {e.text for e in parse_snapshot(no_dialog)}


@needs_jev
async def test_jev_closes_popup_then_navigates(browser):
    """Real Jev: the announcement popup is dismissed first, then the target link is clicked."""
    await browser.open(fixture_url("modal.html"))
    result = await run(browser, Brain(), "Reklam Yöneticisi sayfasına git", max_steps=4)
    print(result)
    assert [s["element_text"] for s in result["steps"]][:2] == ["Anladım", "Reklam Yöneticisi"]
    assert result["url"].endswith("manager.html")


def test_snapshot_row_context_separates_identical_buttons():
    snap = """- rowgroup [ref=r0]:
  - row [ref=r1]:
    - cell [ref=r2]:
      - link "IOS_TR" [ref=r3] [cursor=pointer]
    - cell [ref=r4]:
      - button "Edit" [ref=r5] [cursor=pointer]
  - row [ref=r6]:
    - cell [ref=r7]:
      - link "Android_tr" [ref=r8] [cursor=pointer]
    - cell [ref=r9]:
      - button "Edit" [ref=r10] [cursor=pointer]
"""
    els = parse_snapshot(snap)
    labels = [e.label for e in els]
    assert "button: Edit (row: IOS_TR)" in labels and "button: Edit (row: Android_tr)" in labels
    # The row goes into the label only, so it cannot trip the save/delete brake that looks at `text`.
    assert {e.text for e in els if e.role == "button"} == {"Edit"}


class TabStubBrowser(ExtensionBrowser):
    """ExtensionBrowser with a scripted Playwright MCP: tab lists before/after the click; records calls."""

    def __init__(self, before: list[str], after: list[str]):
        super().__init__()
        self.lists = [before, after]
        self.calls: list[tuple[str, dict]] = []

    async def _call(self, tool, args):
        self.calls.append((tool, args))
        if tool == "browser_tabs" and args["action"] == "list":
            tabs = self.lists.pop(0)
            return "### Result\n" + "\n".join(f"- {i}: {t}" for i, t in enumerate(tabs))
        return ""


def _selects(b):
    return [a["index"] for t, a in b.calls if t == "browser_tabs" and a["action"] == "select"]


@pytest.mark.parametrize("before, after, selected", [
    # Two tabs already open, the click opens nothing: stay (the old code switched to the pre-existing 2nd tab).
    (["(current) [Ads](https://a/1)", "[Docs](https://d/1)"], ["(current) [Ads](https://a/1)", "[Docs](https://d/1)"], []),
    # Two tabs already open, the click opens a third one: follow only the new one.
    (["(current) [Ads](https://a/1)", "[Docs](https://d/1)"],
     ["(current) [Ads](https://a/1)", "[Docs](https://d/1)", "[Report](https://a/r)"], [2]),
    # The new tab has the same title/url as an existing one: still the new (third) one.
    (["(current) [Ads](https://a/1)", "[Docs](https://d/1)"],
     ["(current) [Ads](https://a/1)", "[Docs](https://d/1)", "[Docs](https://d/1)"], [2]),
])
async def test_ext_follows_only_a_tab_opened_by_the_click(before, after, selected, monkeypatch):
    monkeypatch.setattr("jev.ext_browser.asyncio.sleep", _no_sleep)
    b = TabStubBrowser(before, after)
    await b.click(el_(0, "Aç"))
    assert _selects(b) == selected


async def _no_sleep(_):
    return None


def test_snapshot_select_options_become_elements():
    snap = """- generic [ref=e1]:
  - combobox "Ülke" [ref=e2]:
    - option "Türkiye" [selected]
    - option "Almanya"
    - option "Fransa" [disabled]
  - button "Kaydet" [ref=e3]
"""
    els = parse_snapshot(snap)
    assert [e.label for e in els] == ["combobox: Ülke", "option: Türkiye (row: Ülke)", "option: Almanya (row: Ülke)",
                                      "button: Kaydet"]
    alm = els[2]
    assert alm.handle == "e2" and alm.hint == "Almanya" and alm.type == "select-option"


def test_snapshot_empty_trailing_dialog_does_not_hide_the_page():
    snap = """- generic [ref=e1]:
  - searchbox "Search Amazon" [ref=e2]
  - link "PlayStation 5 Pro" [ref=e3] [cursor=pointer]
  - alertdialog "International Shopping Transition Alert" [ref=e4]:
    - button "Change Address" [ref=e5]
  - dialog [ref=e6]
"""
    # blocked unknown: skip the empty dialog, scope to the last non-empty one
    assert [e.text for e in parse_snapshot(snap)] == ["Change Address"]
    # blocked=False (toaster, checked in the browser): the whole page
    assert [e.text for e in parse_snapshot(snap, blocked=False)] == ["Search Amazon", "PlayStation 5 Pro", "Change Address"]
