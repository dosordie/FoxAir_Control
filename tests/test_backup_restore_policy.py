import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dialogs.backup_restore_policy import (
    BACKUP_BLOCKS,
    EXCLUDED_WRITABLE_REGISTERS,
    READ_ONLY_BLOCK_HEADER_RANGES,
)


def test_writable_1xxx_registers_are_backed_up_or_explicitly_excluded():
    register_data = json.loads(
        (ROOT / "data" / "foxair_phnix_registers.json").read_text(encoding="utf-8")
    )
    writable = {
        int(reg_no)
        for reg_no, metadata in register_data.items()
        if reg_no.isdigit()
        and 1000 <= int(reg_no) < 2000
        and metadata.get("mode") == "r/w"
    }
    covered = {
        reg_no
        for _label, start, end in BACKUP_BLOCKS
        for reg_no in range(start, end + 1)
        if str(reg_no) in register_data
    }
    excluded = set(EXCLUDED_WRITABLE_REGISTERS)

    assert writable - covered == excluded
    assert {1015, 1017}.issubset(covered)
    assert excluded == {1011, 1012, 1013, 1014, 1016}
    assert excluded.isdisjoint(covered)
    for start, end in READ_ONLY_BLOCK_HEADER_RANGES:
        assert covered.isdisjoint(range(start, end + 1))
        assert all(
            register_data[str(reg_no)].get("mode") != "r/w"
            for reg_no in range(start, end + 1)
            if str(reg_no) in register_data
        )
