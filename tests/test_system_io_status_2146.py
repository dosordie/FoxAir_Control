from pathlib import Path

from core.foxair_phnix_core import decode_system_io_status_2146

ROOT = Path(__file__).resolve().parents[1]


def test_main_2146_practical_decoder_baseline_and_dynamic_states():
    baseline = decode_system_io_status_2146(0x022C)
    assert baseline["raw"] == 0x022C
    assert baseline["summer_shutdown"] is False
    assert baseline["s10_control_active"] is False
    assert baseline["io_qualification_inhibit"] is False
    assert baseline["hyd61_status_bit1"] is False
    assert baseline["v35_capability_bit"] is True
    assert baseline["s10_state"] == "S10-Hardwaresteuerung nicht aktiv"

    summer = decode_system_io_status_2146(0x022C | 0x0010)
    assert summer["summer_shutdown"] is True

    s10 = decode_system_io_status_2146(0x022C | 0x0040)
    assert s10["s10_control_active"] is True
    assert "aktiv / freigegeben" in s10["s10_state"]

    inhibit = decode_system_io_status_2146(0x022C | 0x0040 | 0x0100)
    assert inhibit["io_qualification_inhibit"] is True
    assert "gesperrt" in inhibit["s10_state"]

    hyd = decode_system_io_status_2146(0x022C | 0x0002)
    assert hyd["hyd61_status_bit1"] is True


def test_main_2146_ui_reads_adjacent_hyd61_value_and_keeps_raw_status_visible():
    dialogs = (ROOT / "dialogs" / "decoder_dialogs.py").read_text(encoding="utf-8")
    main = (ROOT / "foxair_phnix_control.py").read_text(encoding="utf-8")

    assert "class SystemIOStatusDecoderDialog" in dialogs
    assert 'READ_LABEL = "System-/I/O-Status 2146-2147"' in dialogs
    assert "send_read_request(2146, 2" in dialogs
    assert "HYD61:2049 Bit1" in dialogs
    assert "2147 / HYD61:2050" in dialogs
    assert "120 Scheduler-Ticks = 60 s" in dialogs

    assert 'QPushButton("System-/I/O-Status ...")' in main
    assert "self.system_io_popup_btn.clicked.connect(self.open_system_io_decoder)" in main
    assert "SystemIOStatusDecoderDialog.READ_LABEL" in main
