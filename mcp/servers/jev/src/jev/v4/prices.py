"""Prices in page text, for the code-side comparison of options (plan v4 §4.6). Parsing only; never a model."""

from __future__ import annotations

import re

CUR = {"$": "USD", "us$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD", "€": "EUR", "eur": "EUR",
       "euro": "EUR", "euros": "EUR", "£": "GBP", "gbp": "GBP", "₺": "TRY", "tl": "TRY", "try": "TRY",
       "turkish lira": "TRY", "lira": "TRY"}
_AMOUNT = r"\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_SYM = r"US\$|\$|€|£|₺|USD|EUR|GBP|TRY|TL"
_WORD = r"Turkish\s+Lira|lira|dollars?|euros?|TL|TRY|USD|EUR|GBP|€|₺"
PREFIX = re.compile(rf"(?P<c>{_SYM})\s?(?P<a>{_AMOUNT})", re.I)
SUFFIX = re.compile(rf"(?P<a>{_AMOUNT})\s?(?P<c>{_WORD})(?![A-Za-z])", re.I)


def _number(raw: str) -> float:
    raw = raw.replace(" ", "")
    if re.search(r"[.,]\d{1,2}$", raw) and not re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw):
        dec = raw[-3] if raw[-3] in ".," else raw[-2]
        whole, frac = raw[:raw.rfind(dec)], raw[raw.rfind(dec) + 1:]
        return float(re.sub(r"[.,]", "", whole) + "." + frac)
    return float(re.sub(r"[.,]", "", raw))


def find_prices(text: str) -> list[tuple[float, str]]:
    """All prices in reading order. A symbol followed by an amount is a prefix price ("20 ₺7,560" is ₺7,560, not
    "20 ₺"); a suffix price is used only when its symbol does not start a prefix price ("32.450 TL", "15122 Turkish
    Lira")."""
    text = text or ""
    found = [(m.start(), m.group("a"), m.group("c")) for m in PREFIX.finditer(text)]
    prefix_syms = {m.start("c") for m in PREFIX.finditer(text)}
    for m in SUFFIX.finditer(text):
        if m.start("c") not in prefix_syms and not any(st <= m.start() < st + len(a) + len(c) + 1 for st, a, c in found):
            found.append((m.start(), m.group("a"), m.group("c")))
    out = []
    for _, amount, cur in sorted(found):
        cur = re.sub(r"\s+", " ", cur.lower())
        out.append((_number(amount), CUR.get(cur, cur.upper())))
    return out


def first_price(text: str) -> tuple[float, str] | None:
    p = find_prices(text)
    return p[0] if p else None


_TOTAL = re.compile(r"\b(total|in total|grand total|toplam|toplamda)\b", re.I)
_PER_PERSON = re.compile(r"\b(per person|per adult|per passenger|per traveller|per traveler|each|pp|kişi başı|"
                         r"yetişkin başı)\b|/\s?(person|adult|kişi)", re.I)
_SCOPE = re.compile(r"\b(round[- ]trip|one[- ]way|return trip|gidiş[- ]dönüş|tek yön)\b", re.I)
_PAX = re.compile(r"\bfor (\d+) (?:adults?|passengers?|people|travell?ers?)\b|\b(\d+) (?:yetişkin|yolcu|kişi) için\b",
                  re.I)


def total_price(text: str, require_total: bool) -> dict | None:
    """The option's total price, or None when it is not clear (review run 4: compare totals, never the first number).
    A price counts when its own wording marks it as a total (and not per person). Without such a mark, only a single
    price with no per-person wording counts, and only when `require_total` is False. Also returns the scope
    (round trip / one way) and passenger count when the text states them, so options are compared like for like."""
    text = text or ""
    spans = []
    for m in PREFIX.finditer(text):
        spans.append((m.start(), m.end()))
    for m in SUFFIX.finditer(text):
        if not any(a <= m.start() < b for a, b in spans):
            spans.append((m.start(), m.end()))
    spans.sort()
    prices = find_prices(text)
    marked = []
    for (value, cur), (st, en) in zip(prices, spans):
        before = re.split(r"[;,.]\s", text[max(0, st - 14): st])[-1]      # same clause only
        after = re.split(r"[;,]|\.\s", text[en: en + 28])[0]
        # per person: the wording right before the price ("kişi başı 625 TL") or right after it ("₺100 per person")
        per_person = _PER_PERSON.search(before) or _PER_PERSON.match(text[en: en + 20].lstrip(" "))
        if (_TOTAL.search(before) or _TOTAL.search(after)) and not per_person:
            marked.append((value, cur))
    if marked:
        value, cur = marked[0]
    elif not require_total and len(prices) == 1 and not _PER_PERSON.search(text):
        value, cur = prices[0]
    else:
        return None
    scope = _SCOPE.search(text)
    pax = _PAX.search(text)
    return {"price": value, "currency": cur,
            "scope": re.sub(r"[\s-]+", " ", scope.group(1).lower()) if scope else None,
            "passengers": int(pax.group(1) or pax.group(2)) if pax else None}


# a minimum rating asked for in a requirement ("guest rating 4.5 or higher", "4+ stars", "en az 4.5 puan")
MIN_RATING = [re.compile(r"(?:rating|rated|stars?|puan|yıldız)\D{0,20}?(\d(?:[.,]\d)?)\s*(?:\+|or (?:higher|more|above)|"
                         r"and (?:up|above)|ve üzeri|veya üzeri|minimum|at least)", re.I),
              re.compile(r"(?:at least|minimum|en az)\s*(\d(?:[.,]\d)?)\s*(?:\+)?\s*(?:\S+\s){0,2}?(?:rating|stars?|puan|yıldız)", re.I),
              re.compile(r"(\d(?:[.,]\d)?)\s*(?:\+|or (?:higher|more|above))\s*(?:\S+\s){0,2}?(?:rating|stars?|puan|yıldız)", re.I)]
# an option's own rating as listings show it: "4.7 (105)", "4.7/5", "4.7 ★", "4.7 stars"
RATING = re.compile(r"(?<![\d.,])([1-5][.,]\d)\s*(?:/\s*5|\(\s*[\d.,]+\s*[KkMm]?\s*\)|★|stars?\b)")


def min_rating(texts: list[str]) -> float | None:
    for t in texts:
        for rx in MIN_RATING:
            m = rx.search(t or "")
            if m:
                return float(m.group(1).replace(",", "."))
    return None


def own_rating(text: str) -> float | None:
    m = RATING.search(text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def listing_key(text: str) -> str:
    """A normalised label without prices, numbers and punctuation: duplicate rows of one listing share it.
    One-letter words are kept: they are often the only thing that tells listings apart ("Option X", "Deal B")."""
    t = re.sub(r"(US\$|\$|€|£|₺|TRY|TL|USD|EUR)\s?[\d.,]+[KkMm]?|[\d.,]+\s?(TRY|TL|₺|Turkish Lira)", " ", text or "")
    return " ".join(re.findall(r"[^\W\d_]+", t.lower()))[:120]
