import pytest

from core.sg_ready import (
    SG_MODE_OPTIONS, sg_status_description, uses_virtual_sg_input, virtual_stage_options,
)


def test_all_eight_sg01_modes_are_exposed():
    assert [value for _label, value in SG_MODE_OPTIONS] == list(range(8))
    assert SG_MODE_OPTIONS[4][0] == "AI Saving / Remote Energy Control"


def test_mode7_virtual_register_has_exactly_three_pv_stages():
    assert virtual_stage_options(7) == (
        ("Low PV – Begrenzung über SG03 (1336)", 1),
        ("Neutral / Normalbetrieb – keine SG-Anpassung", 2),
        ("High PV – SG05/SG06 Anhebung, SG07 Absenkung", 3),
    )


def test_mode7_status_2133_uses_pv_stage_meanings():
    assert sg_status_description(7, 1).startswith("Low PV")
    assert sg_status_description(7, 2).startswith("Neutral")
    assert sg_status_description(7, 3).startswith("High PV")


def test_classic_virtual_mode_keeps_four_existing_stages():
    assert [value for _label, value in virtual_stage_options(3)] == [1, 2, 3, 4]
    assert sg_status_description(3, 4) == "SG Mode 4 / High PV"
    assert sg_status_description(3, 0) == "WP Aus / SG Ready Aus"


@pytest.mark.parametrize("mode", [0, 1, 2, 4, 5, 6])
def test_non_virtual_modes_do_not_offer_or_write_8801(mode):
    assert virtual_stage_options(mode) == ()
    assert not uses_virtual_sg_input(mode, "standard_modbus")


@pytest.mark.parametrize("mode, stages", [(3, [1, 2, 3, 4]), (7, [1, 2, 3])])
def test_virtual_modes_offer_and_write_only_their_valid_stages(mode, stages):
    assert [value for _label, value in virtual_stage_options(mode)] == stages
    assert uses_virtual_sg_input(mode, "standard_modbus")


@pytest.mark.parametrize("mode", [3, 7])
def test_cloud_backend_never_writes_8801(mode):
    assert not uses_virtual_sg_input(mode, "warmlink")


def test_physical_extended_status_is_left_uninterpreted():
    assert sg_status_description(5, 2).startswith("Status RAW 2")
    assert sg_status_description(6, 3).startswith("Status RAW 3")
