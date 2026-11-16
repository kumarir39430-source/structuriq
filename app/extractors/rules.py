"""Offline, dependency-free extraction engine.

Takes any messy text and produces a structured dictionary:
document type, summary, keywords, entities, key/value fields, tables,
line items, bullets and basic stats.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from datetime import datetime
from typing import Any

MONTHS = (
    "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    "January|February|March|April|June|July|August|September|October|November|December"
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.I)
IP_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
DATE_RES = [
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\.?,?\s+\d{{4}}\b", re.I),
    re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.I),
]
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s?(?:[AaPp]\.?[Mm]\.?)?(?!\d)")
AMOUNT_RES = [
    re.compile(r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s?\d[\d,]*(?:\.\d+)?", re.I),
    re.compile(r"\b\d[\d,]*(?:\.\d+)?\s?(?:USD|INR|EUR|GBP|rupees|dollars|euros)\b", re.I),
]
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%")
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,5}\)|\d{2,5})[\s.-]?\d{3}[\s.-]?\d{3,5}(?![\w])")
HASHTAG_RE = re.compile(r"(?<!\w)#[A-Za-z][\w]{1,40}")
MENTION_RE = re.compile(r"(?<![\w@])@[A-Za-z][\w]{1,30}\b(?!\.\w)")
TITLE_NAME_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})")
EMAIL_NAME_RE = re.compile(r"([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})\s*<[^<>@\s]+@[^<>\s]+>")
INTRO_NAME_RE = re.compile(r"\b(?:name's|name is|called|met|contact)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})")
SIGNOFF_RE = re.compile(r"(?:regards|thanks|thank you|sincerely|best|cheers),?\s*\n\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*$", re.I | re.M)
ORG_RE = re.compile(
    r"\b((?:[A-Z][\w&.-]*\s){1,4}(?:Inc\.?|Ltd\.?|LLC|Corp\.?|Corporation|Company|Pvt\.?\s?Ltd\.?|GmbH|"
    r"Technologies|Solutions|University|Institute|Systems|Labs|Bank))\b"
)
KV_RE = re.compile(r"^\s*[-*•]?\s*([A-Za-z][A-Za-z0-9 _/#.&()%-]{0,40}?)\s*[:=]\s*(\S.*?)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|\[[ xX]?\])\s+(.+?)\s*$")
LINE_ITEM_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*[x×]\s+(.+?)\s+(?:@|at|-|–)\s*((?:₹|Rs\.?|\$|€|£)?\s?\d[\d,]*(?:\.\d+)?)\s*(?:each|ea)?\s*$",
    re.I,
)
ACTION_RE = re.compile(r"\b(todo|to-do|action item|follow[- ]?up|need to|needs to|must|will|please|deadline|due)\b", re.I)

STOPWORDS = set(
    """a about above after again all also am an and any are as at be because been before being below between both but by
    can could did do does doing down during each few for from further had has have having he her here hers him his how i if
    in into is it its just me more most my no nor not now of off on once only or other our out over own same she should so
    some such than that the their them then there these they this those through to too under until up very was we were what
    when where which while who whom why will with would you your yours dear hello regards thanks thank please also may might
    shall per via etc""".split()
)

DOC_TYPES: dict[str, list[str]] = {
    "invoice": ["invoice", "bill to", "amount due", "subtotal", "total due", "gst", "tax", "qty", "unit price", "payment terms"],
    "receipt": ["receipt", "paid", "transaction", "cashier", "change due", "thank you for shopping"],
    "email": ["subject:", "from:", "to:", "cc:", "regards", "dear ", "sent:", "best,"],
    "resume": ["resume", "curriculum vitae", "experience", "education", "skills", "projects", "objective", "certifications"],
    "meeting_notes": ["agenda", "attendees", "minutes", "action items", "discussed", "next meeting", "meeting"],
    "job_posting": ["responsibilities", "requirements", "qualifications", "apply", "we are hiring", "job description", "salary"],
    "contract": ["agreement", "party", "hereby", "terms and conditions", "clause", "governing law", "witness"],
    "log": ["error", "warn", "info", "debug", "traceback", "exception", "stack trace"],
    "support_ticket": ["ticket", "issue", "steps to reproduce", "priority", "reported by", "assigned to", "status"],
}


# ----------------------------------------------------------------- helpers
def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for s, e in spans:
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


def _dedupe(seq: list[Any]) -> list[Any]:
    seen, out = set(), []
    for item in seq:
        key = item if isinstance(item, str) else repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _to_number(raw: str) -> float | None:
    m = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _currency_of(raw: str) -> str:
    r = raw.lower()
    for sym, code in (("₹", "INR"), ("rs", "INR"), ("inr", "INR"), ("rupee", "INR"), ("$", "USD"), ("usd", "USD"), ("dollar", "USD"),
                      ("€", "EUR"), ("eur", "EUR"), ("£", "GBP"), ("gbp", "GBP")):
        if sym in r:
            return code
    return ""


def _iso_date(raw: str) -> str | None:
    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)", "", raw.strip().replace(",", ""), flags=re.I).replace("Sept", "Sep")
    fmts = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"]
    for f in fmts:
        try:
            return datetime.strptime(cleaned, f).date().isoformat()
        except ValueError:
            continue
    return None


def _norm_key(key: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", key.lower())).strip()


# ------------------------------------------------------------- extraction
def extract_entities(text: str) -> dict[str, list[Any]]:
    work = text
    ent: dict[str, list[Any]] = {}

    def grab(regex: re.Pattern) -> list[re.Match]:
        nonlocal work
        found = list(regex.finditer(work))
        work = _mask(work, [m.span() for m in found])
        return found

    ent["emails"] = _dedupe([m.group(0) for m in grab(EMAIL_RE)])
    ent["urls"] = _dedupe([m.group(0).rstrip(".,;") for m in grab(URL_RE)])
    ent["ip_addresses"] = _dedupe([m.group(0) for m in grab(IP_RE)])

    dates: list[dict[str, Any]] = []
    for rx in DATE_RES:
        for m in grab(rx):
            dates.append({"raw": m.group(0), "iso": _iso_date(m.group(0))})
    ent["dates"] = _dedupe(dates)
    ent["times"] = _dedupe([m.group(0).strip().rstrip(".") for m in grab(TIME_RE)])

    amounts: list[dict[str, Any]] = []
    for rx in AMOUNT_RES:
        for m in grab(rx):
            amounts.append({"raw": m.group(0).strip(), "currency": _currency_of(m.group(0)), "value": _to_number(m.group(0))})
    ent["amounts"] = _dedupe(amounts)
    ent["percentages"] = _dedupe([m.group(0) for m in grab(PERCENT_RE)])

    phones = []
    for m in grab(PHONE_RE):
        digits = re.sub(r"\D", "", m.group(0))
        if 10 <= len(digits) <= 13:
            phones.append(m.group(0).strip())
    ent["phones"] = _dedupe(phones)
    ent["hashtags"] = _dedupe([m.group(0) for m in HASHTAG_RE.finditer(text)])
    ent["mentions"] = _dedupe([m.group(0) for m in MENTION_RE.finditer(text)])

    people = [m.group(1).strip() for m in TITLE_NAME_RE.finditer(text)]
    people += [m.group(1).strip() for m in EMAIL_NAME_RE.finditer(text)]
    people += [m.group(1).strip() for m in SIGNOFF_RE.finditer(text)]
    people += [m.group(1).strip() for m in INTRO_NAME_RE.finditer(text)]
    ent["people"] = _dedupe(people)
    ent["organizations"] = _dedupe([m.group(1).strip() for m in ORG_RE.finditer(text)])
    return ent


def extract_key_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = KV_RE.match(line)
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if len(key.split()) > 5 or val.startswith("//") or key.lower() in {"http", "https"}:
            continue
        if key in out:  # keep repeats as key (2), key (3) ...
            n = 2
            while f"{key} ({n})" in out:
                n += 1
            key = f"{key} ({n})"
        out[key] = val
    return out


def extract_tables(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    tables: list[dict[str, Any]] = []
    for delim, min_rows in (("|", 2), ("\t", 2), (",", 3)):
        block: list[list[str]] = []

        def flush():
            nonlocal block
            rows = [r for r in block if not all(re.fullmatch(r":?-{2,}:?", c) or not c for c in r)]
            if len(rows) >= min_rows and max(len(c) for r in rows for c in r) <= 60:
                headers = rows[0]
                body = [r + [""] * (len(headers) - len(r)) for r in rows[1:]]
                if not any(t["headers"] == headers for t in tables):
                    tables.append({"headers": headers, "rows": [r[: len(headers)] for r in body], "delimiter": delim})
            block = []

        width = None
        for line in lines + [""]:
            skip = delim == "," and (":" in line or re.search(r"\d,\d{3}", line))
            cells = [c.strip() for c in line.strip().strip("|").split(delim)] if delim in line and not skip else []
            if len(cells) >= 2 and (width is None or len(cells) == width):
                width = len(cells)
                block.append(cells)
            else:
                flush()
                width = None
                if len(cells) >= 2:
                    width = len(cells)
                    block.append(cells)
    return tables


def extract_line_items(text: str) -> list[dict[str, Any]]:
    items = []
    for line in text.splitlines():
        m = LINE_ITEM_RE.match(line)
        if m:
            qty, desc, price = float(m.group(1)), m.group(2).strip(), m.group(3).strip()
            unit = _to_number(price)
            items.append({
                "quantity": qty, "description": desc, "unit_price": unit,
                "line_total": round(qty * unit, 2) if unit is not None else None,
            })
    return items


def extract_bullets(text: str) -> dict[str, list[str]]:
    bullets = [m.group(1) for line in text.splitlines() if (m := BULLET_RE.match(line))]
    actions = [b for b in bullets if ACTION_RE.search(b)]
    for line in text.splitlines():
        if re.match(r"^\s*(todo|action)\b", line, re.I) and line.strip() not in actions:
            actions.append(line.strip())
    return {"bullets": bullets, "action_items": _dedupe(actions)}


def classify(text: str) -> tuple[str, float]:
    low = text.lower()
    scores = {t: sum(low.count(k) for k in kws) for t, kws in DOC_TYPES.items()}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    if scores[best] < 2:
        return "general_text", 0.3
    return best, round(min(0.99, scores[best] / max(total, 1) * min(1.0, scores[best] / 6) + 0.2), 2)


def keywords(text: str, n: int = 10) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
    counts = Counter(w for w in words if w not in STOPWORDS)
    return [w for w, _ in counts.most_common(n)]


def summarize(text: str, max_sentences: int = 2) -> str:
    """Pick the most keyword-dense prose sentences; skip 'Key: value' lines and bullets."""
    prose = [
        ln.strip() for ln in text.splitlines()
        if ln.strip() and not ln.strip().endswith(":") and not (KV_RE.match(ln) or BULLET_RE.match(ln) or LINE_ITEM_RE.match(ln) or "|" in ln)
    ]
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(prose))
    sentences = [c.strip() for c in chunks if len(c.split()) >= 4]
    if not sentences:
        pairs = [ln.strip() for ln in text.splitlines() if KV_RE.match(ln)][:3]
        if pairs:
            return "; ".join(pairs)
        flat = re.sub(r"\s+", " ", text).strip()
        return flat[:160].rsplit(" ", 1)[0] + ("…" if len(flat) > 160 else "")
    kw = set(keywords(text, 15))
    scored = []
    for i, s in enumerate(sentences):
        score = sum(1 for w in re.findall(r"[a-z']+", s.lower()) if w in kw) / (len(s.split()) ** 0.5)
        scored.append((score + (0.5 if i == 0 else 0), i, s))
    top = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda x: x[1])
    return " ".join(s for _, _, s in top)


# ---------------------------------------------------------- custom fields
_FIELD_HINTS = {
    "email": ("emails", None), "mail": ("emails", None),
    "phone": ("phones", None), "mobile": ("phones", None), "contact number": ("phones", None),
    "url": ("urls", None), "website": ("urls", None), "link": ("urls", None),
    "date": ("dates", "raw"), "deadline": ("dates", "raw"), "due": ("dates", "raw"),
    "total": ("amounts", "max"), "amount": ("amounts", "max"), "price": ("amounts", "max"), "cost": ("amounts", "max"),
    "name": ("people", None), "company": ("organizations", None), "organization": ("organizations", None),
}


def extract_fields(fields: list[str], kv: dict[str, str], ent: dict[str, list[Any]]) -> dict[str, Any]:
    norm_map = {_norm_key(k): v for k, v in kv.items()}
    result: dict[str, Any] = {}
    for field in fields:
        nf = _norm_key(field)
        value: Any = None
        if nf in norm_map:
            value = norm_map[nf]
        else:
            f_tokens = {t for t in nf.split() if len(t) >= 3}
            overlap = []
            for k in norm_map:
                k_tokens = {t for t in k.split() if len(t) >= 3}
                if f_tokens & k_tokens:
                    overlap.append((len(f_tokens & k_tokens) / len(f_tokens | k_tokens), k))
            if overlap:
                value = norm_map[max(overlap)[1]]
            else:
                close = difflib.get_close_matches(nf, list(norm_map), n=1, cutoff=0.85)
                if close:
                    value = norm_map[close[0]]
        if value is None:
            for hint, (bucket, mode) in _FIELD_HINTS.items():
                if hint in nf and ent.get(bucket):
                    items = ent[bucket]
                    if mode == "max":
                        vals = [a for a in items if a.get("value") is not None]
                        value = max(vals, key=lambda a: a["value"])["raw"] if vals else None
                    elif mode == "raw":
                        value = items[0]["raw"]
                    else:
                        value = items[0]
                    break
        result[field] = value
    return result


# ------------------------------------------------------------------ main
def extract_with_rules(text: str, fields: list[str] | None = None) -> dict[str, Any]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    doc_type, conf = classify(text)
    ent = extract_entities(text)
    kv = extract_key_values(text)
    bullets = extract_bullets(text)
    result: dict[str, Any] = {
        "document_type": doc_type,
        "confidence": conf,
        "summary": summarize(text),
        "keywords": keywords(text),
        "fields": kv,
        "entities": {k: v for k, v in ent.items() if v},
        "tables": extract_tables(text),
        "line_items": extract_line_items(text),
        "bullets": bullets["bullets"],
        "action_items": bullets["action_items"],
        "stats": {
            "characters": len(text),
            "words": len(text.split()),
            "lines": len(text.splitlines()),
        },
    }
    li = result["line_items"]
    if li:
        result["computed_total"] = round(sum(i["line_total"] or 0 for i in li), 2)
    if fields:
        result["custom_fields"] = extract_fields(fields, kv, ent)
    return result
