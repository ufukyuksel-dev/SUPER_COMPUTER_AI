"""--jev-first: takeover actions only after a jev_do that did not finish, with a reason; budget and resets."""

from types import SimpleNamespace as NS

import pytest

from jev import mcp_server as m
from jev.browser import Element


def el(i, text):
    return Element(id=f"e{i}", role="button", tag="button", type="", text=text, hint="", handle=None)


class FakeBrowser:
    page = NS(url="http://x/")

    def __init__(self):
        self.clicked, self.hovered = [], []

    async def start(self):
        pass

    async def open(self, url):
        pass

    async def info(self):
        return {"url": "http://x/", "title": "X"}

    async def read_elements(self):
        return [el(0, "Ayarlar"), el(1, "Ürünler")]

    async def still_same(self, e):
        return True

    async def click(self, e):
        self.clicked.append(e.text)

    async def hover(self, e):
        self.hovered.append(e.text)


@pytest.fixture
def server(monkeypatch, tmp_path):
    b = FakeBrowser()
    brain = NS(decisions=[], decide_count=0, decide_ms_total=0)
    statuses = []

    async def fake_get():
        return b, brain

    async def fake_run(browser, br, goal, text=None, max_steps=10):
        status = statuses.pop(0)
        br.decisions = (br.decisions + [{"ms": 120}])[-50:]  # bounded like Brain.decisions
        br.decide_count += 1
        br.decide_ms_total += 120
        return {"status": status, "url": "http://x/", "title": "X", "jev_done_p": 0.1, "steps": []}

    monkeypatch.setattr(m, "_get", fake_get)
    monkeypatch.setattr(m, "run", fake_run)
    monkeypatch.setattr(m.runlog, "record", lambda *a, **k: {"reached": None})
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path))
    monkeypatch.setitem(m._policy, "jev_first", True)
    monkeypatch.setitem(m._policy, "budget", 0)
    monkeypatch.setitem(m._policy, "last_jev_do", None)
    return NS(b=b, statuses=statuses, log=tmp_path / "takeovers.jsonl")


async def look():
    await m.jev_look()


async def test_takeover_refused_before_any_jev_do(server):
    await look()
    r = await m.jev_click("e0", reason="want to")
    assert r["status"] == "refused" and "call jev_do" in r["reason"] and server.b.clicked == []


async def test_takeover_refused_after_done(server):
    server.statuses.append("done")
    await m.jev_do("Ayarları aç")
    await look()
    assert (await m.jev_click("e0", reason="x"))["status"] == "refused"


async def test_after_stuck_two_takeovers_with_reason_then_refused(server):
    server.statuses.append("stuck")
    res = await m.jev_do("Fiyatlar sayfasına git")
    assert res["timing"]["decisions"] == 1 and res["timing"]["decide_ms"] == 120
    await look()
    assert (await m.jev_hover("e1", reason=""))["status"] == "refused"          # reason required
    assert (await m.jev_hover("e1", reason="Jev cannot hover"))["status"] == "hovered"
    assert (await m.jev_click("e0", reason="submenu item after hover"))["status"] == "clicked"
    assert (await m.jev_click("e0", reason="again"))["status"] == "refused"     # budget used up
    assert server.b.hovered == ["Ürünler"] and server.b.clicked == ["Ayarlar"]
    lines = server.log.read_text().splitlines()
    assert len(lines) == 4 and '"after_jev_do": "stuck"' in lines[1]


async def test_open_resets_budget(server):
    server.statuses.append("stuck")
    await m.jev_do("x")
    await m.jev_open("http://x/other")
    await look()
    assert (await m.jev_click("e0", reason="r"))["status"] == "refused"


async def test_default_mode_is_unchanged(server, monkeypatch):
    monkeypatch.setitem(m._policy, "jev_first", False)
    await look()
    assert (await m.jev_click("e0"))["status"] == "clicked"


async def test_timing_counts_decisions_after_the_trace_is_full(server):
    """The trace keeps only 50 entries; timing must still count every new decision (was 0 / 0 ms before)."""
    server.statuses.extend(["done"] * 51)
    for _ in range(50):
        await m.jev_do("x")
    res = await m.jev_do("x")
    assert res["timing"]["decisions"] == 1 and res["timing"]["decide_ms"] == 120


def test_brain_counters_are_unbounded():
    from jev.brain import Brain
    b = Brain(client=NS())
    b.decisions = [{"ms": 1}] * 50
    assert b.decide_count == 0 and b.decide_ms_total == 0
