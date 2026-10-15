"""Validation and compatibility IDs for the existing internal display bus."""
from __future__ import annotations

import re

from core.device_info import decode_wifi_id

REQUIRED_PARAMETER_PACKETS = (1001, 1091, 1181, 1271, 1361, 1451)
OPTIONAL_PARAMETER_PACKETS = (1541,)
UNIT1_SOURCE_START = 2099
UNIT1_WORD_COUNT = 51
UNIT1_VIRTUAL_OFFSET = 89000


def is_virtual_register(register: int) -> bool:
    return 91099 <= int(register) <= 91149


def validate_parameter_packet(start: int, words: list[int], *, complete: bool = True):
    """Reuse the observed WF/header format, without a fixed device identity."""
    if len(words) < 10 or (complete and len(words) != 90):
        return None
    identity = decode_wifi_id(words[:6])
    if not identity or re.fullmatch(r"WF\d{10}", identity) is None:
        return None
    if int(words[8]) != 0x0210 or int(words[9]) != int(start):
        return None
    return {"marker": 0x0210, "internal_start": int(start), "end": int(start) + len(words) - 1}
