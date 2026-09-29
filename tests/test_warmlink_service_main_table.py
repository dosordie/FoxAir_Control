from pathlib import Path
from types import SimpleNamespace

import pytest

from core.foxair_phnix_core import (
    DecodedFrame,
    RegisterMap,
    crc16_modbus,
    decode_frame,
    decode_read_response_registers,
    find_frames,
)


def _map() -> RegisterMap:
    return RegisterMap("")


def _fc10(start: int, values: list[int]) -> bytes:
    data = b"".join((value & 0xFFFF).to_bytes(2, "big") for value in values)
    body = bytes([0x63, 0x10]) + start.to_bytes(2, "big") + len(values).to_bytes(2, "big") + bytes([len(data)]) + data
    return body + crc16_modbus(body).to_bytes(2, "little")


def _decode_fc10(start: int, values: list[int]):
    frames = find_frames(bytearray(_fc10(start, values)))
    assert len(frames) == 1
    return decode_frame(frames[0], _map())


def test_known_service_register_uses_metadata():
    register = _decode_fc10(8022, [42]).registers[0]
    assert register.reg == 8022
    assert register.raw_value == 42
    assert "Heating Compressor Frequency Cap" in register.name
    assert register.dtype == "uint16"
    assert register.slave_addr == 0x63


def test_signed_service_register_keeps_raw_and_signed_values():
    register = _decode_fc10(8055, [0xFFFF]).registers[0]
    assert register.raw_value == 0xFFFF
    assert register.signed_value == -1
    assert register.display_value == "-1"
    assert register.dtype == "signed int16"


def test_unknown_8xxx_service_register_is_not_discarded():
    register = _decode_fc10(8099, [123]).registers[0]
    assert register.reg == 8099
    assert register.raw_value == 123
    assert register.name == "Warmlink Service Register 8099"
    assert register.dtype == "RAW"


def test_fc10_multiple_write_decodes_each_service_register():
    registers = _decode_fc10(8021, [0, 42, 0, 0xFFFF]).registers
    assert [(reg.reg, reg.raw_value) for reg in registers] == [
        (8021, 0), (8022, 42), (8023, 0), (8024, 0xFFFF),
    ]
    assert registers[-1].signed_value == -1


def test_dual_logger_forwards_fc10_service_values_to_normal_main_path():
    app = pytest.importorskip("foxair_phnix_control", exc_type=ImportError)
    frame = _decode_fc10(8021, [0, 42, 0])
    applied = []
    logger = SimpleNamespace(
        warmlink_frames=0,
        _apply_regs_to_main_window=lambda regs, source: applied.append((list(regs), source)),
        _remember_warmlink_values=lambda _frame: None,
        _frame_summary=lambda *_args: None,
        _update_status=lambda: None,
        warmlink_last={},
    )

    app.DualBusLoggerDialog.on_warmlink_frame(logger, frame)

    assert [[reg.reg for reg in regs] for regs, _source in applied] == [[8021, 8022, 8023]]
    assert "0x63" in applied[0][1]


def test_service_context_menu_does_not_offer_user_write():
    qt_widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.context_menu_helpers import RegisterContextAction, build_register_context_menu

    application = qt_widgets.QApplication.instance() or qt_widgets.QApplication([])
    parent = qt_widgets.QWidget()
    menu, action_map = build_register_context_menu(parent, 8055, slave_addr=0x63)
    actions = {result.action for result in action_map.values()}
    assert RegisterContextAction.QUICK_WRITE not in actions
    assert RegisterContextAction.USE_WRITE_ADDRESS not in actions
    assert RegisterContextAction.READ_ONE in actions
    menu.deleteLater()
    parent.deleteLater()
    assert application is not None


def test_explicit_read_response_uses_service_metadata():
    frame = DecodedFrame(0x63, 0x03, 0, 2, b"\x00*", b"", b"", "read-response", [], True, 0, 0)
    register = decode_read_response_registers(frame, 8022, _map())[0]
    assert (register.reg, register.raw_value, register.name) == (
        8022, 42, "Heating Compressor Frequency Cap",
    )


def test_service_dialog_and_settings_button_are_removed():
    root = Path(__file__).parents[1]
    source = (root / "foxair_phnix_control.py").read_text(encoding="utf-8")
    assert not (root / "dialogs" / "warmlink_service_dialog.py").exists()
    assert "WarmlinkServiceDialog" not in source
    assert "Warmlink Service / Engineering ..." not in source
