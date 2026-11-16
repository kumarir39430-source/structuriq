"""Orchestrates rules + optional LLM extraction and returns one unified result."""
from __future__ import annotations

import time
from typing import Any

from .. import config
from .llm import LLMError, extract_with_llm
from .rules import extract_with_rules


def run_extraction(text: str, fields: list[str] | None = None, mode: str = "auto") -> dict[str, Any]:
    started = time.perf_counter()
    fields = [f.strip() for f in (fields or []) if f and f.strip()]
    warnings: list[str] = []
    text = text[: config.MAX_INPUT_CHARS]

    rules_result = extract_with_rules(text, fields)
    result, mode_used = rules_result, "rules"

    want_llm = mode == "llm" or (mode == "auto" and config.LLM_ENABLED)
    if want_llm:
        try:
            llm_result = extract_with_llm(text, fields)
            # Keep the deterministic stats/entities from rules and let the LLM enrich the rest.
            merged = {**rules_result, **{k: v for k, v in llm_result.items() if v not in (None, "", [], {})}}
            merged["stats"] = rules_result["stats"]
            merged["entities"] = {**rules_result.get("entities", {}), **llm_result.get("entities", {})}
            merged["fields"] = {**rules_result.get("fields", {}), **llm_result.get("fields", {})}
            result, mode_used = merged, "llm+rules"
        except LLMError as exc:
            warnings.append(f"LLM unavailable, used rule-based engine instead: {exc}")

    result["meta"] = {
        "mode_requested": mode,
        "mode_used": mode_used,
        "warnings": warnings,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    return result
