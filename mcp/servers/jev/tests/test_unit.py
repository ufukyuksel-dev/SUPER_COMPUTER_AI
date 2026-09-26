"""Decision logic with a fake Jev client (no network, no browser)."""

from types import SimpleNamespace as NS

import pytest

from jev.brain import Brain, rank
from jev.browser import Element


def el(i, role, text, tag="a", type_="", hint=""):
    return Element(id=f"e{i}", role=role, tag=tag, type=type_, text=text, hint=hint, handle=None)


class FakeClient:
    def __init__(self, done=0.1, target=("e0", 0.9), field=None):
        self.done, self.target, self.field = done, target, field
        self.last_questions = None
        self.last_state = None

    @staticmethod
    def _choice(choice, p):
        return NS(choice=choice, probabilities={choice: p, "none": 1 - p}, confidence=p)

    async def system_one(self, state, questions):
        self.last_questions = questions
        self.last_state = state
        choices = {"target": self._choice(*self.target)}
        if "field" in questions and self.field:
            choices["field"] = self._choice(*self.field)
        return NS(nouls={"done": NS(noul=self.done)}, choices=choices)


PAGE = {"url": "file:///x", "title": "X"}
SEARCH = el(1, "searchbox", "Sitede ara", tag="input", type_="search")
PASSWORD = el(2, "textbox", "Şifre", tag="input", type_="password", hint="password")
LINK = el(0, "link", "Reklamlar")


async def decide(client, elements, text=None):
    return await Brain(client=client).decide("go", PAGE, elements, [], text)


async def test_click_when_confident():
    d = await decide(FakeClient(target=("e0", 0.9)), [LINK])
    assert d.kind == "click" and d.element is LINK


async def test_done_stops():
    d = await decide(FakeClient(done=0.95), [LINK])
    assert d.kind == "done"


async def test_low_confidence_is_stuck():
    d = await decide(FakeClient(target=("e0", 0.3)), [LINK])
    assert d.kind == "stuck" and d.options


async def test_typing_takes_precedence_over_click():
    d = await decide(FakeClient(target=("e0", 0.9), field=("e1", 0.9)), [LINK, SEARCH, PASSWORD], text="kampanya")
    assert d.kind == "type" and d.element is SEARCH


async def test_password_never_offered_as_field():
    client = FakeClient(field=("e1", 0.9))
    await decide(client, [LINK, SEARCH, PASSWORD], text="kampanya")
    assert set(client.last_questions["field"].criteria) == {"e1", "none"}


async def test_text_without_search_field_needs_you():
    d = await decide(FakeClient(target=("e0", 0.9)), [LINK, PASSWORD], text="kampanya")
    assert d.kind == "needs_you"


async def test_uncertain_field_falls_back_to_click():
    d = await decide(FakeClient(target=("e0", 0.9), field=("e1", 0.3)), [LINK, SEARCH], text="kampanya")
    assert d.kind == "click"


@pytest.mark.parametrize("text", ["Satın al", "Hesabı sil", "Publish video", "Gönder"])
async def test_brake(text):
    d = await decide(FakeClient(target=("e0", 0.9)), [el(0, "button", text, tag="button")])
    assert d.kind == "needs_you"


def test_search_field_detection():
    assert SEARCH.is_search_field()
    assert el(3, "textbox", "", tag="input", type_="text", hint="q Ara...").is_search_field()
    assert not PASSWORD.is_search_field()
    assert not el(4, "textbox", "Kart numarası ara", tag="input", type_="text", hint="cc-number").is_search_field()
    assert not LINK.is_search_field()


def test_rank_keeps_order_and_limit():
    items = [el(i, "link", f"Sayfa {i}") for i in range(200)] + [el(200, "link", "Reklam Yöneticisi")]
    kept = rank("Reklam Yöneticisi", items, limit=150)
    assert len(kept) == 150 and kept[-1].text == "Reklam Yöneticisi"
    assert [e.id for e in kept] == sorted((e.id for e in kept), key=lambda s: int(s[1:]))


async def test_text_fields_are_not_click_targets():
    client = FakeClient(target=("e0", 0.9))
    await decide(client, [LINK, SEARCH, PASSWORD])
    assert set(client.last_questions["target"].criteria) == {"e0", "none"}


class FakeBrowser:
    """Clicking never changes the URL."""

    def __init__(self):
        self.page = NS(url="file:///x")
        self.clicks = 0

    async def read_elements(self):
        return [LINK]

    async def info(self):
        return PAGE

    async def still_same(self, el):
        return True

    async def click(self, el):
        self.clicks += 1


async def test_same_click_without_progress_stops():
    from jev.brain import run

    b = FakeBrowser()
    result = await run(b, Brain(client=FakeClient(target=("e0", 0.9))), "go", max_steps=10)
    assert result["status"] == "stuck" and "no progress" in result["reason"]
    assert b.clicks == 1


@pytest.mark.parametrize("role,type_,hint", [
    ("searchbox", "password", ""),
    ("searchbox", "email", ""),
    ("searchbox", "search", "cc-number"),
    ("searchbox", "text", "current-password"),
    ("textbox", "search", "q Kart numarası"),
])
def test_sensitive_signals_beat_search_role(role, type_, hint):
    assert not el(9, role, "Ara", tag="input", type_=type_, hint=hint).is_search_field()
