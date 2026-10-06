"""Shared translation of WarmLink values into local register semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.foxair_phnix_core import decode_contact_bits
from cloud.metadata import resolve_cloud_unit


@dataclass(frozen=True)
class ActiveBit:
    bit: int
    name: str
    state: str = "EIN"


@dataclass(frozen=True)
class TranslatedCloudValue:
    original: Any
    raw: int | float | str
    display: str
    hex: str = ""
    active_bits: tuple[ActiveBit, ...] = field(default_factory=tuple)


def parse_cloud_number(value: Any, *, binary: bool = False) -> int | float:
    """Parse API numbers, including 16-character BINARY bit words."""
    text = str(value).strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # JSON numbers are decimal, even for BINARY registers.
        return int(value) if isinstance(value, float) and value.is_integer() else value
    if text and set(text) <= {"0", "1"} and (binary or len(text) == 16):
        return int(text, 2)
    number = float(text.replace(",", "."))
    return int(number) if number.is_integer() else number


def cloud_values_equal(left: Any, right: Any) -> bool:
    """Compare observed payload values without units, types or other metadata."""
    def key(value):
        try:
            return parse_cloud_number(value)
        except (TypeError, ValueError):
            return str(value)
    return key(left) == key(right)


def translate_cloud_value(
    cloud_code: str,
    value: Any,
    register_definition: Mapping[str, Any] | None = None,
    cloud_hint: Mapping[str, Any] | None = None,
    live_metadata: Mapping[str, Any] | None = None,
) -> TranslatedCloudValue:
    """Return a structured display value without duplicating register metadata."""
    definition = register_definition or {}
    hint = cloud_hint or {}
    live = live_metadata or {}
    binary = str(live.get("dataType") or live.get("dataTypeAi") or hint.get("cloud_dataType") or hint.get("dataType") or "").upper() in {"BINARY", "BITWORD16"}
    try:
        raw = parse_cloud_number(value, binary=binary)
    except (TypeError, ValueError):
        return TranslatedCloudValue(value, str(value), str(value))

    if isinstance(raw, int) and str(hint.get("dataType") or "").upper() == "BITWORD16":
        raw &= 0xFFFF

    maps = (hint.get("write_values"), hint.get("value_map"), definition.get("value_map"))
    for values in maps:
        if not isinstance(values, Mapping):
            continue
        label = values.get(str(raw), values.get(raw))
        if label is not None:
            return TranslatedCloudValue(value, raw, f"{raw} = {label}")

    bit_map = definition.get("bit_map")
    dtype = str(definition.get("type") or hint.get("dataType") or "").upper()
    if isinstance(raw, int) and (dtype == "BITFIELD" or isinstance(bit_map, Mapping)):
        active: list[ActiveBit] = []
        if cloud_code == "S01~S10":
            for bit, bit_value, name, state, _meaning in decode_contact_bits(raw):
                if state == "Ein":
                    active.append(ActiveBit(bit, name, "EIN"))
        else:
            bit_map = bit_map if isinstance(bit_map, Mapping) else {}
            for bit in range(16):
                if raw & (1 << bit):
                    name = bit_map.get(str(bit), bit_map.get(bit))
                    active.append(ActiveBit(bit, str(name) if name else "Klartext noch unbekannt"))
        parts = []
        for item in active:
            if item.name == "Klartext noch unbekannt":
                parts.append(f"Bit {item.bit} aktiv – Klartext noch unbekannt")
            else:
                parts.append(f"Bit {item.bit}: {item.name} {item.state}")
        hex_text = f"0x{raw & 0xFFFF:04X}"
        display = hex_text + (" | " + "; ".join(parts) if parts else " | keine Bits aktiv")
        return TranslatedCloudValue(value, raw, display, hex_text, tuple(active))

    unit = resolve_cloud_unit(cloud_code, hint, live, register_definition)
    return TranslatedCloudValue(value, raw, f"{raw} {unit}".strip())
