#!/usr/bin/env python3
"""Deterministic ADB-compatible simulator for the PHNIX OTA controller."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path


EXPECTED_SIZE = 287_598
EXPECTED_MD5 = "CEB6A4BF386FF644E23E410023E74673"
EXPECTED_SERVICE_SHA256 = "7c573431f0a67620d473419644a83a4f4dc04b8a91bde5923c74a63ba1eaedb7"
DEFAULT_HOME = Path.home() / ".local/share/phnix-ota-simulator"
SCENARIOS = {
    "success", "parser-rejected", "crc-error", "metadata-mismatch",
    "offset-backwards", "offset-overflow", "stall-c350", "stall-c5a8",
    "helper-exit", "success-without-step12",
}


def sim_home() -> Path:
    return Path(os.environ.get("PHNIX_OTA_SIM_HOME", DEFAULT_HOME))


def root_path(remote: str) -> Path:
    return sim_home() / "root" / remote.lstrip("/")


def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return (~crc) & 0xFFFF


def make_ota_info(*, offset: int = 0, length: int = 0,
                  md5: str = "", code: str = "", version: str = "",
                  valid_crc: bool = True) -> bytes:
    data = bytearray(220)
    data[28:34] = b"V1.0\0\0"
    data[165:198] = md5.encode()[:32].ljust(33, b"\0")
    data[198:207] = code.encode()[:8].ljust(9, b"\0")
    data[207:212] = version.encode()[:4].ljust(5, b"\0")
    data[212:216] = offset.to_bytes(4, "little")
    data[216:220] = length.to_bytes(4, "little")
    crc = crc16_x25(data[4:])
    if not valid_crc:
        crc ^= 0xFFFF
    data[:4] = crc.to_bytes(4, "little")
    return bytes(data)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    temp.replace(path)


def config() -> dict:
    path = sim_home() / "config.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def reset_state(scenario: str) -> None:
    home = sim_home()
    root = home / "root"
    if root.exists():
        shutil.rmtree(root)
    for directory in ("data", "cache", "tmp", "usr/bin"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    root_path("/data/phnixIot4G").write_text("simulated verified service\n", encoding="utf-8")
    root_path("/data/phnixIot_device_statisic").write_bytes(bytes(256))
    root_path("/data/phnixIot_device_OTA_INFO").write_bytes(make_ota_info())
    root_path("/data/phnix_ota_runtime_hook").write_text("simulated runtime hook\n", encoding="utf-8")
    write_json(home / "config.json", {"scenario": scenario})
    write_json(home / "runtime.json", {
        "running": False, "httpd": False, "held": False,
        "cloud_blocked": False, "watchdogs_paused": False,
    })
    root_path("/tmp/phnix_ota_status.json").unlink(missing_ok=True)


def terminate_helper() -> None:
    pid_file = root_path("/tmp/phnix_ota_sim_helper.pid")
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        if b"phnix_ota_simulator.py" in cmdline:
            os.kill(pid, 15)
    except (OSError, ValueError):
        pass
    pid_file.unlink(missing_ok=True)


def require_started() -> None:
    if not (sim_home() / "started").exists():
        print("error: PHNIX OTA simulator is stopped", file=sys.stderr)
        raise SystemExit(1)


def admin(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="PHNIX OTA VM simulator")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--scenario", choices=sorted(SCENARIOS), default="success")
    reset = sub.add_parser("reset")
    reset.add_argument("--scenario", choices=sorted(SCENARIOS), default="success")
    scenario = sub.add_parser("scenario")
    scenario.add_argument("name", choices=sorted(SCENARIOS))
    sub.add_parser("stop")
    sub.add_parser("status")
    args = parser.parse_args(argv)

    home = sim_home()
    home.mkdir(parents=True, exist_ok=True)
    if args.command == "start":
        terminate_helper()
        reset_state(args.scenario)
        (home / "started").touch()
    elif args.command == "reset":
        was_started = (home / "started").exists()
        terminate_helper()
        reset_state(args.scenario)
        if was_started:
            (home / "started").touch()
    elif args.command == "scenario":
        if not (home / "started").exists():
            print("Simulator is stopped; use start first", file=sys.stderr)
            return 1
        terminate_helper()
        reset_state(args.name)
        (home / "started").touch()
    elif args.command == "stop":
        terminate_helper()
        (home / "started").unlink(missing_ok=True)
        runtime = home / "runtime.json"
        if runtime.exists():
            state = json.loads(runtime.read_text(encoding="utf-8"))
            state.update(running=False, httpd=False, held=False,
                         cloud_blocked=False, watchdogs_paused=False)
            write_json(runtime, state)
    state = {
        "started": (home / "started").exists(),
        "scenario": config().get("scenario"),
        "home": str(home),
    }
    runtime = home / "runtime.json"
    if runtime.exists():
        state.update(json.loads(runtime.read_text(encoding="utf-8")))
    print(json.dumps(state, indent=2))
    return 0


def set_status(phase: str, terminal: bool = False, **extra) -> None:
    write_json(root_path("/tmp/phnix_ota_status.json"), {
        "phase": phase, "terminal": terminal, **extra,
    })


def update_info(offset: int, length: int = EXPECTED_SIZE, *, valid_crc: bool = True,
                bad_metadata: bool = False) -> None:
    root_path("/data/phnixIot_device_OTA_INFO").write_bytes(make_ota_info(
        offset=offset, length=length,
        md5="0" * 32 if bad_metadata else EXPECTED_MD5,
        code="BAD" if bad_metadata else "82400644",
        version="9999" if bad_metadata else "0033",
        valid_crc=valid_crc,
    ))


def runtime_state(**updates) -> None:
    path = sim_home() / "runtime.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update(updates)
    write_json(path, state)


def helper_run() -> int:
    scenario = config().get("scenario", "success")
    pid_file = root_path("/tmp/phnix_ota_sim_helper.pid")
    pid_file.write_text(str(os.getpid()))
    runtime_state(running=True, cloud_blocked=True, watchdogs_paused=True, held=False)
    set_status("parser-injection", armed=True, active=False)
    time.sleep(0.25)
    if scenario == "parser-rejected":
        set_status("parser-rejected", True, armed=False, active=False)
        runtime_state(running=False, cloud_blocked=False, watchdogs_paused=False)
        pid_file.unlink(missing_ok=True)
        return 0
    if scenario == "helper-exit":
        pid_file.unlink(missing_ok=True)
        return 23
    set_status("accepted", armed=True, active=True)
    time.sleep(0.25)
    set_status("c350")
    if scenario == "stall-c350":
        return wait_for_hold(pid_file)
    time.sleep(0.25)
    set_status("c357")
    time.sleep(0.25)
    update_info(0, bad_metadata=scenario == "metadata-mismatch")
    set_status("c5a8")
    if scenario == "crc-error":
        time.sleep(0.25)
        update_info(64_000, valid_crc=False)
    elif scenario == "offset-overflow":
        time.sleep(0.25)
        update_info(EXPECTED_SIZE + 1)
    elif scenario == "stall-c5a8":
        update_info(32_000)
        return wait_for_hold(pid_file)
    else:
        for offset in (32_000, 96_000, 160_000):
            time.sleep(0.25)
            update_info(offset)
        if scenario == "offset-backwards":
            time.sleep(0.25)
            update_info(64_000)
        else:
            time.sleep(0.25)
            update_info(EXPECTED_SIZE)
            board_step = 11 if scenario == "success-without-step12" else 12
            set_status("success", True, board_ota_step=board_step)
            if board_step == 12:
                runtime_state(running=False, cloud_blocked=False, watchdogs_paused=False)
            pid_file.unlink(missing_ok=True)
            return 0
    return wait_for_hold(pid_file)


def wait_for_hold(pid_file: Path) -> int:
    while True:
        time.sleep(0.1)
        path = sim_home() / "runtime.json"
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")).get("held"):
            pid_file.unlink(missing_ok=True)
            return 0


def shell(command: str) -> tuple[int, bytes]:
    if command.startswith("cat ") and " " not in command[4:]:
        path = root_path(command[4:])
        return (0, path.read_bytes()) if path.exists() else (1, b"")
    if command == "pidof phnixIot4G || true":
        return 0, b"4100\n"
    if command.startswith("p=$(pidof phnixIot4G"):
        return 0, b"/data/phnixIot4G\n"
    if command.startswith("sha256sum /data/phnixIot4G"):
        return 0, (EXPECTED_SERVICE_SHA256 + "\n").encode()
    if command.startswith("ps | awk"):
        return 0, b"4001\n4002\n"
    if command == "test -x /usr/bin/gdb; echo $?":
        return 0, b"0\n"
    if command == "busybox --list":
        return 0, b"httpd\nmd5sum\n"
    if command.startswith("netstat -nt"):
        return 0, b"tcp 0 0 10.0.0.2:45100 47.91.78.162:1883 ESTABLISHED\n"
    if command.startswith("df -k"):
        return 0, b"Filesystem 1K-blocks Used Available Use% Mounted on\nsim 1048576 1 1048575 1% /data\n"
    if command.startswith("test -r /data/phnixIot_device_") or command.startswith("test -x /data/phnix_ota_runtime_hook"):
        return 0, b"0\n"
    if command.startswith("mkdir -p /data/phnix_local_ota"):
        root_path("/data/phnix_local_ota").mkdir(parents=True, exist_ok=True)
        return 0, b""
    if command.startswith("md5sum /data/phnix_local_ota/FW3.3.bin"):
        digest = hashlib.md5(root_path("/data/phnix_local_ota/FW3.3.bin").read_bytes()).hexdigest()
        return 0, (digest + "\n").encode()
    if "busybox httpd -p 127.0.0.1:8081" in command:
        runtime_state(httpd=True)
        root_path("/tmp/phnix_ota_httpd.pid").write_text("4200\n")
        return 0, b""
    if command.startswith("curl -fsS http://127.0.0.1:8081/FW3.3.bin"):
        digest = hashlib.md5(root_path("/data/phnix_local_ota/FW3.3.bin").read_bytes()).hexdigest()
        return 0, (digest + "\n").encode()
    if command.startswith("cat /tmp/phnix_ota_status.json"):
        path = root_path("/tmp/phnix_ota_status.json")
        return 0, path.read_bytes() if path.exists() else b""
    if command.startswith("/data/phnix_ota_runtime_hook run "):
        return helper_run(), b""
    if command.startswith("/data/phnix_ota_runtime_hook hold "):
        runtime_state(held=True, running=False)
        set_status("guarded-hold", False, recovery_required=True)
        return 0, b""
    if command.startswith("/data/phnix_ota_runtime_hook stop "):
        runtime_state(running=False, held=False, cloud_blocked=False, watchdogs_paused=False)
        return 0, b""
    if "rm -f /tmp/phnix_ota_httpd.pid" in command:
        runtime_state(httpd=False)
        root_path("/tmp/phnix_ota_httpd.pid").unlink(missing_ok=True)
        return 0, b""
    return 1, f"unsupported simulated shell command: {command}\n".encode()


def adb(argv: list[str]) -> int:
    require_started()
    if len(argv) >= 2 and argv[0] == "-s":
        argv = argv[2:]
    if argv == ["get-state"]:
        print("device")
        return 0
    if len(argv) == 3 and argv[0] == "push":
        destination = root_path(argv[2])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(argv[1], destination)
        print(f"{argv[1]}: 1 file pushed")
        return 0
    if argv and argv[0] == "shell":
        command = " ".join(argv[1:])
        try:
            code, output = shell(command)
        except KeyboardInterrupt:
            return 130
        sys.stdout.buffer.write(output)
        return code
    print("unsupported simulated adb command: " + " ".join(argv), file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "adb":
        return adb(sys.argv[2:])
    return admin(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
