"""Command-line usage:  python cli.py samples/sample_invoice.txt [--fields "invoice number,total"] [--format json|csv|md]"""
import argparse
from pathlib import Path

from app.exporters import EXPORTERS
from app.extractors import run_extraction
from app.filereader import read_upload


def main() -> None:
    p = argparse.ArgumentParser(description="Convert unstructured text into structured data")
    p.add_argument("file", help="Path to a .txt/.md/.csv/.pdf/.docx file")
    p.add_argument("--fields", default="", help="Comma-separated custom fields to extract")
    p.add_argument("--mode", default="auto", choices=["auto", "rules", "llm"])
    p.add_argument("--format", default="json", choices=list(EXPORTERS))
    p.add_argument("--out", help="Write output to this file instead of printing")
    a = p.parse_args()

    path = Path(a.file)
    text = read_upload(path.name, path.read_bytes())
    fields = [f.strip() for f in a.fields.split(",") if f.strip()]
    result = run_extraction(text, fields, a.mode)
    output = EXPORTERS[a.format][0](result)
    if a.out:
        Path(a.out).write_text(output, encoding="utf-8")
        print(f"Saved {a.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
