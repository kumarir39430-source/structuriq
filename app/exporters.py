"""Turn a result dict into JSON, CSV or Markdown."""
from __future__ import annotations

import csv
import io
import json
from typing import Any


def _flat(v: Any) -> str:
    if isinstance(v, dict):
        return v.get("raw") or json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)


def to_csv(result: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "key", "value"])
    w.writerow(["meta", "document_type", result.get("document_type", "")])
    w.writerow(["meta", "summary", result.get("summary", "")])
    for k, v in (result.get("fields") or {}).items():
        w.writerow(["field", k, _flat(v)])
    for k, v in (result.get("custom_fields") or {}).items():
        w.writerow(["custom_field", k, _flat(v)])
    for kind, items in (result.get("entities") or {}).items():
        for item in items:
            w.writerow(["entity", kind, _flat(item)])
    for item in result.get("line_items") or []:
        w.writerow(["line_item", item.get("description", ""), json.dumps(item, ensure_ascii=False)])
    for a in result.get("action_items") or []:
        w.writerow(["action_item", "", a])
    return buf.getvalue()


def to_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Extraction result: {result.get('document_type', 'document')}", "", f"**Summary:** {result.get('summary', '')}", ""]
    if result.get("keywords"):
        lines += ["**Keywords:** " + ", ".join(result["keywords"]), ""]
    for title, key in (("Fields", "fields"), ("Custom fields", "custom_fields")):
        data = result.get(key) or {}
        if data:
            lines += [f"## {title}", "", "| Key | Value |", "|---|---|"]
            lines += [f"| {k} | {_flat(v).replace('|', '/')} |" for k, v in data.items()]
            lines.append("")
    if result.get("entities"):
        lines += ["## Entities", ""]
        for kind, items in result["entities"].items():
            lines.append(f"- **{kind}**: " + ", ".join(_flat(i) for i in items))
        lines.append("")
    for t in result.get("tables") or []:
        lines += ["## Table", "", "| " + " | ".join(t["headers"]) + " |", "|" + "---|" * len(t["headers"])]
        lines += ["| " + " | ".join(r) + " |" for r in t["rows"]]
        lines.append("")
    if result.get("action_items"):
        lines += ["## Action items", ""] + [f"- {a}" for a in result["action_items"]] + [""]
    return "\n".join(lines)


EXPORTERS = {
    "json": (to_json, "application/json", "json"),
    "csv": (to_csv, "text/csv", "csv"),
    "md": (to_markdown, "text/markdown", "md"),
}
