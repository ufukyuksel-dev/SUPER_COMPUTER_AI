"""Redaction of incidental personal data before anything leaves the browser process (review run 4).

Applied once per snapshot, to the display strings only (control texts, contexts, details, full names, cards, page text
and title). Selectors (`data-jev` ids) and option values are untouched, so actions and local identity checks still
work. The same redacted snapshot feeds Jev (TypeSafe), the text helper and every stored record, so nothing is sent or
saved unredacted in the first place.

What is removed:
- the signed-in account's name and contact details: an account control ("Google Account: Jane Doe (jane@x.com)",
  "Signed in as …", "Hesap: …") becomes "account menu", and the name found there is replaced everywhere else;
- email addresses → "[email]"; phone numbers written as phone numbers → "[phone]".
This is not a general PII remover: other personal data on a page (e.g. an address in an order history) is not
detected. Dates, prices, times and flight numbers are kept (see tests).
"""

from __future__ import annotations

import re
from dataclasses import replace

SECRET_PARAM = re.compile(r"\b((?:access_|auth_|id_|refresh_)?token|key|secret|password|code|sig)=[^&#\s)\]]+", re.I)
EMAIL = re.compile(r"[\w.+-]+(?:@|%40)[\w-]+(?:\.[\w-]+)+", re.I)
# a phone number: optional +country code, then 9–12 digits in phone-like groups; never inside a longer token, never
# an ISO date (2026-10-20), a time (10:50) or a price (13,594)
PHONE = re.compile(r"(?<![\w.,:/-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{3,4})(?:[\s.-]\d{2,4}){2,3}(?![\w.,:/-])")
# an account control: "Google Account: Name (mail)", "Account: Name", "Signed in as Name" — a colon or "signed in as"
# is required, so labels such as "Account & Lists" are not taken for a name
ACCOUNT = re.compile(r"^(?:(?:google account|account|hesap|hesabım|profile|profil)\s*:|signed in as|oturum açan)\s*"
                     r"(?P<name>[^()\[\]@:]{2,60}?)\s*(?:\(|\[|$)", re.I)
ACCOUNT_LABEL = "account menu"


def _phone(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group())
    return "[phone]" if 9 <= len(digits) <= 13 and not re.fullmatch(r"\d{4}[\s.-]\d{2}[\s.-]\d{2}", m.group()) \
        else m.group()


class Redactor:
    def __init__(self):
        self.names: set[str] = set()   # account names seen in this task (replaced wherever they appear)

    def text(self, s: str) -> str:
        if not s:
            return s
        for name in sorted(self.names, key=len, reverse=True):
            s = re.sub(re.escape(name), "[account name]", s, flags=re.I)
        s = SECRET_PARAM.sub(r"\1=[redacted]", s)
        s = EMAIL.sub("[email]", s)
        return PHONE.sub(_phone, s)

    def learn(self, label: str) -> bool:
        """Remember the name in an account control's label; True if the label is an account control."""
        m = ACCOUNT.match((label or "").strip())
        if not m:
            return False
        name = m.group("name").strip(" :-–")
        if len(name) >= 3 and not EMAIL.search(name) and re.search(r"[^\W\d_]{2,}", name):
            self.names.add(name)
        return True

    def snapshot(self, snap):
        for c in snap.controls:  # names first, so they are removed from every string below
            self.learn(c.text) or self.learn(c.full)
        controls = []
        for c in snap.controls:
            account = bool(ACCOUNT.match((c.text or "").strip()) or ACCOUNT.match((c.full or "").strip()))
            controls.append(replace(
                c, text=ACCOUNT_LABEL if account else self.text(c.text),
                full="" if account else self.text(c.full), context=self.text(c.context),
                details=self.text(c.details), card=self.text(c.card), state=self.text(c.state),
                hint=c.hint if c.type == "select-option" else self.text(c.hint)))
        # the display URL (model input, records) is redacted; the real one stays in `real_url` for local checks and
        # page identity; the fingerprint is kept only as a hash
        return replace(snap, controls=controls, text=self.text(snap.text), title=self.text(snap.title),
                       url=self.text(snap.url), real_url=snap.real_url or snap.url)  # fp is already a hash

    def url(self, url: str) -> str:
        return self.text(url or "")


def _hash(fp: str) -> str:
    import hashlib
    return hashlib.sha1((fp or "").encode()).hexdigest()[:16] if fp else ""
