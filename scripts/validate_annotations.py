"""Validate the annotation file against the label schema and guidelines.

Checks
------
Errors (the file is not accepted):
  - invalid JSON, missing fields, wrong field types
  - labels outside the allowed set
  - duplicate ids or duplicate texts
  - id prefix that does not match the language label
  - empty, untrimmed, or too long text
  - intent/sentiment combinations forbidden by the guidelines
  - missing notes on ambiguous or mixed-language items
  - patterns that look like personal data (emails, phone numbers, URLs)

Warnings (worth a second look, but not necessarily wrong):
  - a simple function-word heuristic suggests a different language

Usage:
    python scripts/validate_annotations.py
    python scripts/validate_annotations.py --report reports/validation_report.md --csv data/annotations.csv

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "annotations.jsonl"
DEFAULT_SCHEMA = ROOT / "schema" / "label_schema.json"

PII_PATTERNS = {
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "phone number": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
    "URL": re.compile(r"https?://|www\.", re.IGNORECASE),
}

# Very common function words. Good enough to flag obvious mislabels in short texts.
FUNCTION_WORDS = {
    "es": {"el", "la", "los", "las", "que", "y", "de", "en", "mi", "me", "no", "se", "por", "con",
           "una", "un", "es", "del", "para", "lo", "ya", "cómo", "qué", "sí", "muy"},
    "en": {"the", "and", "is", "to", "my", "i", "it", "of", "a", "for", "you", "can", "with",
           "was", "this", "that", "in", "do", "on", "not", "after", "from", "have"},
    "fr": {"le", "la", "les", "et", "de", "est", "je", "mon", "ma", "un", "une", "pour", "des",
           "pas", "vous", "à", "du", "que", "avec", "au", "sans", "il", "nous", "ce"},
}

TOKEN_RE = re.compile(r"[a-záéíóúñüàâçèêëîïôùûœ']+", re.IGNORECASE)


@dataclass
class ValidationResult:
    records: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def guess_language(text: str) -> tuple[str | None, dict[str, int]]:
    """Return the language whose function words appear most often, or None on a tie/zero."""
    tokens = [t.lower().strip("'") for t in TOKEN_RE.findall(text)]
    # Split French elisions such as "l'application" -> "l", "application".
    words = [w for t in tokens for w in t.split("'") if w]
    scores = {lang: sum(w in vocab for w in words) for lang, vocab in FUNCTION_WORDS.items()}
    best = max(scores.values())
    leaders = [lang for lang, score in scores.items() if score == best]
    return (leaders[0] if best > 0 and len(leaders) == 1 else None), scores


def validate_record(rec: dict, schema: dict, where: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    types = {"string": str, "boolean": bool}

    for name, type_name in schema["required_fields"].items():
        if name not in rec:
            errors.append(f"{where}: missing field '{name}'")
        elif not isinstance(rec[name], types[type_name]):
            errors.append(f"{where}: field '{name}' must be {type_name}")
    extra = set(rec) - set(schema["required_fields"])
    if extra:
        errors.append(f"{where}: unexpected field(s) {sorted(extra)}")
    if errors:
        return errors, warnings  # later checks assume a well-formed record

    for name, allowed in schema["labels"].items():
        if rec[name] not in allowed:
            errors.append(f"{where}: '{rec[name]}' is not a valid {name} (allowed: {', '.join(allowed)})")

    text = rec["text"]
    if not text.strip():
        errors.append(f"{where}: text is empty")
    elif text != text.strip():
        errors.append(f"{where}: text has leading or trailing spaces")
    if len(text) > schema["max_text_length"]:
        errors.append(f"{where}: text longer than {schema['max_text_length']} characters")

    prefix = schema["id_prefix_by_language"].get(rec["language"])
    if prefix and not rec["id"].startswith(prefix):
        errors.append(f"{where}: id '{rec['id']}' should start with '{prefix}' for language '{rec['language']}'")

    allowed_sent = schema["consistency_rules"]["intent_allowed_sentiments"].get(rec["intent"])
    if allowed_sent and rec["sentiment"] not in allowed_sent:
        errors.append(
            f"{where}: intent '{rec['intent']}' requires sentiment in {allowed_sent}, got '{rec['sentiment']}'"
        )

    if (rec["ambiguous"] or rec["language"] == "mixed") and not rec["notes"].strip():
        errors.append(f"{where}: notes are required for ambiguous or mixed-language items")

    for label, pattern in PII_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"{where}: text looks like it contains a {label}")

    if rec["language"] in FUNCTION_WORDS:
        guess, scores = guess_language(text)
        if guess and guess != rec["language"]:
            warnings.append(
                f"{where}: labeled '{rec['language']}' but function words suggest '{guess}' {scores}"
            )
    return errors, warnings


def validate_file(data_path: Path, schema_path: Path) -> ValidationResult:
    result = ValidationResult()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not data_path.is_file():
        result.errors.append(f"data file not found: {data_path}")
        return result

    seen_ids: dict[str, int] = {}
    seen_texts: dict[str, int] = {}
    with data_path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            where = f"line {line_no}"
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                result.errors.append(f"{where}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(rec, dict):
                result.errors.append(f"{where}: each line must be a JSON object")
                continue
            if isinstance(rec.get("id"), str):
                where = f"line {line_no} ({rec['id']})"

            errors, warnings = validate_record(rec, schema, where)
            result.errors += errors
            result.warnings += warnings

            if isinstance(rec.get("id"), str):
                if rec["id"] in seen_ids:
                    result.errors.append(f"{where}: duplicate id (first seen on line {seen_ids[rec['id']]})")
                seen_ids.setdefault(rec["id"], line_no)
            if isinstance(rec.get("text"), str):
                key = " ".join(rec["text"].lower().split())
                if key in seen_texts:
                    result.errors.append(f"{where}: duplicate text (first seen on line {seen_texts[key]})")
                seen_texts.setdefault(key, line_no)
            if not errors:
                result.records.append(rec)
    return result


def distribution_report(result: ValidationResult, schema: dict) -> str:
    recs = result.records
    lines = [
        "# Validation Report",
        "",
        f"- Valid records: **{len(recs)}**",
        f"- Errors: **{len(result.errors)}**",
        f"- Warnings: **{len(result.warnings)}**",
        f"- Items marked ambiguous: **{sum(r['ambiguous'] for r in recs)}**",
        "",
    ]
    for name, allowed in schema["labels"].items():
        counts = Counter(r[name] for r in recs)
        lines += [f"## {name}", "", "| Label | Count | Share |", "|---|---:|---:|"]
        for label in allowed:
            n = counts.get(label, 0)
            share = f"{n / len(recs):.0%}" if recs else "0%"
            lines.append(f"| `{label}` | {n} | {share} |")
        lines.append("")

    lines += ["## Sentiment by language", "", "| Language | " + " | ".join(schema["labels"]["sentiment"]) + " |",
              "|---|" + "---:|" * len(schema["labels"]["sentiment"])]
    for lang in schema["labels"]["language"]:
        row = Counter(r["sentiment"] for r in recs if r["language"] == lang)
        lines.append(f"| `{lang}` | " + " | ".join(str(row.get(s, 0)) for s in schema["labels"]["sentiment"]) + " |")
    lines.append("")

    if result.errors:
        lines += ["## Errors", ""] + [f"- {e}" for e in result.errors] + [""]
    if result.warnings:
        lines += ["## Warnings", ""] + [f"- {w}" for w in result.warnings] + [""]
    return "\n".join(lines)


def export_csv(records: list[dict], path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for rec in records:
            # Write booleans as true/false, matching the JSONL file.
            writer.writerow({k: str(v).lower() if isinstance(v, bool) else v for k, v in rec.items()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate multilingual annotations.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--report", type=Path, help="write a Markdown report to this path")
    parser.add_argument("--csv", type=Path, help="export valid records to this CSV path")
    args = parser.parse_args(argv)

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    result = validate_file(args.data, args.schema)

    for message in result.errors:
        print(f"ERROR   {message}")
    for message in result.warnings:
        print(f"WARNING {message}")
    print(f"\n{len(result.records)} valid records, {len(result.errors)} errors, {len(result.warnings)} warnings")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(distribution_report(result, schema), encoding="utf-8")
        print(f"report written to {args.report}")
    if args.csv and result.ok:
        export_csv(result.records, args.csv, list(schema["required_fields"]))
        print(f"CSV written to {args.csv}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
