import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAIN_MAP_PATH = ROOT / "data/foxair_phnix_registers.json"
DISPLAY_MAP_PATH = ROOT / "data/foxair_phnix_display_registers.json"
DISPLAY_ONLY_REGISTERS = set(range(3001, 3022)) | {91105, 91108}


def _numeric_keys(data: dict) -> set[int]:
    return {int(key) for key in data if str(key).isdigit()}


def _load_static_maps() -> tuple[dict, dict]:
    main = json.loads(MAIN_MAP_PATH.read_text(encoding="utf-8"))
    display = json.loads(DISPLAY_MAP_PATH.read_text(encoding="utf-8"))
    return main, display


def test_main_and_display_register_maps_do_not_overlap():
    main, display = _load_static_maps()

    duplicate_registers = sorted(_numeric_keys(main) & _numeric_keys(display))

    assert duplicate_registers == []


def test_register_map_ignores_known_json_comment_metadata(tmp_path):
    from core.foxair_phnix_core import RegisterMap

    mapping_path = tmp_path / "registers.json"
    mapping_path.write_text(
        json.dumps({"_comment": "metadata only", "1001": {"name": "Known", "type": "RAW"}}),
        encoding="utf-8",
    )

    regmap = RegisterMap(str(mapping_path))

    assert 1001 in regmap.items
    assert len(regmap.items) == 1


def test_register_map_rejects_unexpected_non_numeric_keys(tmp_path):
    from core.foxair_phnix_core import RegisterMap

    mapping_path = tmp_path / "registers.json"
    mapping_path.write_text(
        json.dumps({"213X": {"name": "Typo", "type": "RAW"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid register map key '213X'"):
        RegisterMap(str(mapping_path))


def test_backend_register_map_separation_uses_actual_loaded_maps():
    from core.foxair_phnix_core import RegisterMap

    main = RegisterMap(str(MAIN_MAP_PATH))
    display = RegisterMap(str(DISPLAY_MAP_PATH))

    # Warmlink and Standard-Modbus pass only MainWindow.regmap into ReaderWorker.
    warmlink_regs = set(main.items)
    standard_modbus_regs = set(main.items)

    assert DISPLAY_ONLY_REGISTERS.isdisjoint(warmlink_regs)
    assert DISPLAY_ONLY_REGISTERS.isdisjoint(standard_modbus_regs)

    # Modbus Display keeps normal WP registers in the main map and display-only
    # / virtual registers in the separate display map.
    assert set(range(3012, 3022)).issubset(display.items)
    assert {91105, 91108}.issubset(display.items)
    assert {2122, 2133}.issubset(main.items)
    assert set(range(3012, 3022)).isdisjoint(main.items)
    assert {2122, 2124}.isdisjoint(display.items)
