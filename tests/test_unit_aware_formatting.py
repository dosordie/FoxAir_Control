import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.foxair_phnix_core import format_value_by_type


def test_temp1_uses_kelvin_for_register_unit_k():
    assert format_value_by_type(98, "TEMP1", unit="K") == "9.8 K"
    assert format_value_by_type(35, "TEMP1", unit="K") == "3.5 K"


def test_temp1_defaults_to_celsius_without_unit_or_with_celsius():
    assert format_value_by_type(180, "TEMP1") == "18.0 °C"
    assert format_value_by_type(180, "TEMP1", unit="°C") == "18.0 °C"


def test_non_temperature_units_are_not_duplicated_by_unit_argument():
    assert format_value_by_type(337, "VOLT", unit="V") == "337 V"
    assert format_value_by_type(42, "PERCENT", unit="%") == "42 %"


def test_unitless_values_remain_unchanged():
    assert format_value_by_type(123, "DIGI1") == "123"


def test_generic_register_units_are_appended_when_unit_is_supplied():
    assert format_value_by_type(123, "DIGI5", unit="A") == "12.3 A"
    assert format_value_by_type(12, "RAW", unit="h") == "12 h"


def test_value_maps_and_bit_maps_take_precedence_over_register_units():
    assert format_value_by_type(1, "DIGI1", value_map={1: "On"}, unit="A") == "1 = On"
    assert format_value_by_type(0b10, "BITFIELD", bit_map={1: "Pump"}, unit="A") == "0x0002: B1: Pump"


def test_flow_x100_uses_signed_scaling_and_two_decimal_places():
    assert format_value_by_type(36, "FLOW_M3H_X100") == "0.36 m³/h"
    assert format_value_by_type(0, "FLOW_X100") == "0.00 m³/h"
    assert format_value_by_type(0xFFF6, "FLOW_M3H_X100") == "-0.10 m³/h"
    assert format_value_by_type(47, "FLOW_X100") == "0.47 m³/h"
    assert format_value_by_type(50, "FLOW_X100") == "0.50 m³/h"
    assert format_value_by_type(64, "FLOW_X100") == "0.64 m³/h"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, "0 / 0x0000 / 0000000000000000"),
        (1, "1 / 0x0001 / 0000000000000001"),
        (63, "63 / 0x003F / 0000000000111111"),
        (0x8000, "32768 / 0x8000 / 1000000000000000"),
        (0xFFFF, "65535 / 0xFFFF / 1111111111111111"),
    ],
)
def test_generic_bitfield_preserves_unsigned_16_bit_raw_hex_and_binary(raw, expected):
    assert format_value_by_type(raw, "BITFIELD") == expected
