"""Agent takeover guard (jev_click / jev_type)."""

import pytest

from jev.browser import Element
from jev.mcp_server import check_takeover


def el(text, role="button", type_="", hint=""):
    return Element(id="e1", role=role, tag="button", type=type_, text=text, hint=hint, handle=None)


def test_plain_navigation_click_allowed():
    assert check_takeover(el("Edit (row: IOS_TR)")) is None


@pytest.mark.parametrize("text", ["Save", "Kaydet", "Publish", "Confirm", "Onayla", "Delete", "Apply"])
def test_changing_clicks_need_user_approval(text):
    assert "user" in check_takeover(el(text))
    assert check_takeover(el(text), user_approved=True) is None


def test_sensitive_field_never_typed_even_with_approval():
    assert check_takeover(el("Password", role="textbox", type_="password"), typing=True)
    assert check_takeover(el("Kart numarası", role="textbox"), typing=True)


def test_date_field_typing_allowed():
    assert check_takeover(el("Start time", role="textbox"), typing=True) is None


def test_unknown_id():
    assert check_takeover(None)
