#!/usr/bin/env python3
"""Audit FoxAir PHNIX register mappings without changing source mappings."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "data" / "foxair_phnix_registers.json"
DISPLAY_PATH = REPO_ROOT / "data" / "foxair_phnix_display_registers.json"

AUDIT_ALL_PATH = REPO_ROOT / "register_mapping_audit_all.csv"
DUPLICATES_PATH = REPO_ROOT / "register_mapping_duplicates.csv"
CONFLICTS_PATH = REPO_ROOT / "register_mapping_conflicts.csv"
SUMMARY_PATH = REPO_ROOT / "register_mapping_audit_summary.txt"

COMPARE_FIELDS = [
    "name",
    "type",
    "unit",
    "mode",
    "function",
    "block",
    "code",
    "value_map",
    "bit_map",
    "notes",
    "note",
    "description",
    "info",
    "source",
    "last_review",
]

CSV_COLUMNS = [
    "register",
    "register_hex",
    "in_main",
    "in_display",
    "main_name",
    "display_name",
    "main_type",
    "display_type",
    "main_unit",
    "display_unit",
    "main_mode",
    "display_mode",
    "main_function",
    "display_function",
    "main_block",
    "display_block",
    "main_code",
    "display_code",
    "main_value_map",
    "display_value_map",
    "main_bit_map",
    "display_bit_map",
    "main_notes",
    "display_notes",
    "differences",
    "classification",
    "remark",
]

RANGES = [
    ("unter 1000", None, 999),
    ("1000–1999", 1000, 1999),
    ("2000–2999", 2000, 2999),
    ("3000–3999", 3000, 3999),
    ("4000–89999", 4000, 89999),
    ("ab 90000", 90000, None),
]


def load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    normalized: dict[str, dict[str, Any]] = {}
    for register, entry in data.items():
        if not isinstance(entry, dict):
            raise TypeError(f"Register {register!r} in {path} must contain a JSON object")
        normalized[str(parse_register(register))] = entry
    return normalized


def parse_register(register: str | int) -> int:
    text = str(register).strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


def normalize_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {str(key): normalize_value(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    return value


def csv_value(value: Any) -> str:
    normalized = normalize_value(value)
    if normalized == "":
        return ""
    if isinstance(normalized, (dict, list)):
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(normalized)


def is_writable(entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    mode = str(normalize_value(entry.get("mode"))).lower()
    function = str(normalize_value(entry.get("function"))).lower()
    mode_writable = "w" in mode or "write" in mode or "schreib" in mode
    function_writable = any(token in function.replace(",", "/").split("/") for token in ("06", "6", "16"))
    return mode_writable or function_writable


def compare_entries(main_entry: dict[str, Any] | None, display_entry: dict[str, Any] | None) -> tuple[str, list[str], str]:
    if main_entry is None:
        return "DISPLAY_ONLY", [], "Register exists only in display mapping."
    if display_entry is None:
        return "MAIN_ONLY", [], "Register exists only in main mapping."

    differences = [
        field
        for field in COMPARE_FIELDS
        if normalize_value(main_entry.get(field)) != normalize_value(display_entry.get(field))
    ]
    if not differences:
        return "IDENTICAL", [], "Relevant fields are identical."

    if is_writable(main_entry) != is_writable(display_entry) and ({"mode", "function"} & set(differences)):
        return "WRITE_PERMISSION_DIFF", differences, "Writable assessment differs based on mode/function."
    return "DIFFERENT", differences, "Relevant fields differ; no source was selected as authoritative."


def build_row(register: str, main: dict[str, Any], display: dict[str, Any]) -> dict[str, str]:
    main_entry = main.get(register)
    display_entry = display.get(register)
    classification, differences, remark = compare_entries(main_entry, display_entry)

    def field(prefix_entry: dict[str, Any] | None, key: str) -> str:
        return csv_value(prefix_entry.get(key)) if prefix_entry else ""

    return {
        "register": register,
        "register_hex": f"0x{int(register):04X}",
        "in_main": "yes" if main_entry is not None else "no",
        "in_display": "yes" if display_entry is not None else "no",
        "main_name": field(main_entry, "name"),
        "display_name": field(display_entry, "name"),
        "main_type": field(main_entry, "type"),
        "display_type": field(display_entry, "type"),
        "main_unit": field(main_entry, "unit"),
        "display_unit": field(display_entry, "unit"),
        "main_mode": field(main_entry, "mode"),
        "display_mode": field(display_entry, "mode"),
        "main_function": field(main_entry, "function"),
        "display_function": field(display_entry, "function"),
        "main_block": field(main_entry, "block"),
        "display_block": field(display_entry, "block"),
        "main_code": field(main_entry, "code"),
        "display_code": field(display_entry, "code"),
        "main_value_map": field(main_entry, "value_map"),
        "display_value_map": field(display_entry, "value_map"),
        "main_bit_map": field(main_entry, "bit_map"),
        "display_bit_map": field(display_entry, "bit_map"),
        "main_notes": field(main_entry, "notes"),
        "display_notes": field(display_entry, "notes"),
        "differences": ",".join(differences),
        "classification": classification,
        "remark": remark,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def range_counts(registers: set[str]) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    numbers = [int(register) for register in registers]
    for label, lower, upper in RANGES:
        counts.append((label, sum((lower is None or number >= lower) and (upper is None or number <= upper) for number in numbers)))
    return counts


def write_summary(rows: list[dict[str, str]], main: dict[str, Any], display: dict[str, Any]) -> None:
    counts = Counter(row["classification"] for row in rows)
    duplicate_rows = [row for row in rows if row["in_main"] == "yes" and row["in_display"] == "yes"]
    write_conflicts = [row for row in rows if row["classification"] == "WRITE_PERMISSION_DIFF"]
    conflict_rows = [row for row in rows if row["classification"] in {"DIFFERENT", "WRITE_PERMISSION_DIFF"}]

    lines = [
        "FoxAir PHNIX Register Mapping Audit",
        "===================================",
        "",
        f"Anzahl Register Hauptmapping: {len(main)}",
        f"Anzahl Register Displaymapping: {len(display)}",
        f"Anzahl nur Hauptmapping: {counts['MAIN_ONLY']}",
        f"Anzahl nur Displaymapping: {counts['DISPLAY_ONLY']}",
        f"Anzahl doppelte Register: {len(duplicate_rows)}",
        f"Anzahl identische doppelte Register: {counts['IDENTICAL']}",
        f"Anzahl unterschiedliche doppelte Register: {counts['DIFFERENT']}",
        f"Anzahl Schreibrechtskonflikte: {counts['WRITE_PERMISSION_DIFF']}",
        "",
        "Liste der betroffenen Register mit Schreibrechtskonflikten:",
    ]
    if write_conflicts:
        lines.extend(f"- {row['register']} ({row['register_hex']}): {row['differences']}" for row in write_conflicts)
    else:
        lines.append("- keine")

    lines.extend(["", "Bereichsübersicht (Union beider Mappings):"])
    for label, count in range_counts(set(main) | set(display)):
        lines.append(f"- {label}: {count}")

    lines.extend(["", "Wichtigste Konflikte (erste 25 numerisch sortiert):"])
    if conflict_rows:
        for row in conflict_rows[:25]:
            lines.append(f"- {row['register']} ({row['classification']}): {row['differences']}")
    else:
        lines.append("- keine")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    main_mapping = load_mapping(MAIN_PATH)
    display_mapping = load_mapping(DISPLAY_PATH)
    registers = sorted(set(main_mapping) | set(display_mapping), key=int)
    rows = [build_row(register, main_mapping, display_mapping) for register in registers]

    write_csv(AUDIT_ALL_PATH, rows)
    write_csv(DUPLICATES_PATH, [row for row in rows if row["in_main"] == "yes" and row["in_display"] == "yes"])
    write_csv(CONFLICTS_PATH, [row for row in rows if row["classification"] in {"DIFFERENT", "WRITE_PERMISSION_DIFF"}])
    write_summary(rows, main_mapping, display_mapping)

    print(f"Wrote {AUDIT_ALL_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {DUPLICATES_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {CONFLICTS_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
