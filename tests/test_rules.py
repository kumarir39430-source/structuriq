from pathlib import Path

from app.extractors.rules import extract_with_rules

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def read(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def test_invoice_fields_and_totals():
    r = extract_with_rules(read("sample_invoice.txt"), ["invoice number", "total", "due date"])
    assert r["document_type"] == "invoice"
    assert r["fields"]["Invoice Number"] == "INV-2026-0142"
    assert r["custom_fields"]["invoice number"] == "INV-2026-0142"
    assert r["custom_fields"]["total"] == "₹27,431.46"
    assert r["custom_fields"]["due date"] == "2026-11-30"
    assert len(r["line_items"]) == 3
    assert r["line_items"][0]["line_total"] == 2998.0
    assert r["tables"] == []  # thousand separators must not look like a CSV table


def test_entities():
    r = extract_with_rules(read("sample_email.txt"))
    ent = r["entities"]
    assert "arjun.rao@northstar.com" in ent["emails"]
    assert ent["dates"][0]["iso"] == "2026-11-21"
    assert ent["times"] == ["3:30 PM"]
    assert ent["amounts"][0]["value"] == 120000.0
    assert "Arjun Rao" in ent["people"]
    assert "#planning" in ent["hashtags"]


def test_meeting_notes_table_and_actions():
    r = extract_with_rules(read("sample_notes.txt"))
    assert r["document_type"] == "meeting_notes"
    assert r["tables"][0]["headers"] == ["Name", "Role", "Status"]
    assert len(r["tables"][0]["rows"]) == 3
    assert any("login bug" in a for a in r["action_items"])


def test_messy_text():
    r = extract_with_rules(read("sample_messy.txt"), ["priority", "phone"])
    assert r["custom_fields"]["priority"] == "high"
    assert r["custom_fields"]["phone"] == "9820012345"
    assert "Sandeep Kulkarni" in r["entities"]["people"]


def test_empty_like_text_does_not_crash():
    r = extract_with_rules("hello")
    assert r["document_type"] == "general_text"
    assert r["stats"]["words"] == 1
