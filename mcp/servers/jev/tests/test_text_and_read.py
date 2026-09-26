"""Page text can be read with read_text / jev_read."""

import pytest

from jev.brain import text_window
from jev.browser import Browser
from jev.ext_browser import parse_evaluate

from conftest import fixture_url


def test_text_window():
    text = "a" * 100 + "opened in 1973" + "b" * 100
    assert text_window("short", 50) == ("short", False)
    part, cut = text_window(text, 40, near_text="OPENED")
    assert cut and "opened in 1973" in part and len(part) == 40
    part, cut = text_window(text, 40, near_text="missing")
    assert cut and part == text[:40]


def test_parse_evaluate():
    raw = '### Result\n"Bosphorus Bridge\\nOpened 30 October 1973"\n\n### Ran Playwright code\n```js\n```\n'
    assert parse_evaluate(raw) == "Bosphorus Bridge\nOpened 30 October 1973"
    assert parse_evaluate("### Result\nplain text\n") == "plain text"


async def test_browser_read_text():
    b = Browser(profile="test", headless=True)
    await b.start()
    try:
        await b.open(fixture_url("results.html") + "?q=Bosphorus")
        assert "Arama sonuçları: Bosphorus" in await b.read_text()
    finally:
        await b.close()
