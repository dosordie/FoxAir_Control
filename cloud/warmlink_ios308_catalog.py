"""Observed WarmLink iOS 3.0.8 requests; semantics and live support stay separate.

Source: Issue #178, app capture 2026-10-10, GL9/644 with the heat pump OFF.
S01~S11 and O25~O27 are literal protocol codes, not ranges to expand.
"""
from __future__ import annotations

WARMLINK_IOS308_SOURCE = "WarmLink iOS 3.0.8 / Issue #178, 2026-10-10 (WP OFF)"
WARMLINK_IOS308_CODES = (
    "Run_Mode",
    "H02",
    "H06",
    "H23",
    "H35",
    "H41",
    "F21",
    "E24",
    "R40",
    "R41",
    "C06",
    "O14",
    "O13",
    "O12",
    "S01~S11",
    "T13",
    "T14",
    "T45",
    "T49",
    "1250",
    "1256",
    "1257",
    "1258",
    "1259",
    "1260",
    "1261",
    "1262",
    "1263",
    "1264",
    "1265",
    "1266",
    "1267",
    "1268",
    "1269",
    "CP1-1",
    "CP1-2",
    "CP1-3",
    "CP1-5",
    "CP1-6",
    "CP1-7",
    "CP2-1",
    "CP2-2",
    "CP2-3",
    "CP2-5",
    "CP2-6",
    "CP2-7",
    "L01",
    "L02",
    "L03",
    "L04",
    "L05",
    "L06",
    "L07",
    "Output1",
    "Switch1",
    "T18",
    "T19",
    "T20",
    "T24",
    "T25",
    "T26",
    "H55",
    "O25~O27",
    "S100",
    "T50",
    "T51",
    "T52",
    "T53",
    "T54",
    "T55",
    "T56",
    "T108",
    "T100",
    "T101",
    "T102",
    "T103",
    "T_PWM_Out2",
    "T_PWM_IN2_1",
    "T104",
    "T_PWM_IN2_2",
    "T105",
    "T106",
    "T107",
    "T06_1",
    "Fault100",
    "C22",
    "C23",
    "CompPreHeatRemainTim",
    "H59",
    "H61",
    "H61_1",
    "H61_2",
    "H61_3",
    "H52",
    "H53",
    "H61_5",
    "O33",
    "T113",
    "T114",
    "T57",
    "T58",
    "T109",
    "T112",
    "T116",
    "T117",
    "T118",
    "T119",
    "T120",
)
WARMLINK_IOS308_CODE_SET = frozenset(WARMLINK_IOS308_CODES)
WARMLINK_IOS308_PWM_CODES = ("T_PWM_Out2", "T_PWM_IN2_1", "T_PWM_IN2_2")

# Documentation only. These values neither create mappings nor imply units.
IOS308_OFF_OBSERVATIONS = {
    "CompPreHeatRemainTim": 0, "T57": 608, "T58": 0,
    "1256": 1805, "1257": 5396,
    **{str(code): 0 for code in range(1258, 1268)},
    "1268": "0000000100011111", "1269": "0",
    **{f"L0{code}": 0 for code in range(1, 8)},
}
IOS308_OBSERVED_TYPES = {
    "CompPreHeatRemainTim": "DIGI1", "T57": "DIGI1", "T58": "DIGI1",
    "1268": "BINARY", "1269": "BINARY",
}


def ios308_code_metadata(code: str) -> dict[str, object]:
    """An app request proves query eligibility, not a local mapping or write grant."""
    if code not in WARMLINK_IOS308_CODE_SET:
        return {}
    metadata = {
        "name": code, "app_known": True, "query_candidate": True,
        "app_version": "iOS 3.0.8", "source": WARMLINK_IOS308_SOURCE,
        "confidence": "unknown", "mapping_intentionally_absent": True,
        "write_allowed": False, "live_validation_required": True,
        "note": "Original app request observed with WP OFF; semantics, unit and scaling remain unconfirmed",
    }
    if code in IOS308_OBSERVED_TYPES:
        metadata["cloud_dataType"] = IOS308_OBSERVED_TYPES[code]
    if code in IOS308_OFF_OBSERVATIONS:
        metadata["observed_off_value"] = IOS308_OFF_OBSERVATIONS[code]
    return metadata
