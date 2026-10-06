"""Audit discovery/hints/MAIN mappings, optionally with current normalized rows."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud.mapping_audit import audit_cloud_mappings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, help="JSON list of normalized rows from one current scan")
    args = parser.parse_args()
    rows = json.loads(args.rows.read_text(encoding="utf-8")) if args.rows else None
    report = audit_cloud_mappings(rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(report["errors"]))
