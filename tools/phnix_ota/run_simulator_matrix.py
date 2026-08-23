#!/usr/bin/env python3
"""Run the OTA controller against every deterministic VM scenario."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


EXPECTED = {
    "success": (0, False),
    "parser-rejected": (1, False),
    "crc-error": (1, True),
    "metadata-mismatch": (1, True),
    "offset-backwards": (1, True),
    "offset-overflow": (1, True),
    "stall-c350": (1, True),
    "stall-c5a8": (1, True),
    "helper-exit": (1, True),
    "success-without-step12": (1, True),
}


def run(command: list[str], timeout: float = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", type=Path, default=Path("./phnix-ota-sim"))
    parser.add_argument("--adb", type=Path, default=Path("./phnix-sim-adb"))
    parser.add_argument("--controller", type=Path, default=Path("./phnix_local_ota_controller.py"))
    parser.add_argument("--firmware", type=Path, required=True)
    args = parser.parse_args()
    args.sim = args.sim.resolve()
    args.adb = args.adb.resolve()
    args.controller = args.controller.resolve()
    args.firmware = args.firmware.resolve()
    results = []

    for scenario, (expected_rc, expected_hold) in EXPECTED.items():
        run([str(args.sim), "scenario", scenario])
        with tempfile.TemporaryDirectory(prefix=f"phnix-{scenario}-") as state_dir:
            completed = run([
                str(args.controller), "--adb", str(args.adb), "run",
                "--firmware", str(args.firmware), "--execute",
                "--state-dir", state_dir, "--poll-interval", "0.05",
                "--start-timeout", "3", "--handshake-timeout", "3",
                "--block-timeout", "1",
            ])
        status_result = run([str(args.sim), "status"])
        status = json.loads(status_result.stdout)
        passed = completed.returncode == expected_rc and status.get("held") is expected_hold
        results.append({
            "scenario": scenario,
            "returncode": completed.returncode,
            "held": status.get("held"),
            "passed": passed,
        })
        print(json.dumps(results[-1]), flush=True)

    failures = [item for item in results if not item["passed"]]
    print(json.dumps({"passed": len(results) - len(failures), "total": len(results),
                      "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
