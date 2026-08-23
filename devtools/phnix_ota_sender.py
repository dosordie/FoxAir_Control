#!/usr/bin/env python3
"""Controlled PHNIX mainboard OTA sender.

The default commands only inspect or simulate a firmware transfer.  Physical
I/O is reachable exclusively through the explicit ``send`` command plus a
confirmation phrase that includes the firmware SHA-256.

This tool implements the LTE-to-mainboard side of the protocol reconstructed
from phnixIot4G.  It never contacts MQTT, HTTP or any cloud service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Optional, Protocol


UNIT = 0x63
FC_WRITE_MULTIPLE = 0x10
REG_C350 = 0xC350
REG_C357 = 0xC357
REG_C36E = 0xC36E
REG_C371 = 0xC371
REG_C37B = 0xC37B
REG_C5A8 = 0xC5A8
DEFAULT_BLOCK_SIZE = 168
LIVE_CONFIRM_PREFIX = "PHNIX-LIVE-TRANSFER"


class ProtocolError(RuntimeError):
    """The peer response does not match the expected PHNIX OTA protocol."""


def crc16_modbus_value(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def with_crc(data: bytes) -> bytes:
    crc = crc16_modbus_value(data)
    return data + bytes((crc & 0xFF, crc >> 8))


def has_valid_crc(frame: bytes) -> bool:
    return len(frame) >= 4 and crc16_modbus_value(frame[:-2]) == int.from_bytes(
        frame[-2:], "little"
    )


def normalize_version(version: str) -> str:
    """Convert cloud spelling V3.4 to the four-byte C350 spelling 0034."""
    raw = version.strip()
    if len(raw) == 4 and raw.isdigit():
        return raw
    if len(raw) == 4 and raw[0].upper() == "V" and raw[1].isdigit() and raw[2] == "." and raw[3].isdigit():
        return f"00{raw[1]}{raw[3]}"
    raise ValueError("version must look like V3.4 or 0034")


def parse_ssid(value: str) -> int:
    raw = value.strip().lower()
    number = int(raw, 16) if raw.startswith("0x") else int(raw, 16)
    if not 0 <= number <= 0xFFFF:
        raise ValueError("SSID must fit into 16 bits")
    return number


@dataclass(frozen=True)
class Firmware:
    path: Path
    data: bytes
    md5: str
    sha256: str

    @classmethod
    def load(
        cls,
        path: str | Path,
        expected_md5: Optional[str] = None,
        expected_size: Optional[int] = None,
    ) -> "Firmware":
        file_path = Path(path)
        data = file_path.read_bytes()
        md5 = hashlib.md5(data).hexdigest().upper()
        sha256 = hashlib.sha256(data).hexdigest().upper()
        if expected_size is not None and len(data) != expected_size:
            raise ValueError(f"firmware size mismatch: {len(data)} != {expected_size}")
        if expected_md5 is not None and md5 != expected_md5.strip().upper():
            raise ValueError(f"firmware MD5 mismatch: {md5} != {expected_md5.upper()}")
        return cls(file_path, data, md5, sha256)


@dataclass(frozen=True)
class TransferSpec:
    firmware: Firmware
    software_code: str
    version: str
    ssid: int
    block_size: int = DEFAULT_BLOCK_SIZE

    def __post_init__(self) -> None:
        if len(self.software_code) != 8 or not self.software_code.isascii():
            raise ValueError("software code must contain exactly 8 ASCII characters")
        object.__setattr__(self, "version", normalize_version(self.version))
        if not 1 <= self.block_size <= 255 or (self.block_size + 6) % 2:
            raise ValueError("block size must be 1..255 and block_size+6 must be even")

    @property
    def total_blocks(self) -> int:
        return math.ceil(len(self.firmware.data) / self.block_size)

    @property
    def confirmation_phrase(self) -> str:
        return f"{LIVE_CONFIRM_PREFIX}-{self.firmware.sha256}"


def fc10_frame(register: int, payload: bytes, *, byte_count: Optional[int] = None) -> bytes:
    if len(payload) % 2:
        raise ValueError("FC10 payload must contain an even number of bytes")
    count = len(payload) if byte_count is None else byte_count
    header = bytes((UNIT, FC_WRITE_MULTIPLE)) + register.to_bytes(2, "big")
    header += (len(payload) // 2).to_bytes(2, "big") + bytes((count,))
    return with_crc(header + payload)


def build_c350(spec: TransferSpec) -> bytes:
    payload = spec.ssid.to_bytes(2, "big")
    payload += spec.software_code.encode("ascii") + spec.version.encode("ascii")
    return fc10_frame(REG_C350, payload)


def build_c357(spec: TransferSpec) -> bytes:
    payload = spec.ssid.to_bytes(2, "big")
    payload += len(spec.firmware.data).to_bytes(4, "big")
    payload += spec.firmware.md5.lower().encode("ascii")
    return fc10_frame(REG_C357, payload)


def firmware_payload(spec: TransferSpec, block: int) -> bytes:
    if not 1 <= block <= spec.total_blocks:
        raise ValueError(f"block outside 1..{spec.total_blocks}: {block}")
    start = (block - 1) * spec.block_size
    chunk = spec.firmware.data[start : start + spec.block_size]
    return chunk + b"\xFF" * (spec.block_size - len(chunk))


def build_c5a8(spec: TransferSpec, block: int) -> bytes:
    header = spec.ssid.to_bytes(2, "big")
    header += spec.total_blocks.to_bytes(2, "big") + block.to_bytes(2, "big")
    payload = header + firmware_payload(spec, block)
    # phnixIot4G puts only the firmware block length in the byte-count field.
    return fc10_frame(REG_C5A8, payload, byte_count=spec.block_size)


def iter_transfer_frames(spec: TransferSpec) -> Iterable[tuple[str, bytes]]:
    yield "C350", build_c350(spec)
    yield "C357", build_c357(spec)
    for block in range(1, spec.total_blocks + 1):
        yield f"C5A8:{block}", build_c5a8(spec, block)


def build_c371_ack(spec: TransferSpec, block: int, ack_b: Optional[int] = None) -> bytes:
    final = block == spec.total_blocks
    ack_kind = (2 if final else 1) if ack_b is None else ack_b
    payload = spec.ssid.to_bytes(2, "big") + (1).to_bytes(2, "big")
    payload += ack_kind.to_bytes(2, "big") + block.to_bytes(2, "big")
    return fc10_frame(REG_C371, payload)


def decode_fc10(frame: bytes) -> tuple[int, bytes]:
    if len(frame) < 8 or frame[0] != UNIT or frame[1] != FC_WRITE_MULTIPLE:
        raise ProtocolError(f"not a PHNIX FC10 frame: {frame.hex(' ')}")
    if not has_valid_crc(frame):
        raise ProtocolError(f"CRC error: {frame.hex(' ')}")
    register = int.from_bytes(frame[2:4], "big")
    if len(frame) == 8:
        return register, b""
    byte_count = frame[6]
    expected_length = (15 if register == REG_C5A8 else 9) + byte_count
    if len(frame) != expected_length:
        raise ProtocolError(
            f"length mismatch for register 0x{register:04X}: {len(frame)} != {expected_length}"
        )
    return register, frame[7:-2]


def decode_c36e(payload: bytes) -> tuple[int, int, Optional[int]]:
    if len(payload) not in (4, 6):
        raise ProtocolError(f"unexpected C36E payload length: {len(payload)}")
    ssid = int.from_bytes(payload[0:2], "big")
    status = int.from_bytes(payload[2:4], "big")
    block_size = int.from_bytes(payload[4:6], "big") if len(payload) == 6 else None
    return ssid, status, block_size


def decode_c371(payload: bytes) -> tuple[int, int, int, int]:
    if len(payload) != 8:
        raise ProtocolError(f"unexpected C371 payload length: {len(payload)}")
    return tuple(int.from_bytes(payload[i : i + 2], "big") for i in range(0, 8, 2))  # type: ignore[return-value]


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, size: int, timeout: float) -> bytes: ...
    def close(self) -> None: ...


class TcpTransport:
    def __init__(self, host: str, port: int, timeout: float):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)

    def read(self, size: int, timeout: float) -> bytes:
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(size)
        except socket.timeout:
            return b""

    def close(self) -> None:
        self.sock.close()


class SerialTransport:
    def __init__(self, port: str, baudrate: int, timeout: float):
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise RuntimeError("USB-RS485 requires pyserial: pip install pyserial") from exc
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )

    def write(self, data: bytes) -> None:
        self.serial.write(data)
        self.serial.flush()

    def read(self, size: int, timeout: float) -> bytes:
        self.serial.timeout = timeout
        return self.serial.read(size)

    def close(self) -> None:
        self.serial.close()


class FrameReader:
    """Extract FC10 service frames from a raw TCP or serial stream."""

    def __init__(self, transport: Transport):
        self.transport = transport
        self.pending = bytearray()

    def read_frame(self, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frame = self._extract()
            if frame is not None:
                return frame
            chunk = self.transport.read(4096, min(0.25, max(0.01, deadline - time.monotonic())))
            if chunk:
                self.pending.extend(chunk)
        raise TimeoutError("timeout waiting for PHNIX response")

    def _extract(self) -> Optional[bytes]:
        while True:
            marker = self.pending.find(bytes((UNIT, FC_WRITE_MULTIPLE)))
            if marker < 0:
                if self.pending[-1:] == bytes((UNIT,)):
                    del self.pending[:-1]
                else:
                    self.pending.clear()
                return None
            if marker:
                del self.pending[:marker]
            if len(self.pending) < 8:
                return None
            # Try an extended FC10 write first. PHNIX uses quantity that can be
            # inconsistent with byte_count for C5A8, so byte_count is decisive.
            if len(self.pending) >= 7:
                register = int.from_bytes(self.pending[2:4], "big")
                extended_len = (15 if register == REG_C5A8 else 9) + self.pending[6]
                if self.pending[6] <= 255 and len(self.pending) >= extended_len:
                    candidate = bytes(self.pending[:extended_len])
                    if has_valid_crc(candidate):
                        del self.pending[:extended_len]
                        return candidate
            candidate = bytes(self.pending[:8])
            if has_valid_crc(candidate):
                del self.pending[:8]
                return candidate
            if len(self.pending) < extended_len:
                return None
            del self.pending[0]


class JsonlLog:
    def __init__(self, path: Optional[str]):
        self.handle: Optional[BinaryIO] = None
        if path:
            self.handle = open(path, "ab", buffering=0)

    def event(self, direction: str, label: str, frame: Optional[bytes] = None, **fields: object) -> None:
        record = {"time": time.time(), "direction": direction, "label": label, **fields}
        if frame is not None:
            record["frame"] = frame.hex(" ").upper()
        line = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
        if self.handle:
            self.handle.write(line)

    def close(self) -> None:
        if self.handle:
            self.handle.close()


def wait_for_handshake(
    reader: FrameReader,
    expected_register: int,
    expected_status: int,
    spec: TransferSpec,
    timeout: float,
    log: JsonlLog,
) -> Optional[int]:
    deadline = time.monotonic() + timeout
    confirmed = False
    status_seen = False
    negotiated: Optional[int] = None
    while not (confirmed and status_seen):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"handshake timeout: confirm={confirmed}, status{expected_status}={status_seen}"
            )
        frame = reader.read_frame(remaining)
        register, payload = decode_fc10(frame)
        log.event("rx", f"0x{register:04X}", frame)
        if register == expected_register:
            confirmed = True
        elif register == REG_C36E:
            ssid, status, block_size = decode_c36e(payload)
            if ssid != spec.ssid:
                raise ProtocolError(f"C36E SSID 0x{ssid:04X} != 0x{spec.ssid:04X}")
            if status in (4, 6):
                raise ProtocolError(f"board reported OTA error status {status}")
            if status == expected_status:
                status_seen = True
                negotiated = block_size
        # Other valid traffic is logged but does not advance the handshake.
    return negotiated


def run_live_transfer(
    spec: TransferSpec,
    transport: Transport,
    timeout: float,
    log: JsonlLog,
    stop_after: str = "data",
) -> None:
    reader = FrameReader(transport)
    c350 = build_c350(spec)
    log.event("tx", "C350", c350)
    transport.write(c350)
    negotiated = wait_for_handshake(reader, REG_C350, 1, spec, timeout, log)
    if negotiated is not None and negotiated != spec.block_size:
        raise ProtocolError(
            f"board negotiated block size {negotiated}, plan uses {spec.block_size}; stopping"
        )

    c357 = build_c357(spec)
    log.event("tx", "C357", c357)
    transport.write(c357)
    negotiated = wait_for_handshake(reader, REG_C357, 2, spec, timeout, log)
    if negotiated is not None and negotiated != spec.block_size:
        raise ProtocolError(
            f"board negotiated block size {negotiated}, plan uses {spec.block_size}; stopping"
        )

    if stop_after == "handshake":
        log.event("stop", "C357-status2-handshake-boundary")
        return

    for block in range(1, spec.total_blocks + 1):
        frame = build_c5a8(spec, block)
        log.event("tx", "C5A8", frame, block=block, total=spec.total_blocks)
        transport.write(frame)
        while True:
            reply = reader.read_frame(timeout)
            register, payload = decode_fc10(reply)
            log.event("rx", f"0x{register:04X}", reply, block=block)
            if register == REG_C36E:
                ssid, status, _ = decode_c36e(payload)
                if ssid != spec.ssid or status in (4, 6):
                    raise ProtocolError(f"board status during block {block}: SSID={ssid:04X}, status={status}")
                continue
            if register != REG_C371:
                continue
            ssid, ack_a, ack_b, ack_block = decode_c371(payload)
            expected_ack_b = 2 if block == spec.total_blocks else 1
            if (ssid, ack_a, ack_b, ack_block) != (
                spec.ssid,
                1,
                expected_ack_b,
                block,
            ):
                raise ProtocolError(
                    "C371 mismatch: "
                    f"got ssid={ssid:04X} ackA={ack_a} ackB={ack_b} block={ack_block}; "
                    f"expected ssid={spec.ssid:04X} ackA=1 ackB={expected_ack_b} block={block}"
                )
            break

    # Deliberate boundary: do not ACK C36E status 3/5 and do not emit C37B.
    log.event(
        "stop",
        "final-C371-ackB2",
        blocks=spec.total_blocks,
        bytes=len(spec.firmware.data),
        sha256=spec.firmware.sha256,
    )


def simulate(spec: TransferSpec) -> dict[str, object]:
    reconstructed = bytearray()
    stream_hash = hashlib.sha256()
    for label, frame in iter_transfer_frames(spec):
        if not has_valid_crc(frame):
            raise AssertionError(f"generated CRC failed for {label}")
        stream_hash.update(frame)
        if label.startswith("C5A8:"):
            block = int(label.split(":", 1)[1])
            register, payload = decode_fc10(frame)
            if register != REG_C5A8:
                raise AssertionError("wrong data register")
            ssid = int.from_bytes(payload[0:2], "big")
            total = int.from_bytes(payload[2:4], "big")
            current = int.from_bytes(payload[4:6], "big")
            if (ssid, total, current) != (spec.ssid, spec.total_blocks, block):
                raise AssertionError("generated C5A8 header mismatch")
            chunk_len = min(spec.block_size, len(spec.firmware.data) - len(reconstructed))
            reconstructed.extend(payload[6 : 6 + chunk_len])
            ack = build_c371_ack(spec, block)
            _, ack_payload = decode_fc10(ack)
            _, ack_a, ack_b, ack_block = decode_c371(ack_payload)
            expected_ack = 2 if block == spec.total_blocks else 1
            if (ack_a, ack_b, ack_block) != (1, expected_ack, block):
                raise AssertionError("simulated C371 ACK mismatch")
    if bytes(reconstructed) != spec.firmware.data:
        raise AssertionError("simulated firmware reconstruction mismatch")
    final_real = len(spec.firmware.data) % spec.block_size or spec.block_size
    return {
        "mode": "internal-simulation-no-io",
        "firmware": str(spec.firmware.path),
        "size": len(spec.firmware.data),
        "md5": spec.firmware.md5,
        "sha256": spec.firmware.sha256,
        "softwareCode": spec.software_code,
        "version485": spec.version,
        "ssid": f"{spec.ssid:04X}",
        "blockSize": spec.block_size,
        "totalBlocks": spec.total_blocks,
        "lastBlockRealBytes": final_real,
        "lastBlockPaddingBytes": spec.block_size - final_real,
        "generatedStreamSha256": stream_hash.hexdigest().upper(),
        "finalAckB": 2,
        "stopBoundary": "after final C371 ackB=2; no C37B/status ACK",
        "verified": True,
    }


def compare_capture(spec: TransferSpec, capture_path: str | Path) -> dict[str, object]:
    """Find every generated request, byte-for-byte and in order, in a raw capture."""
    capture = Path(capture_path).read_bytes()
    cursor = 0
    matched = 0
    first_offset: Optional[int] = None
    last_offset: Optional[int] = None
    for label, expected in iter_transfer_frames(spec):
        offset = capture.find(expected, cursor)
        if offset < 0:
            raise ProtocolError(
                f"capture mismatch after {matched} frames: {label} not found after offset {cursor}"
            )
        if first_offset is None:
            first_offset = offset
        last_offset = offset
        cursor = offset + len(expected)
        matched += 1
    return {
        "mode": "capture-comparison-no-io",
        "capture": str(capture_path),
        "captureSize": len(capture),
        "firmwareSha256": spec.firmware.sha256,
        "matchedFrames": matched,
        "expectedFrames": spec.total_blocks + 2,
        "firstMatchOffset": first_offset,
        "lastMatchOffset": last_offset,
        "matchedThroughOffset": cursor,
        "byteExactAndInOrder": True,
    }


def build_spec(args: argparse.Namespace) -> TransferSpec:
    firmware = Firmware.load(args.firmware, args.expected_md5, args.expected_size)
    return TransferSpec(
        firmware=firmware,
        software_code=args.software_code,
        version=args.version,
        ssid=parse_ssid(args.ssid),
        block_size=args.block_size,
    )


def add_firmware_args(parser: argparse.ArgumentParser, *, live: bool = False) -> None:
    parser.add_argument("--firmware", required=True, help="firmware binary")
    parser.add_argument("--software-code", required=True, help="8-character board software code")
    parser.add_argument("--version", required=True, help="cloud form V3.4 or internal form 0034")
    parser.add_argument("--ssid", required=True, help="four-digit hexadecimal OTA session, e.g. 0063")
    parser.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE)
    parser.add_argument("--expected-md5", required=live, help="abort unless firmware MD5 matches")
    parser.add_argument("--expected-size", required=live, type=int, help="abort unless firmware size matches")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "simulate"):
        child = sub.add_parser(name, help=f"{name} without opening any transport")
        add_firmware_args(child)
        child.add_argument("--json-output", help="also write result JSON to this file")

    compare = sub.add_parser(
        "compare-capture",
        help="compare generated requests with a raw original-program RS485 capture",
    )
    add_firmware_args(compare)
    compare.add_argument("--capture", required=True)
    compare.add_argument("--json-output", help="also write result JSON to this file")

    send = sub.add_parser("send", help="DANGEROUS: send to a physically connected mainboard")
    add_firmware_args(send, live=True)
    endpoint = send.add_mutually_exclusive_group(required=True)
    endpoint.add_argument("--tcp", metavar="HOST:PORT", help="raw ser2net endpoint")
    endpoint.add_argument("--serial", metavar="PORT", help="USB-RS485 port, e.g. COM5 or /dev/ttyUSB0")
    send.add_argument("--baudrate", type=int, default=9600)
    send.add_argument("--timeout", type=float, default=12.0)
    send.add_argument("--log", required=True, help="JSONL transcript path")
    send.add_argument(
        "--stop-after",
        choices=("handshake", "data"),
        default="handshake",
        help="default handshake never sends C5A8; data performs the firmware data phase",
    )
    send.add_argument(
        "--confirm-live-transfer",
        help=f"must equal {LIVE_CONFIRM_PREFIX}-<firmware SHA256>",
    )
    return parser


def write_result(result: dict[str, object], output: Optional[str]) -> None:
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        spec = build_spec(args)
        result = simulate(spec)
        if args.command in ("plan", "simulate", "compare-capture"):
            if args.command == "compare-capture":
                write_result(compare_capture(spec, args.capture), args.json_output)
                return 0
            if args.command == "plan":
                result["mode"] = "plan-no-io"
                result["c350"] = build_c350(spec).hex(" ").upper()
                result["c357"] = build_c357(spec).hex(" ").upper()
                result["firstC5A8"] = build_c5a8(spec, 1).hex(" ").upper()
                result["lastC5A8"] = build_c5a8(spec, spec.total_blocks).hex(" ").upper()
                result["requiredLiveConfirmation"] = spec.confirmation_phrase
            write_result(result, args.json_output)
            return 0

        if args.confirm_live_transfer != spec.confirmation_phrase:
            print("LIVE TRANSFER REFUSED. Required phrase:", file=sys.stderr)
            print(spec.confirmation_phrase, file=sys.stderr)
            return 3

        log = JsonlLog(args.log)
        transport: Optional[Transport] = None
        try:
            if args.tcp:
                host, separator, port_text = args.tcp.rpartition(":")
                if not separator or not host:
                    raise ValueError("--tcp must use HOST:PORT")
                transport = TcpTransport(host, int(port_text), args.timeout)
            else:
                transport = SerialTransport(args.serial, args.baudrate, args.timeout)
            run_live_transfer(spec, transport, args.timeout, log, args.stop_after)
        finally:
            if transport is not None:
                transport.close()
            log.close()
        if args.stop_after == "handshake":
            print("Handshake completed; stopped after C357 confirmation and C36E status 2.")
            print("No C5A8 firmware block was sent.")
        else:
            print("Transfer data phase completed; stopped after final C371 ackB=2.")
            print("No C37B status acknowledgement was sent.")
        return 0
    except (OSError, ValueError, ProtocolError, TimeoutError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
