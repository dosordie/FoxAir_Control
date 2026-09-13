from core.sg_ready import sg_status_description, virtual_stage_options


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
