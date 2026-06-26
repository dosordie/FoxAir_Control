import sys
from pathlib import Path

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
