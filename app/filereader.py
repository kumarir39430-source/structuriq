"""Read text out of uploaded files (txt/md/csv/json/log/pdf/docx)."""
from __future__ import annotations

import io

TEXT_EXT = {".txt", ".md", ".csv", ".json", ".log", ".tsv", ".eml", ".html", ".htm", ".xml", ".yaml", ".yml"}


class UnsupportedFile(ValueError):
    pass


def read_upload(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    ext = name[name.rfind("."):] if "." in name else ""
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(parts).strip()
    if ext in TEXT_EXT or not ext:
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                return data.decode(enc).strip()
            except UnicodeDecodeError:
                continue
    raise UnsupportedFile(f"Unsupported file type: {ext or 'unknown'}")
