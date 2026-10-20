"""V3.5 catalog integration using synthetic direct-mainboard Modbus traffic."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import foxair_phnix_control as gui
from cloud.cloud_write_helpers import cloud_code_for_register
from cloud.warmlink_codes import WARMLINK_CLOUD_CODE_HINTS
from core.foxair_phnix_core import (
    RegisterMap, build_write_frame, crc_bytes_le, decode_frame,
    decode_read_response_registers, find_frames, numeric_value_by_type,
)
from dialogs.parameter_settings_dialog import ParameterSettingsDialog
from test_warmlink_request_scheduler import application, window

ROOT = Path(__file__).parents[1]
MAP_PATH = ROOT / 'data/foxair_phnix_registers.json'
KNOWLEDGE_PATH = ROOT / 'data/foxair_phnix_knowledge.json'
DEFS = json.loads(MAP_PATH.read_text(encoding='utf-8'))
KNOWLEDGE = json.loads(KNOWLEDGE_PATH.read_text(encoding='utf-8'))
REGMAP = RegisterMap(str(MAP_PATH))
ENGINEERING = set(range(8802, 8809))


def decoded_response(reg, word, slave=1):
    body = bytes([slave, 3, 2]) + word.to_bytes(2, 'big')
    frame = decode_frame(find_frames(bytearray(body + crc_bytes_le(body)))[0], REGMAP)
    return decode_read_response_registers(frame, reg, REGMAP)[0]


@pytest.mark.parametrize('reg', sorted(ENGINEERING))
def test_engineering_metadata_documents_direct_volatile_signed_registers(reg):
    item = DEFS[str(reg)]
    assert item['firmware'] == 'V3.5+'
    assert item['function'] == '03/06/16' and item['mode'] == 'r/w'
    assert item['interface'] == 'direct_user_modbus'
    assert item['ram_address'] == f'0x{0x20016980 + 2*(reg-8801):08X}'
    assert item['signed'] and item['storage_type'] == 'int16'
    assert item['ui_visibility'] == 'engineering'
    assert 'volatile RAM' in item['persistence']
    assert 'im untersuchten direkten fc06-/fc16-schreibpfad' in item['notes'].lower()
    assert 'keine garantierte Wiederherstellung' in item['notes']
    assert not set(item) & {'min', 'max', 'rangeStart', 'rangeEnd', 'write_min', 'write_max', 'default'}
    assert cloud_code_for_register(reg) is None
    assert all(hint.get('modbus_register') != reg for hint in WARMLINK_CLOUD_CODE_HINTS.values())
    assert cloud_code_for_register(reg, require_write_allowed=True) is None
    assert not item.get('cloud_aliases')


@pytest.mark.parametrize('reg', [8802, 8803, 8804, 2017])
@pytest.mark.parametrize('word,expected', [(0, '0.0 °C'), (0xFFF1, '-1.5 °C'), (0x8000, '-3276.8 °C'), (0x7FFF, '3276.7 °C')])
@pytest.mark.parametrize('slave', [1, 0x63])
def test_scaled_signed_temperature_read_response(reg, word, expected, slave):
    decoded = decoded_response(reg, word, slave)
    assert decoded.display_value == expected
    assert decoded.raw_value == word
    assert decoded.signed_value == (word if word < 0x8000 else word - 0x10000)
    assert numeric_value_by_type(word, decoded.dtype) == float(expected.split()[0])
    assert decoded.name == DEFS[str(reg)]['name']


@pytest.mark.parametrize('reg', [8805, 8806, 8807, 8808])
@pytest.mark.parametrize('word,expected', [(0, '0'), (0xFFFF, '-1'), (0x8000, '-32768'), (0x7FFF, '32767')])
@pytest.mark.parametrize('slave', [1, 0x63])
def test_unscaled_engineering_words_remain_signed_and_unitless(reg, word, expected, slave):
    assert decoded_response(reg, word, slave).display_value == expected
    assert DEFS[str(reg)]['type'] == 'INT16'
    assert 'unit' not in DEFS[str(reg)]
    assert 'offen' in DEFS[str(reg)]['description']


@pytest.mark.parametrize('slave', [1, 0x63])
def test_observed_engineering_fc16_uses_catalog_instead_of_unknown_service_type(slave):
    raw = build_write_frame(8803, 0xFFF1, slave_addr=slave)
    decoded = decode_frame(find_frames(bytearray(raw))[0], REGMAP).registers[0]
    assert decoded.reg == 8803 and decoded.dtype == 'TEMP1'
    assert decoded.signed_value == -15 and decoded.display_value == '-1.5 °C'


def test_engineering_parameters_use_existing_visibility_gate():
    owner = SimpleNamespace(register_defs=DEFS, settings={})
    dialog = SimpleNamespace(main_window=owner, PARAM_RE=ParameterSettingsDialog.PARAM_RE)
    items = ParameterSettingsDialog._collect_parameter_items(dialog)
    assert ENGINEERING.isdisjoint(item['reg'] for item in items)
    owner.settings['show_engineering_parameters'] = True
    items = ParameterSettingsDialog._collect_parameter_items(dialog)
    assert ENGINEERING.issubset(item['reg'] for item in items)
    for item in items:
        if item['reg'] in (8807, 8808):
            assert item['name'].startswith('[Engineering] Engineering-Korrekturwert')


def test_8803_selection_and_zone_reserve_semantics_are_explicit():
    description = DEFS['8803']['description']
    for fragment in ('MAIN:1334=0', 'MAIN:1540=0', '1334=7 unwirksam',
                     '8801=2 (Neutral)', '1334=4', '1540!=0', '8025',
                     'Heizkurve/Außentemperaturführung', 'R10-/R11', 'Kein universeller'):
        assert fragment in description
    for reg, source, zone, warmlink in [(8805, '+0x0A', '0x2001606C +0x9E', '8027'),
                                       (8806, '+0x0C', '0x20016110 +0x9E', '8028')]:
        text = DEFS[str(reg)]['description']
        assert all(fragment in text for fragment in (source, zone, warmlink, 'addiert oder subtrahiert'))
    for reg, field in [(8807, '+0x06'), (8808, '+0x08')]:
        text = DEFS[str(reg)]['description']
        assert all(fragment in text for fragment in (field, '1540=0', '1540!=0', '1334=7', 'übersprungen'))


def test_effective_heating_status_replaces_invalid_1557_and_keeps_sources_separate():
    item = DEFS['2017']
    assert item['name'] == 'Effektiver Heiz-Wassersollwert'
    assert item['firmware'] == 'V3.5+'
    assert item['mode'] == 'read' and item['function'] == '03'
    assert item['write_allowed'] is False and item['signed'] is True
    assert item['getter'] == '0x0808261C'
    assert int(item['status_buffer_offset'], 16) == 0x820 + 2*(2017 - 2001)
    assert 'unabhängig' in item['description'] and 'R10/R11' in item['description']
    assert '1557' not in DEFS and '1557' not in KNOWLEDGE
    assert 1557 not in REGMAP.items
    assert {8791, 8794}.isdisjoint(REGMAP.items)
    assert '+0x06' in DEFS['2013']['description']
    assert 'nicht abschließend bewiesen' in DEFS['2013']['description']
    for reg in (2014, 2016):
        text = DEFS[str(reg)]['description']
        assert all(fragment in text for fragment in ('+0x56', 'Heiz-', 'Warmwasser-', 'Kühlsollwertpfad'))
    assert DEFS['2013']['name'] == 'Temperaturwert nach Begrenzung'
    assert DEFS['2014']['name'] == 'Temperaturwert nach Wetterkompensation während des Heizens'
    assert DEFS['2016']['name'] == 'Solltemperatur wie 2014'


def test_loaded_knowledge_does_not_restore_stale_status_descriptions():
    old_knowledge = {**KNOWLEDGE, '1557': {'description': 'Alter ungültiger Heizsollwert-Alias'}}
    owner = SimpleNamespace(regmap_path=str(MAP_PATH), knowledge_defs=old_knowledge)
    loaded = gui.MainWindow._load_register_defs(owner)
    assert '1557' not in loaded
    for reg in ('2013', '2014', '2016', '2017'):
        assert loaded[reg]['description'] == DEFS[reg]['description']


@pytest.mark.parametrize('reg,text,expected', [(8802, '-1.5', 0xFFF1), (8803, '-1,5', 0xFFF1),
    (8804, '2.3', 23), (8805, '-1', 0xFFFF), (8806, '-32768', 0x8000),
    (8807, '-15', 0xFFF1), (8808, '32767', 0x7FFF)])
def test_existing_direct_fc06_write_path_encodes_signed_engineering_input(window, reg, text, expected):
    window.backend_combo.setCurrentIndex(window.backend_combo.findData('standard_modbus'))
    value = window.parse_register_write_value(reg, text)
    window.send_register_write(reg, value, slave_addr=1)
    window.worker._flush_write_queue()
    wire = window._test_transmitted[-1]
    assert wire[0:2] == b'\x01\x06'
    assert int.from_bytes(wire[2:4], 'big') == reg
    assert int.from_bytes(wire[4:6], 'big') == expected
