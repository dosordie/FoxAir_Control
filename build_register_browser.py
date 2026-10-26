"""Generiert die öffentliche Registerliste aus den drei FoxAir-Control-JSON-Dateien."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/FAQ/assets/register-browser/registers.json"
FIELDS = (
    "name", "code", "block", "group", "function", "mode", "type", "unit",
    "firmware", "description", "notes", "note", "app_label", "value_map",
    "bit_map", "bit_descriptions", "range", "default", "write_allowed",
    "virtual", "namespace", "source_slave", "source_register", "main_aliases",
    "raw_format", "persistence", "interface", "ui_visibility",
)
KNOWLEDGE_FIELDS = ("description", "knowledge", "notes", "note", "range", "default")

def load(name):
    obj = json.loads((ROOT / "data" / name).read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError("Erwartetes JSON-Objekt fehlt: " + name)
    return obj

def clean(value):
    if isinstance(value, (str, float, int, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [clean(v) for v in value][:200]
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items() if not str(k).startswith("_")}
    return str(value)

def access(entry, virtual):
    if virtual:
        return "Virtuell / nicht direkt lesbar"
    if entry.get("write_allowed") is False:
        return "Nur lesen"
    mode = str(entry.get("mode", "")).lower()
    if "w" in mode and ("r" in mode or "/" in mode):
        return "Lesen / Schreiben"
    if "write" in mode and "read" not in mode:
        return "Schreiben"
    return "Nur lesen"

def main():
    main_data = load("foxair_phnix_registers.json")
    display_data = load("foxair_phnix_display_registers.json")
    knowledge = load("foxair_phnix_knowledge.json")
    records = []
    keys = set()
    for namespace, data in (("main", main_data), ("display", display_data)):
        for raw_id, entry in data.items():
            if not raw_id.isdecimal() or not isinstance(entry, dict):
                continue
            virtual = namespace == "display" and entry.get("virtual") is True
            category = "virtual" if virtual else namespace
            key = (category, int(raw_id))
            if key in keys:
                raise ValueError("Register doppelt: " + str(key))
            keys.add(key)
            row = {"id": int(raw_id), "category": category}
            row.update({field: clean(entry[field]) for field in FIELDS
                        if field in entry and entry[field] is not None and entry[field] != ""})
            row["access"] = access(entry, virtual)
            if virtual:
                row["virtual"] = True
            extra = knowledge.get(raw_id, {}) if namespace == "main" else {}
            if isinstance(extra, dict):
                supplemental = {field: clean(extra[field]) for field in KNOWLEDGE_FIELDS
                                if field in extra and extra[field] not in (None, "")}
                if supplemental:
                    row["knowledge"] = supplemental
            records.append(row)
    records.sort(key=lambda row: (row["id"], row["category"]))
    counts = Counter(row["category"] for row in records)
    if len(records) < 850 or counts["main"] < 600 or counts["display"] < 150:
        raise ValueError("Registerbestand unplausibel: " + str(dict(counts)))
    data = {
        "schema": 1,
        "meta": {"total": len(records), "main": counts["main"],
                 "display": counts["display"], "virtual": counts["virtual"],
                 "knowledge": sum(bool(row.get("knowledge")) for row in records)},
        "registers": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("Register-Browser:", data["meta"])

if __name__ == "__main__":
    main()
