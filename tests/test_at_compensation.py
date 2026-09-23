import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.at_compensation import AT_SEVEN_POINT_REGISTERS, calculate_seven_point_target


def test_h36_modes_and_exact_seven_point_mapping():
    mapping = json.loads((ROOT / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))
    assert mapping["1236"]["value_map"] == {"0": "Aus", "1": "Lineare Kennlinie", "2": "7-Punkt-Kennlinie"}
    assert AT_SEVEN_POINT_REGISTERS == ((-20.0, 1250), (-10.0, 1251), (-5.0, 1252), (0.0, 1235), (5.0, 1253), (10.0, 1254), (20.0, 1255))
    assert all(mapping[str(register)]["type"] == "TEMP1" for _at, register in AT_SEVEN_POINT_REGISTERS)


def test_seven_point_interpolation_clamps_outdoor_and_result():
    values = {1250: 60, 1251: 50, 1252: 45, 1235: 40, 1253: 35, 1254: 30, 1255: 20}
    expected = {-15: 55, -7.5: 47.5, 2.5: 37.5, 15: 25, -30: 60, 30: 20}
    for outdoor, target in expected.items():
        assert calculate_seven_point_target(outdoor, values, 10, 70) == pytest.approx(target)
    assert calculate_seven_point_target(-20, values, 25, 55) == 55
    assert calculate_seven_point_target(20, values, 25, 55) == 25


def test_mode_two_calculation_has_no_slope_input():
    assert "slope" not in calculate_seven_point_target.__annotations__


def test_dialog_data_flow_reads_and_updates_all_curve_registers():
    source = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")
    assert "(1250, 6, \"AT-Kompensation 7-Punkt 1250-1255\")" in source
    assert "(1164, 2, \"AT-Kompensation Grenzen R10/R11\")" in source
    for register in (1234, 1235, 1236, 1250, 1251, 1252, 1253, 1254, 1255, 1164, 1165, 2014, 2048):
        assert str(register) in source.split("LIVE_REGISTERS = {", 1)[1].split("}", 1)[0]


def test_mode_and_parameter_writes_are_separate_methods():
    source = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")
    mode_body = source.split("    def write_mode(self):", 1)[1].split("    def write_linear_params", 1)[0]
    assert "send_register_write(1236" in mode_body
    assert "send_register_write(1234" not in mode_body and "send_register_write(1235" not in mode_body
