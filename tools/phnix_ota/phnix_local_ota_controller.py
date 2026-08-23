#!/usr/bin/env python3
"""Host-side controller for a local PHNIX mainboard OTA via an LTE modem.

The controller is intentionally fail-closed.  Without --execute it performs
only read-only preflight checks.  Runtime modification is delegated to a
build-specific helper that must be verified separately on the real modem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


EXPECTED_SIZE = 287_598
EXPECTED_MD5 = "CEB6A4BF386FF644E23E410023E74673"
EXPECTED_SOFTWARE_CODE = "82400644"
EXPECTED_SOFTWARE_VERSION = "0033"
EXPECTED_SSID = "0063"
EXPECTED_BUILD_ID = "af4dcae12639bedce833ee5efa5da009777b6319"
EXPECTED_SERVICE_SHA256 = "7C573431F0A67620D473419644A83A4F4DC04B8A91BDE5923C74A63BA1EAEDB7"

REMOTE_SERVICE = "/data/phnixIot4G"
REMOTE_CACHE = "/cache/phnixIot_device_OTA"
REMOTE_INFO = "/data/phnixIot_device_OTA_INFO"
REMOTE_STATISTICS = "/data/phnixIot_device_statisic"
REMOTE_HELPER = "/data/phnix_ota_runtime_hook"
REMOTE_STAGE_DIR = "/data/phnix_local_ota"
REMOTE_FIRMWARE = f"{REMOTE_STAGE_DIR}/FW3.3.bin"
REMOTE_COMMAND = f"{REMOTE_STAGE_DIR}/ota-command.json"
REMOTE_STATUS = "/tmp/phnix_ota_status.json"
REMOTE_HTTP_PID = "/tmp/phnix_ota_httpd.pid"
DEFAULT_FIRMWARE_URL = "http://127.0.0.1:8081/FW3.3.bin"


class OtaError(RuntimeError):
    pass


@dataclass
class OtaInfo:
    crc_ok: bool
    stored_crc: int
    calculated_crc: int
    system_version: str
    md5: str
    software_code: str
    software_version: str
    offset: int
    length: int


def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return (~crc) & 0xFFFF


def c_string(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("ascii", errors="replace")


def parse_ota_info(raw: bytes) -> OtaInfo:
    if len(raw) != 220:
        raise OtaError(f"OTA_INFO has {len(raw)} bytes; expected 220")
    stored = int.from_bytes(raw[0:4], "little")
    calculated = crc16_x25(raw[4:220])
    return OtaInfo(
        crc_ok=stored == calculated,
        stored_crc=stored,
        calculated_crc=calculated,
        system_version=c_string(raw[28:34]),
        md5=c_string(raw[165:198]),
        software_code=c_string(raw[198:207]),
        software_version=c_string(raw[207:212]),
        offset=int.from_bytes(raw[212:216], "little"),
        length=int.from_bytes(raw[216:220], "little"),
    )


class Adb:
    def __init__(self, executable: str, serial: str | None):
        self.base = [executable]
        if serial:
            self.base += ["-s", serial]

    def run(self, *args: str, binary: bool = False, check: bool = True):
        completed = subprocess.run(
            [*self.base, *args], capture_output=True,
            text=not binary, check=False,
        )
        if check and completed.returncode != 0:
            stderr = completed.stderr if not binary else completed.stderr.decode(errors="replace")
            raise OtaError(f"adb {' '.join(args)} failed: {stderr.strip()}")
        return completed.stdout

    def shell(self, command: str, check: bool = True) -> str:
        return self.run("shell", command, check=check).strip()

    def read_file(self, remote: str) -> bytes:
        # The modem's older adbd closes `exec-out`; on a Linux Pi, shell/cat
        # still preserves the binary stream byte-for-byte.
        return self.run("shell", "cat", remote, binary=True)


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def command_payload(firmware_url: str) -> dict:
    return {
        "cmd": "CMD_OTA",
        "code": "0033",
        "param": {
            "softwareCode": EXPECTED_SOFTWARE_CODE,
            "softwareVer": "V3.3",
            "ssid": EXPECTED_SSID,
            "fileMD5": EXPECTED_MD5,
            "fileSize": EXPECTED_SIZE,
            "otaFileDownloadAddr": firmware_url,
        },
    }


def print_event(event: str, **fields) -> None:
    record = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event, **fields}
    print(json.dumps(record, ensure_ascii=False), flush=True)


def preflight(adb: Adb, firmware: Path, require_helper: bool) -> dict:
    checks: dict[str, object] = {}
    if not firmware.is_file():
        raise OtaError(f"firmware not found: {firmware}")
    checks["firmware_size"] = firmware.stat().st_size
    checks["firmware_md5"] = file_md5(firmware)
    checks["firmware_ok"] = (
        checks["firmware_size"] == EXPECTED_SIZE
        and checks["firmware_md5"] == EXPECTED_MD5
    )

    checks["adb_state"] = adb.run("get-state").strip()
    checks["service_pid"] = adb.shell("pidof phnixIot4G || true")
    checks["service_path"] = adb.shell(
        "p=$(pidof phnixIot4G | awk '{print $1}'); "
        "test -n \"$p\" && readlink /proc/$p/exe || true"
    )
    checks["service_sha256"] = adb.shell(
        f"sha256sum {REMOTE_SERVICE} | awk '{{print $1}}'"
    ).upper()
    checks["service_binary_ok"] = checks["service_sha256"] == EXPECTED_SERVICE_SHA256
    checks["watchdog_pids"] = adb.shell(
        "ps | awk '$4 == \"{helloworld}\" {print $1}'"
    )
    checks["gdb_present"] = adb.shell("test -x /usr/bin/gdb; echo $?") == "0"
    checks["httpd_present"] = "httpd" in adb.shell("busybox --list") .splitlines()
    checks["mqtt_connection"] = adb.shell(
        "netstat -nt 2>/dev/null | awk '$4 ~ /:1883$/ || $5 ~ /:1883$/ {print}'"
    )
    checks["storage"] = adb.shell("df -k /cache /data 2>/dev/null || true")
    checks["info_writable"] = adb.shell(f"test -r {REMOTE_INFO} && test -w {REMOTE_INFO}; echo $?") == "0"
    checks["statistics_writable"] = adb.shell(
        f"test -r {REMOTE_STATISTICS} && test -w {REMOTE_STATISTICS}; echo $?"
    ) == "0"
    checks["helper_present"] = adb.shell(f"test -x {REMOTE_HELPER}; echo $?") == "0"
    checks["ota_info"] = asdict(parse_ota_info(adb.read_file(REMOTE_INFO)))
    checks["no_active_resume"] = (
        checks["ota_info"]["offset"] == 0 and checks["ota_info"]["length"] == 0
    )

    failures = []
    if not checks["firmware_ok"]:
        failures.append("firmware size/MD5 mismatch")
    if checks["adb_state"] != "device":
        failures.append("ADB device is not ready")
    if not checks["service_pid"]:
        failures.append("original phnixIot4G service is not running")
    if checks["service_path"] != REMOTE_SERVICE:
        failures.append(f"unexpected service executable: {checks['service_path']!r}")
    if not checks["service_binary_ok"]:
        failures.append("original service SHA256/build does not match the verified binary")
    if not checks["watchdog_pids"]:
        failures.append("helloworld service watchdog was not found")
    if not checks["gdb_present"] or not checks["httpd_present"]:
        failures.append("required modem gdb/busybox-httpd support is missing")
    if not checks["info_writable"] or not checks["statistics_writable"]:
        failures.append("persistent state files are not readable/writable")
    if not checks["ota_info"]["crc_ok"]:
        failures.append("OTA_INFO CRC is invalid")
    if not checks["no_active_resume"]:
        failures.append("an existing OTA/resume session is active")
    if require_helper and not checks["helper_present"]:
        failures.append("verified runtime hook helper is missing")
    checks["ok"] = not failures
    checks["failures"] = failures
    return checks


def save_remote_state(adb: Adb, state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=False)
    (state_dir / "phnixIot_device_OTA_INFO").write_bytes(adb.read_file(REMOTE_INFO))
    (state_dir / "phnixIot_device_statisic").write_bytes(adb.read_file(REMOTE_STATISTICS))
    manifest = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ota_info": asdict(parse_ota_info((state_dir / "phnixIot_device_OTA_INFO").read_bytes())),
    }
    (state_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def stage_firmware(adb: Adb, firmware: Path) -> None:
    adb.shell(f"mkdir -p {REMOTE_STAGE_DIR}")
    adb.run("push", str(firmware), REMOTE_FIRMWARE)
    remote_md5 = adb.shell(f"md5sum {REMOTE_FIRMWARE} | awk '{{print $1}}'").upper()
    if remote_md5 != EXPECTED_MD5:
        raise OtaError(f"staged modem firmware MD5 mismatch: {remote_md5}")
    adb.shell(
        f"test -f {REMOTE_HTTP_PID} && kill $(cat {REMOTE_HTTP_PID}) 2>/dev/null || true; "
        f"busybox httpd -p 127.0.0.1:8081 -h {REMOTE_STAGE_DIR}; "
        f"pgrep -f '^busybox httpd -p 127.0.0.1:8081 ' | awk '{{print $1}}' > {REMOTE_HTTP_PID}"
    )
    served_md5 = adb.shell(
        f"curl -fsS {DEFAULT_FIRMWARE_URL} | md5sum | awk '{{print $1}}'"
    ).upper()
    if served_md5 != EXPECTED_MD5:
        raise OtaError(f"modem localhost HTTP firmware MD5 mismatch: {served_md5}")
    print_event("firmware-staged", remote=REMOTE_FIRMWARE, url=DEFAULT_FIRMWARE_URL)


def stop_local_http(adb: Adb) -> None:
    adb.shell(
        f"test -f {REMOTE_HTTP_PID} && kill $(cat {REMOTE_HTTP_PID}) 2>/dev/null || true; "
        f"rm -f {REMOTE_HTTP_PID}",
        check=False,
    )


def remote_status(adb: Adb) -> dict:
    status_text = adb.shell(f"cat {REMOTE_STATUS} 2>/dev/null || true")
    hook = json.loads(status_text) if status_text else {"state": "hook-not-running"}
    info = asdict(parse_ota_info(adb.read_file(REMOTE_INFO)))
    return {"hook": hook, "ota_info": info}


def run_update(args, adb: Adb) -> None:
    # A dry-run must remain useful before the build-specific modem helper exists.
    checks = preflight(adb, args.firmware, require_helper=args.execute)
    print_event("preflight", **checks)
    if not checks["ok"]:
        raise OtaError("preflight failed: " + "; ".join(checks["failures"]))
    if not args.execute:
        print_event("dry-run-complete", message="No modem or bus state was changed")
        return

    state_dir = args.state_dir / time.strftime("%Y%m%d-%H%M%S")
    save_remote_state(adb, state_dir)
    print_event("state-backed-up", directory=str(state_dir))
    stage_firmware(adb, args.firmware)

    payload = command_payload(args.firmware_url)
    with tempfile.TemporaryDirectory() as temp_dir:
        command_file = Path(temp_dir) / "ota-command.json"
        command_file.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        adb.run("push", str(command_file), REMOTE_COMMAND)

    helper_command = (
        f"{REMOTE_HELPER} run --build-id {EXPECTED_BUILD_ID} "
        f"--command {REMOTE_COMMAND} --status {REMOTE_STATUS} "
        "--allow-publish 0023,0053,0083"
    )
    print_event("hook-start", allowed_publish=["0023", "0053", "0083"])
    helper = subprocess.Popen([*adb.base, "shell", helper_command])

    phase_started = time.monotonic()
    previous_phase = None
    last_offset = -1
    last_progress = time.monotonic()
    safe_terminal = False
    guarded_hold = False
    try:
        while True:
            status = remote_status(adb)
            hook = status["hook"]
            info = status["ota_info"]
            print_event("status", **status)
            if not info["crc_ok"]:
                raise OtaError("OTA_INFO CRC became invalid")
            if info["length"] and info["offset"] > info["length"]:
                raise OtaError("OTA_INFO offset exceeds firmware length")
            if (
                last_offset >= 0
                and info["offset"] < last_offset
                and hook.get("phase") not in {"success", "failed"}
            ):
                raise OtaError("OTA_INFO offset moved backwards unexpectedly")
            if info["offset"] != last_offset:
                last_offset = info["offset"]
                last_progress = time.monotonic()

            phase = hook.get("phase", "unknown")
            if phase != previous_phase:
                previous_phase = phase
                phase_started = time.monotonic()
                print_event("phase-change", phase=phase)
            if phase == "c5a8":
                metadata_ok = (
                    info["md5"] == EXPECTED_MD5
                    and info["software_code"] == EXPECTED_SOFTWARE_CODE
                    and info["software_version"] == EXPECTED_SOFTWARE_VERSION
                    and info["length"] == EXPECTED_SIZE
                    and info["offset"] >= 0
                )
                if not metadata_ok:
                    raise OtaError("persisted OTA metadata is not valid for FW3.3 before C5A8")
            if hook.get("terminal") is True:
                safe_terminal = phase in {"success", "failed", "parser-rejected"}
                if phase == "success":
                    print_event("complete", offset=info["offset"], length=info["length"])
                    return
                raise OtaError(f"terminal OTA state: {phase}")
            if helper.poll() is not None:
                raise OtaError(f"runtime helper exited unexpectedly with code {helper.returncode}")

            now = time.monotonic()
            phase_limit = {
                "c350": args.handshake_timeout,
                "c357": args.handshake_timeout,
                "c5a8": args.block_timeout,
            }.get(phase, args.start_timeout)
            reference = last_progress if phase == "c5a8" else phase_started
            if now - reference > phase_limit:
                raise OtaError(f"phase watchdog expired in {phase}")
            time.sleep(args.poll_interval)
    except BaseException:
        if not safe_terminal:
            adb.shell(f"{REMOTE_HELPER} hold --status {REMOTE_STATUS}", check=False)
            guarded_hold = True
            print_event(
                "guarded-hold",
                message="Active OTA was frozen fail-closed; cloud and watchdog guards remain active",
            )
        raise
    finally:
        if safe_terminal and helper.poll() is None:
            adb.shell(f"{REMOTE_HELPER} stop --status {REMOTE_STATUS}", check=False)
            try:
                helper.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print_event("warning", message="runtime helper did not exit within 10 seconds")
        if safe_terminal:
            stop_local_http(adb)
            print_event("hook-stopped")
        elif guarded_hold:
            print_event("manual-recovery-required", status=REMOTE_STATUS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adb", default=shutil.which("adb") or "adb")
    parser.add_argument("--serial")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--firmware", type=Path, required=True)

    sub.add_parser("preflight", parents=[common])
    sub.add_parser("status")
    run = sub.add_parser("run", parents=[common])
    run.add_argument("--firmware-url", default=DEFAULT_FIRMWARE_URL)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--state-dir", type=Path, default=Path("phnix-ota-state"))
    run.add_argument("--poll-interval", type=float, default=2.0)
    run.add_argument("--start-timeout", type=float, default=60.0)
    run.add_argument("--handshake-timeout", type=float, default=20.0)
    run.add_argument("--block-timeout", type=float, default=25.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    adb = Adb(args.adb, args.serial)
    try:
        if args.command == "preflight":
            result = preflight(adb, args.firmware, require_helper=False)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["ok"] else 1
        if args.command == "status":
            print(json.dumps(remote_status(adb), indent=2, ensure_ascii=False))
            return 0
        run_update(args, adb)
        return 0
    except (OtaError, OSError, json.JSONDecodeError) as error:
        print_event("error", message=str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
