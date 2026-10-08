import json
from pathlib import Path

from cloud.warmlink_codes import cloud_hint
from cloud.warmlink_value_translator import translate_cloud_value


DEFS = json.loads((Path(__file__).parents[1] / "data/foxair_phnix_registers.json").read_text(encoding="utf-8"))


def test_output_bitword_uses_register_bit_map():
    value = translate_cloud_value("O01~023", "0000010000000000", DEFS["2019"], cloud_hint("O01~023"))
    assert value.raw == 0x0400
    assert value.active_bits[0].bit == 10
    assert "Alarm-Ausgang" in value.display


def test_unknown_fault_bit_remains_visible():
    value = translate_cloud_value("Fault8", "0000001000000000", DEFS["2088"], cloud_hint("Fault8"))
    assert value.raw == 0x0200
    assert "Bit 9 aktiv" in value.display
    assert "unbekannt" in value.display


def test_known_fault_bit_uses_existing_register_text():
    value = translate_cloud_value("Fault8", "0000000010000000", DEFS["2088"], cloud_hint("Fault8"))
    assert value.raw == 0x0080
    assert "Externer Außentemperaturfühler Fehler" in value.display


def test_contact_word_reuses_contact_decoder_semantics():
    value = translate_cloud_value("S01~S10", "0011000000000000", DEFS["2034"], cloud_hint("S01~S10"))
    assert value.raw == 0x3000
    assert {bit.bit for bit in value.active_bits} >= {12, 13}
    assert "SG Kontakt 1" in value.display
