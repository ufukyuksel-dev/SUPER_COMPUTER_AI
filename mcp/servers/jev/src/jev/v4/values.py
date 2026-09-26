"""Value contract (plan v4 §4.4, v1.2 from design note report-v4-spike.md (private)): code checks before anything is typed."""
import datetime as dt
import re
import unicodedata

SENSITIVE = ("password", "şifre", "parola", "e-mail", "email", "e-posta", "eposta", "phone", "telefon", "card",
             "kart", "cvv", "cvc", "iban", "tc kimlik", "ssn")
NUMERIC_FIELD = ("price", "fiyat", "budget", "bütçe", "quantity", "adet", "miktar", "rating", "puan", "min", "max",
                 "amount", "tutar")
LIMIT_ROLES = ("price", "limit", "max", "min", "budget", "fiyat", "bütçe", "rating", "quantity")
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            "pazartesi": 0, "salı": 1, "sali": 1, "çarşamba": 2, "carsamba": 2, "perşembe": 3, "persembe": 3,
            "cuma": 4, "cumartesi": 5, "pazar": 6}
MONTHS = {m: i + 1 for i, names in enumerate([
    ("january", "ocak"), ("february", "şubat"), ("march", "mart"), ("april", "nisan"), ("may", "mayıs"),
    ("june", "haziran"), ("july", "temmuz"), ("august", "ağustos"), ("september", "eylül"), ("october", "ekim"),
    ("november", "kasım"), ("december", "aralık")]) for m in names}
STOP = {"the", "a", "an", "of", "for", "about", "on", "in", "and", "to", "ve", "için", "ile", "bir", "da", "de"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", (s or "").replace("İ", "i")).lower().replace("\u0307", "")
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def words(s: str) -> list[str]:
    # quotes around a word are punctuation, not part of it ('browser-use/jev' -> browser, use, jev)
    return [w for w in (t.strip("'") for t in re.findall(r"[\w']+", norm(s))) if w and w not in STOP]


def numbers(s: str) -> list[float]:
    out = []
    for m in re.finditer(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?", s or ""):
        raw = m.group()
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw):
            raw = re.sub(r"[.,]", "", raw)
        else:
            raw = raw.replace(",", ".")
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def dates_in(span: str, today: dt.date) -> list[dt.date]:
    s, out = norm(span), []
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", s):
        out.append(dt.date(*map(int, m.groups())))
    for m in re.finditer(r"(\d{1,2})\s+([a-zçğıöşü]+)(?:\s+(\d{4}))?", s):
        if m.group(2) in MONTHS:
            out.append(dt.date(int(m.group(3) or today.year), MONTHS[m.group(2)], int(m.group(1))))
    for m in re.finditer(r"([a-zçğıöşü]+)\s+(\d{1,2}),?\s+(\d{4})", s):
        if m.group(1) in MONTHS:
            out.append(dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))))
    if re.search(r"\b(yarın|tomorrow)\b", s):
        out.append(today + dt.timedelta(days=1))
    for name, wd in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", s):
            d = today + dt.timedelta(days=(wd - today.weekday()) % 7 or 7)
            if re.search(r"\b(haftaya|next week|gelecek hafta|önümüzdeki hafta)\b", s) and \
                    d.isocalendar()[1] == today.isocalendar()[1]:
                d += dt.timedelta(days=7)
            out.append(d)
    return out


def parse_date(v: str) -> dt.date | None:
    v = norm(v)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    ds = dates_in(v, dt.date(2000, 1, 1))
    return ds[0] if len(ds) == 1 and re.search(r"\d{4}", v) else None


TR_SUFFIX = re.compile(r"'s|'?(?:da|de|ta|te|dan|den|tan|ten|a|e|ya|ye|ı|i|u|ü|yı|yi|yu|yü|ın|in|un|ün|nın|nin|nun|"
                      r"nün|la|le|yla|yle|daki|deki|taki|teki|lar|ler|ları|leri|ndan|nden|nda|nde)")
CURRENCY = {"$": "USD", "us$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD", "dolar": "USD",
            "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR", "avro": "EUR",
            "tl": "TRY", "₺": "TRY", "lira": "TRY", "£": "GBP", "gbp": "GBP", "pound": "GBP"}


