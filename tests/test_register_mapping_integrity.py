import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_main_and_display_register_maps_do_not_overlap():
    main = json.loads((ROOT / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))
    display = json.loads((ROOT / "data/foxair_phnix_display_registers.json").read_text(encoding="utf-8"))

    main_registers = {key for key in main if key.isdigit()}
    display_registers = {key for key in display if key.isdigit()}
    duplicate_registers = sorted(main_registers & display_registers, key=int)

    assert duplicate_registers == []


def test_register_map_ignores_json_comment_metadata(tmp_path):
    from core.foxair_phnix_core import RegisterMap

    mapping_path = tmp_path / "registers.json"
    mapping_path.write_text(
        json.dumps({"_comment": "metadata only", "1001": {"name": "Known", "type": "RAW"}}),
        encoding="utf-8",
    )

    regmap = RegisterMap(str(mapping_path))

    assert 1001 in regmap.items
    assert len(regmap.items) == 1
