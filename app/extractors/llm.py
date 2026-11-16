"""Optional LLM extractor (Anthropic Messages API). Used only when ANTHROPIC_API_KEY is set."""
from __future__ import annotations

import json
import re
from typing import Any

from .. import config

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = (
    "You convert messy, unstructured text into clean structured JSON. "
    "Respond with ONE valid JSON object and nothing else: no prose, no markdown fences. "
    "Never invent facts that are not in the text; use null for anything missing."
)

BASE_SCHEMA = """{
  "document_type": "short snake_case label, e.g. invoice, email, resume, meeting_notes, general_text",
  "summary": "1-2 sentence summary",
  "keywords": ["up to 10 keywords"],
  "fields": {"<label>": "<value>"},
  "entities": {"people": [], "organizations": [], "emails": [], "phones": [], "urls": [],
               "dates": [{"raw": "", "iso": "YYYY-MM-DD or null"}],
               "amounts": [{"raw": "", "currency": "", "value": 0}]},
  "tables": [{"headers": [], "rows": [[]]}],
  "line_items": [{"description": "", "quantity": 0, "unit_price": 0, "line_total": 0}],
  "action_items": []
}"""


class LLMError(RuntimeError):
    pass


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("Model did not return JSON")
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"Invalid JSON from model: {exc}") from exc


def extract_with_llm(text: str, fields: list[str] | None = None, timeout: float = 60.0) -> dict[str, Any]:
    if not config.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    try:
        import httpx
    except ImportError as exc:
        raise LLMError("httpx is not installed") from exc
    custom = ""
    if fields:
        custom = (
            "\nAlso add a top-level object \"custom_fields\" with exactly these keys "
            f"(null when absent): {json.dumps(fields)}"
        )
    prompt = f"Target JSON shape:\n{BASE_SCHEMA}{custom}\n\nText to structure:\n<text>\n{text}\n</text>"
    payload = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        resp = httpx.post(API_URL, json=payload, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise LLMError(f"Network error: {exc}") from exc
    if resp.status_code != 200:
        raise LLMError(f"API error {resp.status_code}: {resp.text[:200]}")
    blocks = resp.json().get("content", [])
    out = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return _parse_json(out)
