"""Local scenario matrix without the Jev model: element extraction, actions and reading on both backends.

own = jev.browser.Browser (own headless Chrome); ext = ExtensionBrowser driving headless @playwright/mcp (the same
snapshot parse / ref click path as the user's-Chrome extension backend, without the extension itself).
Every scenario appends a trace line (on page -> offered -> chosen -> result) to $JEV_STATE_DIR/scenarios/trace.jsonl.
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import json
import threading
import time
from pathlib import Path

import pytest

from jev.brain import text_window
from jev import paths
from jev.browser import Browser
from jev.ext_browser import ExtensionBrowser

SCN = Path(__file__).parent / "fixtures" / "scn"
TRACE = paths.state_dir() / "scenarios" / "trace.jsonl"


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SCN))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(params=["own", "ext"])
async def browser(request):
    b = Browser(profile="scenarios", headless=True) if request.param == "own" else \
        ExtensionBrowser(mcp_args=["--headless", "--isolated", "--browser", "chrome"])
    b.kind = request.param
    await b.start()
    yield b
    await b.close()


def trace(scenario: str, b, **rec) -> None:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "scenario": scenario, "backend": b.kind,
                            "chooser": "test", **rec}, ensure_ascii=False) + "\n")


# Not supported on the extension path: the Playwright MCP accessibility snapshot does not expose these at all.
EXT_GAPS = {
    "S05 details summary": "<summary> has no ARIA role/ref in the snapshot (shown as a plain `generic`)",
    "S03 name-only field": "the `name` attribute is not an accessible name; the field shows as a bare `textbox`",
}


def known_gap(sid: str, b) -> None:
    if b.kind == "ext" and sid in EXT_GAPS:
        pytest.xfail("unsupported (ext): " + EXT_GAPS[sid])


async def labels(b) -> list[str]:
    return [e.label for e in await b.read_elements()]


async def find(b, label: str):
    for e in await b.read_elements():
        if e.label == label:
            return e
    return None


async def title(b) -> str:
    for _ in range(10):  # title changes made by click handlers may land a moment later
        t = (await b.info())["title"]
        if t.startswith("OK"):
            return t
        await asyncio.sleep(0.2)
    return t


async def type_into(b, el, text: str, submit: bool) -> None:
    if b.kind == "ext":
        await b.type(el, text, submit=submit)
    elif submit:
        await b.fill_and_submit(el, text)
    else:
        await el.handle.fill(text, timeout=5000)
        await asyncio.sleep(0.3)


# (scenario id, page, label to act on, expected title after clicking it, labels that must also be offered)
CLICKS = [
    ("S01 icon button aria-label", "s01_icon_aria.html", "button: Ayarlar", "OK ayarlar", []),
    ("S02 icon button svg title", "s02_icon_inner.html", "button: Bildirimler", "OK bildirimler", ["link: Profil"]),
    ("S04 native checkbox", "s04_native_checks.html", "checkbox: Bülten", "OK bulten true", ["radio: Küçük"]),
    ("S04 native radio", "s04_native_checks.html", "radio: Büyük", "OK buyuk", []),
    ("S05 aria checkbox", "s05_aria_roles.html", "checkbox: Hatırla", "OK hatirla",
     ["radio: Aylık", "option: Seçenek A", "combobox: Dil"]),
    ("S05 aria switch", "s05_aria_roles.html", "switch: Karanlık mod", "OK karanlik", []),
    ("S05 details summary", "s05_aria_roles.html", "summary: Daha fazla", "OK detay", []),
    ("S06 same-name row (link)", "s06_same_name_rows.html", "button: Düzenle (row: Kampanya B)", "OK B",
     ["button: Düzenle (row: Kampanya A)", "button: Düzenle (row: Kampanya C)"]),
    ("S06 same-name list item", "s06_same_name_rows.html", "button: Aç (row: Liste İki)", "OK L2",
     ["button: Aç (row: Liste Bir)"]),
    ("S13 off-screen button", "s13_offscreen.html", "button: En alttaki düğme", "OK alt", []),
    ("S15 cookie bar button", "s15_cookie.html", "button: Tümünü kabul et", "OK kabul", ["link: Hakkımızda"]),
    ("S17 iframe button", "s17_iframe.html", "button: Çerçevedeki düğme", "OK cerceve", []),
    ("S18 shadow DOM button", "s18_shadow.html", "button: Gölge düğme", "OK golge", []),
]


@pytest.mark.parametrize("sid, page, target, expected, also", CLICKS, ids=[c[0] for c in CLICKS])
async def test_click_scenarios(browser, base_url, sid, page, target, expected, also):
    await browser.open(f"{base_url}/{page}")
    offered = await labels(browser)
    el = await find(browser, target)
    result = None
    if el:
        await browser.click(el)
        result = await title(browser)
    trace(sid, browser, page=page, offered=offered, chosen=target if el else None, result=result,
          ok=bool(el) and result == expected and all(a in offered for a in also))
    if el is None:
        known_gap(sid, browser)
    assert el is not None, f"{target!r} not offered; offered={offered}"
    assert result == expected
    missing = [a for a in also if a not in offered]
    assert not missing, f"not offered: {missing}; offered={offered}"


# (scenario id, page, field label, text, submit, expected title/url fragment, then click label)
TYPES = [
    ("S03 placeholder-only field", "s03_unlabeled.html", "textbox: Şehir", "Ankara", False, None, None),
    ("S03 name-only field", "s03_unlabeled.html", "textbox: kod", "42", False, None, None),
    ("S07 label-wrapped field", "s07_label_wrap.html", "textbox: Bülten adı", "x", False, None, None),
    ("S08 search + Enter", "s08_search_enter.html", "searchbox: Sitede ara", "İstanbul", True, "q=", None),
    ("S10 autocomplete option", "s10_autocomplete.html", "combobox: Şehir ara", "İst", False, "OK İstanbul",
     "option: İstanbul"),
]


@pytest.mark.parametrize("sid, page, field, text, submit, expected, then", TYPES, ids=[t[0] for t in TYPES])
async def test_type_scenarios(browser, base_url, sid, page, field, text, submit, expected, then):
    await browser.open(f"{base_url}/{page}")
    offered = await labels(browser)
    el = await find(browser, field)
    result = None
    if el:
        await type_into(browser, el, text, submit)
        if then:
            opt = await find(browser, then)
            offered_after = await labels(browser)
            if opt:
                await browser.click(opt)
            else:
                result = f"{then!r} not offered after typing; offered={offered_after}"
        info = await browser.info()
        result = result or (await title(browser) if expected and expected.startswith("OK") else info["url"])
    ok = bool(el) and (expected is None or expected in (result or ""))
    trace(sid, browser, page=page, offered=offered, chosen=field if el else None, typed=text, result=result, ok=ok)
    if el is None:
        known_gap(sid, browser)
    assert el is not None, f"{field!r} not offered; offered={offered}"
    if expected:
        assert expected in result


async def test_s09_select_options_are_offered_and_choosable(browser, base_url):
    """Native <select> options are offered as elements (context = the select) and clicking one selects it."""
    await browser.open(f"{base_url}/s09_select.html")
    offered = await labels(browser)
    opt = await find(browser, "option: Almanya (row: Ülke)")
    result = None
    if opt:
        assert await browser.still_same(opt)
        await browser.click(opt)
        result = await title(browser)
    trace("S09 select option", browser, page="s09_select.html", offered=offered, chosen=opt and opt.label,
          result=result, ok=result == "OK Almanya")
    assert "combobox: Ülke" in offered and "option: Türkiye (row: Ülke)" in offered, offered
    assert result == "OK Almanya"  # the page's own change handler reports the selected value


async def test_s12_late_content_appears_on_next_read(browser, base_url):
    await browser.open(f"{base_url}/s12_late.html")
    await asyncio.sleep(2)
    offered = await labels(browser)
    trace("S12 late content", browser, page="s12_late.html", offered=offered, chosen=None, result=None,
          ok="button: Geç yüklenen" in offered)
    assert "button: Geç yüklenen" in offered


async def test_s14_hover_menu(browser, base_url):
    await browser.open(f"{base_url}/s14_hover_menu.html")
    before = await labels(browser)
    await browser.hover(await find(browser, "button: Ürünler"))
    after = await labels(browser)
    trace("S14 hover menu", browser, page="s14_hover_menu.html", offered=before, offered_after_hover=after,
          chosen="button: Ürünler (hover)", result=None, ok="link: Fiyatlar" in after)
    assert "link: Fiyatlar" not in before and "link: Fiyatlar" in after


async def test_s15_covered_button_is_hidden(browser, base_url):
    await browser.open(f"{base_url}/s15_cookie.html")
    offered = await labels(browser)
    trace("S15 covered button", browser, page="s15_cookie.html", offered=offered, chosen=None, result=None,
          ok="button: Alt düğme" not in offered or browser.kind == "ext")
    if browser.kind == "own":
        assert "button: Alt düğme" not in offered


async def test_s16_new_tab_is_followed(browser, base_url):
    await browser.open(f"{base_url}/s16_new_tab.html")
    await browser.click(await find(browser, "link: Yeni sekmede aç"))
    await asyncio.sleep(1)
    info = await browser.info()
    trace("S16 new tab", browser, page="s16_new_tab.html", offered=None, chosen="link: Yeni sekmede aç",
          result=info["url"], ok="yenisekme" in info["url"])
    assert "yenisekme" in info["url"]


READS = [
    ("S19 table", "s19_table.html", ["İstanbul\t21\t17", "Iğdır\t25\t9"], []),
    ("S21 hidden content", "s21_hidden.html", ["GÖRÜNÜR"], ["GİZLİ-1", "GİZLİ-2", "DETAY-KAPALI"]),
]


@pytest.mark.parametrize("sid, page, present, absent", READS, ids=[r[0] for r in READS])
async def test_read_scenarios(browser, base_url, sid, page, present, absent):
    await browser.open(f"{base_url}/{page}")
    text = await browser.read_text()
    ok = all(p in text for p in present) and not any(a in text for a in absent)
    trace(sid, browser, page=page, offered=None, chosen=None, result=text[:300], ok=ok)
    assert all(p in text for p in present), text
    assert not any(a in text for a in absent), text


async def test_s20_long_text_near_text(browser, base_url):
    await browser.open(f"{base_url}/s20_long.html")
    text = await browser.read_text()
    part, cut = text_window(text, 500, near_text="AÇILIŞ YILI")
    trace("S20 long text", browser, page="s20_long.html", offered=None, chosen=None, result=part[-120:],
          ok=cut and "1973" in part)
    assert cut and "Köprünün açılış yılı: 1973" in part


@pytest.mark.parametrize("near", ["istanbul", "İSTANBUL", "ığdır", "IĞDIR"])
def test_near_text_turkish_case(near):
    text = "x" * 300 + " Merkez: İstanbul ve Iğdır " + "y" * 300
    part, cut = text_window(text, 60, near_text=near)
    assert cut and ("İstanbul" in part if "stanbul" in near.lower() else "Iğdır" in part), part


async def run_js(b, js: str) -> None:
    if b.kind == "own":
        await b.page.evaluate(js)
    else:
        await b._call("browser_evaluate", {"function": f"() => {{ {js} }}"})


async def test_still_same_rejects_button_whose_row_changed(browser, base_url):
    """The chosen 'Düzenle' must still belong to 'Kampanya A'; if the row is renamed/re-sorted under it, reject."""
    await browser.open(f"{base_url}/s06_same_name_rows.html")
    el = await find(browser, "button: Düzenle (row: Kampanya A)")
    assert el is not None and await browser.still_same(el)
    await run_js(browser, "document.querySelector('a[href=\"#a\"]').textContent = 'Kampanya Z';")
    changed = not await browser.still_same(el)
    trace("S06b row changed under chosen button", browser, page="s06_same_name_rows.html", offered=None,
          chosen=el.label, result="rejected" if changed else "accepted (wrong row)", ok=changed)
    assert changed


async def test_s22_toaster_and_empty_dialog_do_not_hide_the_page(browser, base_url):
    """Amazon case: a non-blocking role=alertdialog toaster and an empty role=dialog must not scope the page."""
    await browser.open(f"{base_url}/s22_toaster.html")
    offered = await labels(browser)
    ok = {"searchbox: Sitede ara", "link: PlayStation 5 Pro", "button: Kapat"} <= set(offered) and not browser.popup_open
    trace("S22 toaster + empty dialog", browser, page="s22_toaster.html", offered=offered, chosen=None,
          result=f"popup_open={browser.popup_open}", ok=ok)
    assert {"searchbox: Sitede ara", "link: PlayStation 5 Pro", "link: PlayStation 5 Slim", "button: Kapat"} <= set(offered), offered
    assert browser.popup_open is False


async def test_s23_dialog_over_backdrop_scopes_to_the_dialog(browser, base_url):
    """A dialog without aria-modal over a full-screen backdrop still blocks the page: only its buttons are offered."""
    await browser.open(f"{base_url}/s23_backdrop_modal.html")
    offered = await labels(browser)
    trace("S23 backdrop modal", browser, page="s23_backdrop_modal.html", offered=offered, chosen=None,
          result=f"popup_open={browser.popup_open}", ok=offered == ["button: Anladım", "button: Tura başla"])
    assert offered == ["button: Anladım", "button: Tura başla"] and browser.popup_open is True
