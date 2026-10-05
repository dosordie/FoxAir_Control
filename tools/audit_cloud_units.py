"""Audit confirmed WarmLink mappings against the current local register map."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud.metadata import audit_cloud_units
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS


if __name__ == "__main__":
    report = audit_cloud_units(WARMLINK_CLOUD_CODE_HINTS)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(bool(report["conflicts"]))
