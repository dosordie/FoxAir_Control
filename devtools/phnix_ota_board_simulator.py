#!/usr/bin/env python3
"""Loopback board peer for end-to-end tests of phnix_ota_sender.py.

The simulator validates every request against a local firmware file and only
returns protocol acknowledgements. It has no flash, serial, MQTT or HTTP code.
By default it binds to 127.0.0.1 and refuses non-loopback listen addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import time
from pathlib import Path

from phnix_ota_sender import (
    FrameReader,
    ProtocolError,
    TransferSpec,
    Firmware,
    build_c350,
    build_c357,
    build_c371_ack,
    build_c5a8,
    decode_fc10,
    fc10_frame,
    parse_ssid,
    with_crc,
)


class AcceptedSocketTransport:
    def __init__(self, connection: socket.socket):
        self.connection = connection

    def write(self, data: bytes) -> None:
        self.connection.sendall(data)

    def read(self, size: int, timeout: float) -> bytes:
        self.connection.settimeout(timeout)
        try:
            return self.connection.recv(size)
        except socket.timeout:
            return b""

    def close(self) -> None:
        self.connection.close()


def standard_fc10_response(request: bytes) -> bytes:
    return with_crc(request[:6])


def c36e_status(spec: TransferSpec, status: int) -> bytes:
    payload = spec.ssid.to_bytes(2, "big") + status.to_bytes(2, "big")
    return fc10_frame(0xC36E, payload)


def serve_once(spec: TransferSpec, listen: str, timeout: float, result_path: str | None) -> dict:
    host, separator, port_text = listen.rpartition(":")
    if not separator or not host:
        raise ValueError("--listen must use HOST:PORT")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("simulator only accepts a loopback listen address")

    server = socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, int(port_text)))
    server.listen(1)
    server.settimeout(timeout)
    print(f"READY {host}:{port_text}", flush=True)
    connection, address = server.accept()
    server.close()
    transport = AcceptedSocketTransport(connection)
    reader = FrameReader(transport)
    reconstructed = bytearray()
    try:
        for label, expected, status in (
            ("C350", build_c350(spec), 1),
            ("C357", build_c357(spec), 2),
        ):
            frame = reader.read_frame(timeout)
            if frame != expected:
                raise ProtocolError(f"{label} differs from expected frame")
            transport.write(standard_fc10_response(frame))
            # Separate writes model the original UART receive assumption that
            # a read contains one Modbus frame.
            time.sleep(0.02)
            transport.write(c36e_status(spec, status))

        for block in range(1, spec.total_blocks + 1):
            frame = reader.read_frame(timeout)
            expected = build_c5a8(spec, block)
            if frame != expected:
                register, _ = decode_fc10(frame)
                raise ProtocolError(
                    f"block {block} differs from expected C5A8 (register 0x{register:04X})"
                )
            _, payload = decode_fc10(frame)
            real = min(spec.block_size, len(spec.firmware.data) - len(reconstructed))
            reconstructed.extend(payload[6 : 6 + real])
            transport.write(build_c371_ack(spec, block))
    finally:
        transport.close()

    if bytes(reconstructed) != spec.firmware.data:
        raise ProtocolError("reconstructed firmware differs from fixture")
    result = {
        "mode": "loopback-board-simulator",
        "peer": str(address),
        "bytes": len(reconstructed),
        "blocks": spec.total_blocks,
        "md5": hashlib.md5(reconstructed).hexdigest().upper(),
        "sha256": hashlib.sha256(reconstructed).hexdigest().upper(),
        "finalAckB": 2,
        "c37bEmitted": False,
        "verified": True,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered, flush=True)
    if result_path:
        Path(result_path).write_text(rendered + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default="127.0.0.1:24001")
    parser.add_argument("--firmware", required=True)
    parser.add_argument("--software-code", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--ssid", required=True)
    parser.add_argument("--block-size", type=int, default=168)
    parser.add_argument("--expected-md5")
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--result")
    args = parser.parse_args()
    try:
        firmware = Firmware.load(args.firmware, args.expected_md5, args.expected_size)
        spec = TransferSpec(
            firmware,
            args.software_code,
            args.version,
            parse_ssid(args.ssid),
            args.block_size,
        )
        serve_once(spec, args.listen, args.timeout, args.result)
        return 0
    except (OSError, ValueError, ProtocolError, TimeoutError) as exc:
        print(f"ERROR: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
