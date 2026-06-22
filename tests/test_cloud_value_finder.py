from dataclasses import dataclass

from dialogs.cloud_table_helpers import value_finder_matches
from core.foxair_phnix_core import RegisterInfo


@dataclass
class Reg:
    raw_value: int
    signed_value: int
    display_value: str
    name: str = ""
    dtype: str = "RAW"


def display_parts(reg_no, name):
    return "", str(reg_no), ""


def match_regs(cloud_raw, tolerance):
    regs = [
        (2004, Reg(4, 4, "4", "Exact", "RAW")),
        (2035, Reg(35, 35, "3.5 °C", "Lower", "TEMP1")),
        (2045, Reg(45, 45, "4.5 °C", "Upper", "TEMP1")),
        (2053, Reg(465, 465, "46.5 °C", "Abgastemperatur", "TEMP1")),
        (2079, Reg(4616, 4616, "4616 kWh", "Energiezähler", "KWH")),
        (2091, Reg(22342, 22342, "22342", "Text contains 4", "RAW")),
    ]
    regmap = {reg_no: RegisterInfo(name=reg.name, dtype=reg.dtype) for reg_no, reg in regs}
    return value_finder_matches(
        code="CloudTest",
        cloud_raw=cloud_raw,
        latest_regs_items=regs,
        regmap=regmap,
        display_parts_for_register=display_parts,
        tolerance=tolerance,
        hide_zero=False,
    )


def test_cloud_value_4_tolerance_0_matches_only_numeric_4():
    matches = match_regs("4", 0.0)
    assert [row[2] for row in matches] == ["2004"]
    assert all(row[6] == "numeric==cloud" for row in matches)


def test_cloud_value_4_tolerance_half_matches_only_3_5_to_4_5():
    matches = match_regs("4", 0.5)
    assert [row[2] for row in matches] == ["2004", "2035", "2045"]


def test_cloud_decimal_comma_is_numeric():
    matches = match_regs("4,0", 0.0)
    assert [row[2] for row in matches] == ["2004"]
