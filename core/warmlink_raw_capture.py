"""Helpers for lossless WarmLink raw-capture event metadata.

The binary RX/TX capture is deliberately independent from this module.  The
helpers here only classify TCP chunks for the optional JSONL event index and
therefore prefer conservative ``chunk``/``continuation`` labels over false
Modbus anomalies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXPECTED_BUS_ADDRESSES = frozenset({0x63})
KNOWN_FUNCTION_CODES = frozenset({0x03, 0x06, 0x10})
NORMAL_FC16_STATUS_BLOCKS = frozenset({0x0443, 0x07D1, 0x082B})
NORMAL_STATUS_QTY = 90


@dataclass
class ContinuationState:
    remaining: int = 0
    start_addr: int | None = None
    qty: int | None = None

    @property
    def active(self) -> bool:
        return self.remaining > 0


class WarmlinkChunkEventParser:
    """Conservative TCP-chunk classifier for raw-capture events."""

    def __init__(self, unit_id: int | None = None, expected_bus_addresses: set[int] | None = None) -> None:
        addresses = set(EXPECTED_BUS_ADDRESSES)
        if unit_id is not None:
            addresses.add(int(unit_id) & 0xFF)
        if expected_bus_addresses:
            addresses.update(int(v) & 0xFF for v in expected_bus_addresses)
        self.expected_bus_addresses = frozenset(addresses)
        self.continuation = ContinuationState()

    def parse_modbus(self, data: bytes | bytearray | memoryview) -> dict[str, Any]:
        data = bytes(data or b"")
        event: dict[str, Any] = {
            "parser": "chunk" if len(data) >= 2 else "partial",
            "len": len(data),
            "hex_head": data[:32].hex(" "),
        }
        if not data:
            return event

        if self.continuation.active and not self._is_plausible_known_frame_start(data):
            consumed = min(len(data), self.continuation.remaining)
            self.continuation.remaining -= consumed
            event.update({
                "parser": "continuation",
                "continuation_remaining": self.continuation.remaining,
            })
            if self.continuation.start_addr is not None:
                event["start_addr"] = self.continuation.start_addr
            if self.continuation.qty is not None:
                event["qty"] = self.continuation.qty
            return event

        if len(data) < 4:
            return event

        slave = data[0]
        func = data[1]
        if slave not in self.expected_bus_addresses:
            return event

        if func not in KNOWN_FUNCTION_CODES:
            event["parser"] = "frame_start"
            event["slave"] = slave
            event["anomaly"] = "unknown_function"
            return event

        event.update({"parser": "frame_start", "slave": slave, "function": func})
        if func in (0x03, 0x06, 0x10) and len(data) >= 6:
            event["start_addr"] = int.from_bytes(data[2:4], "big")
            event["qty"] = int.from_bytes(data[4:6], "big")
        if func == 0x10:
            self._maybe_start_continuation(data, event)
            self._maybe_flag_firmware_sequence(event)
        return event

    def _is_plausible_known_frame_start(self, data: bytes) -> bool:
        return len(data) >= 2 and data[0] in self.expected_bus_addresses and data[1] in KNOWN_FUNCTION_CODES

    def _maybe_start_continuation(self, data: bytes, event: dict[str, Any]) -> None:
        if len(data) < 6:
            return
        start_addr = int(event.get("start_addr", -1))
        qty = int(event.get("qty", -1))
        if qty <= 0:
            return
        # WarmLink FC16 status blocks are large TCP payloads. The observed stream
        # uses 6-byte headers plus register payload and trailing bytes; keeping a
        # conservative expected window prevents continuation chunks being parsed as
        # standalone frames while never changing the raw binary stream.
        expected_total = 6 + (qty * 2) + 2
        if start_addr in NORMAL_FC16_STATUS_BLOCKS or qty >= NORMAL_STATUS_QTY:
            remaining = max(0, expected_total - len(data))
            self.continuation = ContinuationState(remaining=remaining, start_addr=start_addr, qty=qty)
            event["parser"] = "frame_start"
            event["known_warmlink_block"] = start_addr in NORMAL_FC16_STATUS_BLOCKS and qty == NORMAL_STATUS_QTY
            event["expected_total_len"] = expected_total
            event["continuation_remaining"] = remaining

    def _maybe_flag_firmware_sequence(self, event: dict[str, Any]) -> None:
        start_addr = int(event.get("start_addr", -1))
        qty = int(event.get("qty", 0))
        if start_addr in NORMAL_FC16_STATUS_BLOCKS and qty == NORMAL_STATUS_QTY:
            return
        if qty > NORMAL_STATUS_QTY or start_addr not in NORMAL_FC16_STATUS_BLOCKS:
            event["firmware_like_fc16_sequence_candidate"] = True


def parse_modbus(data: bytes | bytearray | memoryview, unit_id: int | None = None) -> dict[str, Any]:
    """Backward-compatible one-shot chunk classification.

    This intentionally does not report ``unknown_function`` unless the chunk has
    a plausible WarmLink frame start.
    """

    return WarmlinkChunkEventParser(unit_id=unit_id).parse_modbus(data)
