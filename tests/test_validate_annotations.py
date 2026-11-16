"""Tests for the annotation validator. Run with: python -m pytest"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_annotations import DEFAULT_SCHEMA, guess_language, main, validate_file  # noqa: E402

GOOD = {
    "id": "en-900",
    "text": "The package arrived on time and the box was in good condition.",
    "language": "en",
    "content_type": "product_review",
    "sentiment": "positive",
    "intent": "praise",
    "topic": "delivery",
    "ambiguous": False,
    "notes": "",
}


def write_jsonl(tmp_path: Path, records: list) -> Path:
    path = tmp_path / "data.jsonl"
    lines = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def errors_for(tmp_path: Path, records: list) -> list[str]:
    return validate_file(write_jsonl(tmp_path, records), DEFAULT_SCHEMA).errors


def test_committed_dataset_is_valid():
    result = validate_file(ROOT / "data" / "annotations.jsonl", DEFAULT_SCHEMA)
    assert result.errors == []
    assert len(result.records) == 64
    languages = {r["language"] for r in result.records}
    assert {"es", "en", "fr", "mixed"} <= languages


def test_good_record_passes(tmp_path):
    assert errors_for(tmp_path, [GOOD]) == []


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"sentiment": "happy"}, "not a valid sentiment"),
        ({"topic": "shipping"}, "not a valid topic"),
        ({"id": "fr-900"}, "should start with 'en-'"),
        ({"text": "  "}, "text is empty"),
        ({"text": " padded text "}, "leading or trailing spaces"),
        ({"intent": "praise", "sentiment": "negative"}, "requires sentiment"),
        ({"intent": "complaint", "sentiment": "positive"}, "requires sentiment"),
        ({"ambiguous": True, "notes": ""}, "notes are required"),
        ({"ambiguous": "no"}, "must be boolean"),
        ({"text": "Write to me at someone@example.com"}, "email address"),
        ({"text": "Call me on +57 300 123 4567"}, "phone number"),
    ],
)
def test_invalid_records_are_rejected(tmp_path, change, expected):
    errors = errors_for(tmp_path, [{**GOOD, **change}])
    assert any(expected in e for e in errors), errors


def test_missing_field_and_extra_field(tmp_path):
    missing = {k: v for k, v in GOOD.items() if k != "topic"}
    extra = {**GOOD, "id": "en-901", "text": "Another text.", "score": 3}
    errors = errors_for(tmp_path, [missing, extra])
    assert any("missing field 'topic'" in e for e in errors)
    assert any("unexpected field" in e for e in errors)


def test_duplicates_are_detected(tmp_path):
    same_id = {**GOOD, "text": "A different text with the same id."}
    same_text = {**GOOD, "id": "en-902", "text": GOOD["text"].upper()}
    errors = errors_for(tmp_path, [GOOD, same_id, same_text])
    assert any("duplicate id" in e for e in errors)
    assert any("duplicate text" in e for e in errors)


def test_invalid_json_line_is_reported(tmp_path):
    errors = errors_for(tmp_path, [GOOD, "{not json"])
    assert any("line 2: invalid JSON" in e for e in errors)


def test_language_mismatch_is_a_warning_not_an_error(tmp_path):
    record = {**GOOD, "text": "Le colis est arrivé à temps et je suis très content."}
    result = validate_file(write_jsonl(tmp_path, [record]), DEFAULT_SCHEMA)
    assert result.errors == []
    assert len(result.warnings) == 1 and "suggest 'fr'" in result.warnings[0]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("¿Cómo cambio el correo de mi cuenta?", "es"),
        ("How do I download my invoices?", "en"),
        ("Je voudrais annuler mon abonnement.", "fr"),
        ("Ok", None),
    ],
)
def test_guess_language(text, expected):
    assert guess_language(text)[0] == expected


def test_cli_exit_codes(tmp_path):
    good = write_jsonl(tmp_path, [GOOD])
    assert main(["--data", str(good)]) == 0
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({**GOOD, "sentiment": "???"}) + "\n", encoding="utf-8")
    assert main(["--data", str(bad)]) == 1
    assert main(["--data", str(tmp_path / "missing.jsonl")]) == 1
