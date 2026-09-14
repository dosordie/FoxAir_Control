import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.foxair_phnix_core import RegisterMap, format_value_by_type


REGISTER_MAP_PATH = ROOT / "data" / "foxair_phnix_registers.json"


def test_fault_register_definitions_include_reconstructed_dwin_texts():
    regmap = RegisterMap(str(REGISTER_MAP_PATH))

    assert regmap.get(2083).bit_map[7] == "F24 – EEPROM beschädigt / ungültige Fehlerdaten"
    assert regmap.get(2084).bit_map[15] == "F109 – Lüftertreiber Überdrehzahlschutz"
    assert regmap.get(2085).bit_map[13] == "E035 – Niedriger Wasserdurchfluss – Schutz"
    assert regmap.get(2086).bit_map[3] == "E103 – Lüftermotor 1 Überlastfehler"
    assert regmap.get(2086).bit_map[4] == "E203 – Lüftermotor 2 Überlastfehler"
    assert regmap.get(2086).bit_map[13] == "E08g – Kommunikationsfehler Thermostat Zone 1"
    assert regmap.get(2086).bit_map[14] == "E08h – Kommunikationsfehler Thermostat Zone 2"
    assert regmap.get(2087).bit_map[10] == "E035 – Niedriger Wasserdurchfluss – Schutz (3+)"
    assert regmap.get(2089).bit_map[7] == "P03a – Pufferspeicher-Temperatursensorfehler"
    assert regmap.get(2090).bit_map[14] == "E08c – Kommunikationsfehler Hydraulikmodul"
    assert regmap.get(2019).bit_map[10] == "011 Alarm-Ausgang (0=AUS/1=EIN)"


def test_protection_limit_status_register_uses_generic_bitfield_decoder():
    info = RegisterMap(str(REGISTER_MAP_PATH)).get(2139)

    assert info.dtype == "BITFIELD"
    assert set(info.bit_map) == {1, 3, 4, 5, 6}
    assert format_value_by_type(0x0020, info.dtype, bit_map=info.bit_map) == (
        "0x0020: B5: AC-Eingangsstrom-Begrenzung / T35"
    )
    assert format_value_by_type(0x0012, info.dtype, bit_map=info.bit_map) == (
        "0x0012: B1: A24 – Wasserspreizung / Temperaturdifferenz T01-T02 zu groß; "
        "B4: A38 – Niederdruck-Frequenzbegrenzung"
    )


def test_fault_decoder_includes_error_10_and_preserves_unknown_bits():
    source = (ROOT / "dialogs" / "decoder_dialogs.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    fault_decoder = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "FaultDecoderDialog"
    )
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in fault_decoder.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }

    assert assignments["FAULT_REGS"][-1] == 2084
    assert assignments["FAULT_TITLES"][2084] == "Fehler 10"
    assert 'bit_map.get(bit, "Fehlerbit aktiv, Klartext noch unbekannt")' in source


def test_fault_decoder_keeps_complete_error_register_block_read():
    source = (ROOT / "dialogs" / "decoder_dialogs.py").read_text(encoding="utf-8")

    assert "send_read_request(2081, 10" in source
    assert "Alarm-Ausgang: Register 2019 Bit 10" in source
