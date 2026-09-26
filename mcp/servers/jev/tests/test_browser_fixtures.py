"""Headless Chrome on local fixtures. Tests marked needs_jev call the real TypeSafe API."""

import pytest

from jev import runlog
from jev.brain import Brain, run
from jev.browser import Browser

from conftest import fixture_url, needs_jev


@pytest.fixture
async def browser():
    b = Browser(profile="test", headless=True)
    await b.start()
    yield b
    await b.close()


async def _find(browser, text):
    return next(e for e in await browser.read_elements() if e.text == text)


async def test_still_same_detects_detach_and_text_change(browser):
    await browser.open(fixture_url("changing.html"))
    good = await _find(browser, "Profil ayarlarını aç")
    assert await browser.still_same(good)
    await browser.page.evaluate("document.getElementById('good').textContent = 'Hesabı sil'")
    assert not await browser.still_same(good)
    await browser.page.evaluate("document.getElementById('good').remove()")
    assert not await browser.still_same(good)


async def test_inserted_element_does_not_redirect_click(browser):
    await browser.open(fixture_url("changing.html"))
    good = await _find(browser, "Profil ayarlarını aç")
    await browser.page.evaluate("""
      const b = document.createElement('button');
      b.textContent = 'Yanlış buton';
      b.onclick = () => document.title = 'TIKLANDI: Yanlış';
      document.getElementById('box').prepend(b);
    """)
    assert await browser.still_same(good)
    await browser.click(good)
    assert await browser.page.title() == "TIKLANDI: Profil"


@needs_jev
async def test_fixture_navigation_reaches_destination(browser):
    """Spec §5.1 (required): home → Reklamlar → Reklam Yöneticisi, success judged by URL, not by Jev."""
    await browser.open(fixture_url("index.html"))
    goal = "Reklam Yöneticisi sayfasına git"
    result = await run(browser, Brain(), goal, max_steps=6)
    rec = runlog.record(goal, result, expected="manager.html")
    print(result, rec)
    assert rec["reached"] is True, result


@needs_jev
async def test_changing_page_never_clicks_inserted_button(browser):
    """Spec §5.2: a button inserted before the chosen one after reading must never be clicked."""
    await browser.open(fixture_url("changing.html"))
    inserted = False

    async def insert_decoy(b, decision):
        nonlocal inserted
        if inserted:
            return
        inserted = True
        await b.page.evaluate("""
          const x = document.createElement('button');
          x.textContent = 'Yanlış buton';
          x.onclick = () => document.title = 'TIKLANDI: Yanlış';
          document.getElementById('box').prepend(x);
        """)

    result = await run(browser, Brain(), "Profil ayarlarını aç butonuna tıkla", max_steps=1, before_act=insert_decoy)
    print(result)
    assert inserted
    assert result["title"] != "TIKLANDI: Yanlış"


@needs_jev
async def test_typing_fills_search_once(browser):
    """Spec §5.3: text goes only into the search box, once."""
    await browser.open(fixture_url("search.html"))
    result = await run(browser, Brain(), "Sitede 'kampanya' kelimesini ara", text="kampanya", max_steps=3)
    print(result)
    typed = [s for s in result["steps"] if s["action"] == "type"]
    assert len(typed) == 1
    assert "results.html" in result["url"] and "q=kampanya" in result["url"]


async def test_field_values_never_observed(browser):
    """Typed/prefilled values must not appear in element text (observation, jev_look, Jev state)."""
    await browser.open(fixture_url("secret.html"))
    await browser.page.fill("#s", "SENTINEL_TYPED_VALUE")
    elements = await browser.read_elements()
    dump = repr([(e.role, e.text, e.hint) for e in elements])
    for sentinel in ("SENTINEL_PW_VALUE", "SENTINEL_TEXT_VALUE", "SENTINEL_TYPED_VALUE"):
        assert sentinel not in dump
    assert any(e.text == "Tamam" for e in elements)  # button-like inputs keep their value label


async def test_jev_state_has_no_field_values(browser):
    from test_unit import FakeClient

    await browser.open(fixture_url("secret.html"))
    client = FakeClient(target=("none", 0.9), field=("none", 0.9))
    await Brain(client=client).decide("ara", await browser.info(), await browser.read_elements(), [], "x")
    assert "SENTINEL" not in repr(client.last_state)


async def test_field_turning_sensitive_is_not_filled(browser):
    await browser.open(fixture_url("search.html"))
    field_el = next(e for e in await browser.read_elements() if e.is_search_field())
    await browser.page.evaluate("document.querySelector('input[type=search]').setAttribute('autocomplete', 'cc-number')")
    assert not await browser.still_same(field_el)