def _word_match(w: str, s: str) -> bool:
    """Same word, or `s` = `w` + a Turkish case/plural suffix or an English possessive (tuzla -> tuzlada, 5 -> 5'i,
    gödel -> gödel's). Not car -> carpet."""
    if w == s:
        return True
    return s.startswith(w) and bool(TR_SUFFIX.fullmatch(s[len(w):])) and not s[len(w)].isdigit()


def currencies(s: str) -> set[str]:
    s = norm(s)
    found = {c for sym, c in CURRENCY.items() if not sym.isalpha() and sym in s}
    found |= {c for sym, c in CURRENCY.items() if sym.isalpha() and re.search(rf"(?<![a-z]){re.escape(sym)}(?![a-z])", s)}
    return found


def kind_of(field: dict) -> str:
    label = norm(field["label"] + " " + field.get("context", ""))
    if field.get("type") in ("date", "datetime-local") or re.search(r"\b(date|tarih|departure|return|gidiş|dönüş)\b", label):
        return "date"
    if field["role"] in ("slider", "spinbutton") or field.get("type") in ("number", "range") or \
            any(w in label for w in NUMERIC_FIELD):
        return "number"
    return "text"


def check(proposal: dict, field: dict, sources: list[str], today: dt.date, role_ok=None) -> tuple[bool, str]:
    """Return (accept, reason). `sources` = user goal, caller end_condition, caller checklist (never the helper's).
    `role_ok(role_in_goal, field_label) -> float` is the Jev Noul (injected; None = skip, for unit tests)."""
    label = norm(field["label"])
    if any(w in label for w in SENSITIVE) or field.get("type") in ("password", "email", "tel"):
        return False, "sensitive field"
    value = proposal.get("value")
    if value is None or str(value).strip() == "":
        return False, "helper returned no value"
    value = str(value)
    if norm(proposal.get("field", "")) != label:
        return False, "field does not match the chosen target"
    span = norm(proposal.get("goal_span", ""))
    if not span or not any(span in norm(s) for s in sources):
        return False, "goal_span is not verbatim in the user's goal/end_condition/checklist"
    kind = kind_of(field)
    if kind == "number":
        nums = numbers(value)
        if len(nums) != 1 or re.search(r"[a-zA-Zçğıöşü]", re.sub(r"(?i)\b(tl|usd|eur|\$|€|stars?|yıldız)\b", "", value)):
            return False, "a number field needs one number"
        if nums[0] not in numbers(span):
            return False, f"{nums[0]:g} is not a number from the goal span"
        span_cur = currencies(span) or currencies(" ".join(sources))
        field_cur = currencies(" ".join(str(field.get(k, "")) for k in ("label", "state", "context")))
        unit_cur = currencies(str(proposal.get("unit", "")) + " " + value)
        if span_cur and field_cur and not span_cur & field_cur:
            return False, f"currency mismatch: goal {sorted(span_cur)}, field {sorted(field_cur)} (no conversion)"
        if span_cur and unit_cur and not span_cur & unit_cur:
            return False, f"currency mismatch: goal {sorted(span_cur)}, proposal {sorted(unit_cur)}"
        lo, hi = field.get("min"), field.get("max")
        if lo is not None and nums[0] < lo or hi is not None and nums[0] > hi:
            return False, "outside the field's range"
    elif kind == "date":
        d = parse_date(value)
        if not d:
            return False, "not a date"
        if d not in dates_in(span, today):
            return False, f"{d} is not the date in the goal span"
    else:
        vw, sw = words(value), words(span)
        if not vw or not all(any(_word_match(w, x) for x in sw) for w in vw):
            return False, "text uses words that are not in the goal span"
        role = norm(proposal.get("role_in_goal", ""))
        searchy = field["role"] == "searchbox" or re.search(r"\b(search|ara|arama|query)\b", label)
        if any(r in role for r in LIMIT_ROLES) or (re.fullmatch(r"[\d.,\s$€₺tl]+", norm(value)) and searchy):
            return False, "a limit/number value does not go into a free-text or search field"
    if role_ok is not None:
        p = role_ok(proposal.get("role_in_goal", ""), field["label"], value)
        if p < 0.5:
            return False, f"Jev: role does not fit the field (p={p:.2f})"
    return True, "ok"
