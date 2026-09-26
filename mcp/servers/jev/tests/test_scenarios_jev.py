"""Selected local scenarios with the real Jev model (TypeSafe API). Each run appends a trace line:
on the page (all elements) -> offered to Jev -> Jev's choice per step -> actual result."""

from __future__ import annotations

import json
import time

import pytest

from jev.brain import Brain, run

from conftest import needs_jev
from test_scenarios import TRACE, base_url, browser, title  # noqa: F401  (fixtures)

# (scenario, page, goal, text, check kind, expected substring)
JEV = [
    ("J01 icon button", "s01_icon_aria.html", "Ayarları aç", None, "title", "OK ayarlar"),
    ("J04 native checkbox", "s04_native_checks.html", "Bülten kutucuğunu işaretle", None, "title", "OK bulten true"),
    ("J05 aria switch", "s05_aria_roles.html", "Karanlık modu aç", None, "title", "OK karanlik"),
    ("J06 same-name row", "s06_same_name_rows.html", "Kampanya B'yi düzenle", None, "title", "OK B"),
    ("J09 select option", "s09_select.html", "Ülke olarak Almanya'yı seç", None, "title", "OK Almanya"),
    ("J10 autocomplete", "s10_autocomplete.html", "Şehir olarak İstanbul'u seç", "İst", "title", "OK İstanbul"),
    ("J15 covered by cookie bar", "s15_cookie.html", "Alt düğmeye bas", None, "title", "OK alt"),
    ("J16 new tab", "s16_new_tab.html", "Yeni sekmede açılan sayfaya git", None, "url", "yenisekme"),
    ("J17 iframe", "s17_iframe.html", "Çerçevedeki düğmeye bas", None, "title", "OK cerceve"),
    ("J18 shadow DOM", "s18_shadow.html", "Gölge düğmeye bas", None, "title", "OK golge"),
    ("J14 hover menu (unsupported)", "s14_hover_menu.html", "Fiyatlar sayfasına git", None, "url", "fiyat"),
]


@needs_jev
@pytest.mark.parametrize("sid, page, goal, text, kind, expected", JEV, ids=[j[0] for j in JEV])
async def test_jev_scenarios(browser, base_url, sid, page, goal, text, kind, expected):
    await browser.open(f"{base_url}/{page}")
    on_page = [e.label for e in await browser.read_elements()]
    brain = Brain()
    result = await run(browser, brain, goal, text=text, max_steps=4)
    got = await title(browser) if kind == "title" else (await browser.info())["url"]
    ok = expected in got
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with TRACE.open("a") as f:
        f.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "scenario": sid, "backend": browser.kind, "chooser": "jev",
            "page": page, "goal": goal, "text": text, "on_page": on_page,
            "decisions": brain.decisions, "status": result["status"], "reason": result.get("reason"),
            "steps": result["steps"], "result": got, "ok": ok}, ensure_ascii=False) + "\n")
    if "unsupported" in sid and not ok:
        pytest.xfail("Jev cannot hover; the submenu link is never offered")
    assert ok, f"{sid}: got {got!r}; status={result['status']} reason={result.get('reason')} decisions={brain.decisions}"
