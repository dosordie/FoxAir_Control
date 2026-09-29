import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.at_compensation import (
    AT_LIVE_REGISTERS,
    AT_MODE_VALUES,
    AT_READ_BLOCKS,
    AT_SEVEN_POINT_REGISTERS,
    calculate_seven_point_target,
    FALLBACK_TARGET_LIMITS,
    linear_write_plan,
    seven_point_write_plan,
    target_limits,
)


def test_h36_supports_three_numeric_modes_and_exact_point_mapping():
    mapping = json.loads((ROOT / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))

    assert AT_MODE_VALUES == (0, 1, 2)
    assert {int(value) for value in mapping["1236"]["value_map"]} == set(AT_MODE_VALUES)
    assert AT_SEVEN_POINT_REGISTERS == (
        (-20.0, 1250), (-10.0, 1251), (-5.0, 1252), (0.0, 1235),
        (5.0, 1253), (10.0, 1254), (20.0, 1255),
    )
    assert all(mapping[str(register)]["type"] == "TEMP1" for _at, register in AT_SEVEN_POINT_REGISTERS)


def test_seven_point_interpolation_clamps_outdoor_and_result():
    values = {1250: 60, 1251: 50, 1252: 45, 1235: 40, 1253: 35, 1254: 30, 1255: 20}
    expected = {-15: 55, -7.5: 47.5, 2.5: 37.5, 15: 25, -30: 60, 30: 20}
    for outdoor, target in expected.items():
        assert calculate_seven_point_target(outdoor, values, 10, 70) == pytest.approx(target)
    assert calculate_seven_point_target(-20, values, 25, 55) == 55
    assert calculate_seven_point_target(20, values, 25, 55) == 25


def test_read_blocks_and_live_registers_cover_all_required_values():
    assert AT_READ_BLOCKS == ((1234, 3), (1250, 6), (1164, 2), (2014, 1), (2048, 1))
    required = {1234, 1235, 1236, 1250, 1251, 1252, 1253, 1254, 1255, 1164, 1165, 2014, 2048}
    assert required <= AT_LIVE_REGISTERS

    send_read_request = Mock()
    for start, quantity in AT_READ_BLOCKS:
        send_read_request(start, quantity)
    assert [call.args for call in send_read_request.call_args_list] == list(AT_READ_BLOCKS)


def test_editor_limits_prefer_r10_r11_and_have_conservative_fallback():
    assert FALLBACK_TARGET_LIMITS == (5.0, 70.0)
    assert target_limits(None, None) == FALLBACK_TARGET_LIMITS
    assert target_limits(18.0, 55.0) == (18.0, 55.0)
    assert target_limits(60.0, 20.0) == FALLBACK_TARGET_LIMITS


def test_write_plans_keep_modes_and_curve_parameters_independent():
    linear = linear_write_plan(1.5, -2.5)
    seven_values = {register: 30 + index for index, (_at, register) in enumerate(AT_SEVEN_POINT_REGISTERS)}
    seven = seven_point_write_plan(seven_values)

    assert linear == ((1234, 15), (1235, 0xFFE7))
    assert tuple(register for register, _raw in seven) == (1250, 1251, 1252, 1235, 1253, 1254, 1255)
    assert 1234 not in {register for register, _raw in seven}
    assert 1236 not in {register for register, _raw in linear + seven}

    send_register_write = Mock()
    send_register_write(1236, 2)
    for write in seven:
        send_register_write(*write)
    assert send_register_write.call_args_list[0].args == (1236, 2)
    assert [call.args[0] for call in send_register_write.call_args_list[1:]] == [1250, 1251, 1252, 1235, 1253, 1254, 1255]
