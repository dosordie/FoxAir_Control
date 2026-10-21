"""Live GL9 examples as synthetic values; no account, network or hardware."""
from types import SimpleNamespace

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QMessageBox

from cloud.operating_timer import (M_TIMER_CODES, M_CODE_REGISTERS, M_MASK_CODES,
    M_SCALED_CODES, m_timer_word, m_timer_write_value)
from cloud.cloud_write_helpers import (cloud_code_for_register, validate_cloud_commands,
    cloud_readback_matches, cloud_command_batches)
from cloud.register_resolver import resolve_cloud_register
from cloud.warmlink_codes import cloud_hint, merged_cloud_metadata
from cloud.warmlink_api import WarmLinkCloudApi
from cloud.mapping_audit import audit_cloud_mappings
from dialogs.cloud_dialog import WarmLinkCloudDialog
from dialogs.timer_editor_dialog import TimerEditorDialog
from workers.warmlink_cloud_worker import WarmLinkCloudCommandWorker
from test_cloud_single_read_and_values import application, cloud_row
from test_cloud_decoders_silent_timer import capture
from test_control_transport import command_api, CommandApi
from test_csv_logger_transport import wait_for
from test_warmlink_request_scheduler import window


# Independent specification anchors, not values generated from production hints.
SPEC_BASES = (1281, 1288, 1295, 1302, 1309, 1316)
SPEC_FIELDS = ('Start', 'End', 'Hot Water Target', 'Heating Target',
               'Cooling Target', 'Mode', 'Max. Power')
EXPECTED_CODES = {
    **{base + offset: f'M{timer} {suffix}' for timer, base in enumerate(SPEC_BASES, 1)
       for offset, suffix in enumerate(SPEC_FIELDS)},
    1323: 'M1_2 Enalbe', 1324: 'M3_4 Enalbe', 1325: 'M5_6 Enalbe',
}
LIVE_EXAMPLES = {
    'Start': (1024, 'DIGI1'), 'End': (5947, 'DIGI1'),
    'Hot Water Target': (55.0, 'TEMP'), 'Heating Target': (41.0, 'TEMP'),
    'Cooling Target': (7.0, 'TEMP'), 'Mode': (9, 'ENUM'), 'Max. Power': (1.2, 'DIGI5'),
}


def rows():
    result = []
    for reg, code in EXPECTED_CODES.items():
        if reg >= 1323:
            value = {1323: '0000000011111111', 1324: '0000000001101111', 1325: '0000000000000000'}[reg]
            dtype = 'BINARY'
        else:
            value, dtype = LIVE_EXAMPLES[code.split(' ', 1)[1]]
        result.append(cloud_row(value, code, dataType=dtype, rangeStart=13.5 if code.endswith('Cooling Target') else 0,
                                rangeEnd=53 if code.endswith('Hot Water Target') else 10000))
    return result


def opened(window, monkeypatch, supplied=None):
    requests = capture(window, monkeypatch)
    monkeypatch.setattr(window, '_display_wait_for_param_blocks_before_popup', lambda *a: pytest.fail('No local prerequisite for Cloud'))
    window.open_timer_editor()
    dialog = window.timer_dialog
    dialog.initial_read_timer.stop()
    dialog.read_from_wp()
    dialog.cloud_read_finished(requests[-1].cycle_id, rows() if supplied is None else supplied, '')
    return dialog, requests


@pytest.mark.parametrize('reg,code', list(EXPECTED_CODES.items()))
def test_all_45_explicit_schema_routes_and_grants_have_honest_evidence(reg, code):
    assert cloud_code_for_register(reg) == cloud_code_for_register(reg, True) == code
    hint = cloud_hint(code)
    assert resolve_cloud_register(code, hint) == reg
    assert hint['confidence'] == 'derived'
    assert hint['cloud_read_live_confirmed'] and hint['gl9_tested_supported']
    assert hint['modbus_comparison_confirmed'] is False
    assert hint['cloud_write_live_confirmed'] is False
    assert merged_cloud_metadata(code)['write_confirmed'] is False
    assert hint['write_allowed']


def test_unknown_codes_are_not_promoted_and_audit_preserves_derived_status():
    for code in ('M7 Start', 'M1_2 Enable', 'W1 Start', 'DP1'):
        assert resolve_cloud_register(code, cloud_hint(code)) is None
        with pytest.raises(ValueError): validate_cloud_commands([(code, '1')])
    wrong = {**cloud_hint('M1 Start'), 'modbus_register': 1282}
    assert resolve_cloud_register('M1 Start', wrong) is None
    report = audit_cloud_mappings(rows())
    assert report['errors'] == []
    relevant = [r for r in report['codes'] if r['code'] in M_CODE_REGISTERS]
    assert len(relevant) == 45 and all(r['derived_mapped'] and not r['confirmed_mapped'] for r in relevant)


@pytest.mark.parametrize('code,value,word', [
    ('M1 Start', 0, 0), ('M1 Start', 1024, 0x400), ('M1 Start', 1536, 0x600), ('M6 End', 5947, 0x173B),
    ('M1 Hot Water Target', '50.5', 505), ('M1 Heating Target', '-1.5', 65521),
    ('M2 Cooling Target', '8.0', 80), ('M2 Max. Power', '1.2', 12), ('M6 Max. Power', '0.0', 0),
    ('M1 Mode', '9', 9), ('M1 Mode', '77', 77),
    ('M1_2 Enalbe', '0000000011111111', 255), ('M3_4 Enalbe', '0000000001101111', 111),
    ('M5_6 Enalbe', '0000000000000000', 0),
])
def test_live_formats_are_distinct(code, value, word):
    assert m_timer_word(code, value) == word
    if code != 'M1 Mode' or word == 9:
        encoded = m_timer_write_value(code, word)
        assert m_timer_word(code, encoded) == word
        assert validate_cloud_commands([(code, encoded)]) == ((code, encoded),)


@pytest.mark.parametrize('value', [None, '', 'nan', 'inf', True, 'bad'])
@pytest.mark.parametrize('code', ['M1 Start', 'M1 Heating Target', 'M1_2 Enalbe'])
def test_missing_invalid_words_are_never_zero(code, value):
    with pytest.raises((ValueError, TypeError)): m_timer_word(code, value)


@pytest.mark.parametrize('value', [60, 256*24, '1.5', -1, 65536])
def test_invalid_clock_words_rejected(value):
    with pytest.raises(ValueError): validate_cloud_commands([('M1 Start', value)])


@pytest.mark.parametrize('code,wanted,actual,match', [
    ('M1 Start', '5947', 5947, True), ('M1 Mode', '9', 9.1, False),
    ('M1_2 Enalbe', '0000000011111111', '0000000011111111', True),
    ('M1 Heating Target', '50.5', 50.500000001, True), ('M1 Heating Target', '50.5', 50.6, False), ('M1 Heating Target', '50.5', 50.55, False),
    ('M1 Max. Power', '1.2', 1.21, True), ('M1 Max. Power', '1.2', 12, False),
])
def test_fresh_readback_units_and_resolution(code, wanted, actual, match):
    assert cloud_readback_matches(code, wanted, cloud_row(actual, code)) == match
    assert not cloud_readback_matches(code, wanted, cloud_row(actual, code, cached=True))


def test_cloud_autoload_45_and_no_implicit_write_or_metadata_clamp(window, monkeypatch):
    requests = capture(window, monkeypatch)
    monkeypatch.setattr(window, '_display_wait_for_param_blocks_before_popup', lambda *a: pytest.fail('Cloud bypass'))
    monkeypatch.setattr(window, 'send_read_request', lambda *a, **kw: pytest.fail('No local reads'))
    monkeypatch.setattr(window, 'send_cloud_write', lambda *a, **kw: pytest.fail('No write on open/read'))
    window.latest_regs[1283] = SimpleNamespace(raw_value=100)
    window.open_timer_editor(); d = window.timer_dialog
    assert d.windowTitle() == 'Betriebsart Timer 1-6'
    assert not d.send_btn.isEnabled() and d.fields[1]['ww_temp'].text() == '—'
    QTest.qWait(300)
    assert len(requests) == 1 and set(requests[0].codes) == set(M_TIMER_CODES.values())
    dispatcher = WarmLinkCloudDialog(window)
    dispatcher._on_targeted_snapshot('operating_timer', requests[0].cycle_id, rows(), '')
    assert '45/45' in d.status_label.text() and len(d._baseline) == 45
    f = d.fields[1]
    assert (f['on_hour'].value(), f['off_hour'].value(), f['off_min'].value()) == (4, 23, 59)
    assert f['ww_temp'].value() == 55 and f['cool_temp'].value() == 7 and f['power_kw'].value() == 1.2
    assert f['mode_combo'].currentData() == 9
    assert window.cloud_overlay_by_reg[1283]['engineering_value'] == 55
    assert window.cloud_overlay_by_reg[1287]['engineering_value'] == 1.2
    assert not d._dirty and not d._dirty_days and not d.send_btn.isEnabled()
    d.send_values()
    assert 'Keine geänderten' in d.status_label.text()
    assert not hasattr(d, 'timer_delay_ms') and not hasattr(d, 'auto_update_cb')
    assert all(not {'power_raw', 'day_raw', 'mode_raw'} & f.keys() for f in d.fields.values())
    labels = [w.text() for w in d.findChildren(QLabel)]
    assert not any('Raw' in s or 'Pause zwischen' in s for s in labels)
    d.close(); dispatcher.close()


@pytest.mark.parametrize('failure', ['missing', 'stale', 'cached', 'currentEmpty', 'invalid', 'timeout'])
def test_partial_snapshot_cannot_write_missing_baseline(window, monkeypatch, failure):
    sample = rows(); first = sample[0]
    if failure == 'missing': sample.pop(0)
    elif failure == 'invalid': first['value'] = 255
    elif failure != 'timeout': first[failure] = True
    d, requests = opened(window, monkeypatch, sample)
    if failure == 'timeout': d.read_from_wp(); d._cloud_timeout()
    assert len(d._baseline) < 45
    d.fields[1]['heat_temp'].setValue(42)
    assert not d.send_btn.isEnabled()
    monkeypatch.setattr(window, 'control_write_registers', lambda *a, **kw: pytest.fail('Incomplete baseline'))
    d.send_values()
    assert 'unvollständig' in d.status_label.text()
    d.close()


def test_zeroes_unknown_modes_and_reload_preserve_drafts(window, monkeypatch):
    sample = rows()
    for row in sample:
        if row['code'] in ('M1 Start', 'M1 End', 'M1 Max. Power'): row['value'] = 0
        if row['code'] == 'M1 Mode': row['value'] = 77
    d, req = opened(window, monkeypatch, sample)
    assert len(d._baseline) == 45 and d.fields[1]['power_kw'].value() == 0
    assert d.fields[1]['mode_combo'].currentData() == 77 and 'Unbekannter' in d.fields[1]['mode_combo'].currentText()
    d.fields[1]['heat_temp'].setValue(50.5); d.fields[1]['heat_temp'].clearFocus()
    window.open_timer_editor(); assert window.timer_dialog is d and d.fields[1]['heat_temp'].value() == 50.5
    d.read_from_wp(); d.cloud_read_finished(req[-1].cycle_id, sample, '')
    assert d.fields[1]['heat_temp'].value() == 50.5
    sent = []
    monkeypatch.setattr(window, 'control_write_registers', lambda *a, **kw: sent.append((a, kw)))
    d.send_values()
    assert sent[0][0][0] == [(1284, 505, None)]
    d.close()


@pytest.mark.parametrize('timer', range(1, 7))
def test_one_timer_keeps_partner_byte_and_ignores_other_timer_draft(window, monkeypatch, timer):
    d, _ = opened(window, monkeypatch)
    reg = d._timer_bit_reg(timer)
    d._apply_cloud_snapshot({**d._baseline, reg: 0xA55A})
    other = timer-1 if timer % 2 == 0 else timer+1
    d.fields[other]['active_cb'].toggle()  # An unsaved draft in another tab must not be sent.
    d.fields[timer]['active_cb'].toggle()
    d.tabs.setCurrentIndex(timer-1)
    sent = []
    monkeypatch.setattr(window, 'control_write_registers', lambda *a, **kw: sent.append((a, kw)))
    d.send_values()
    assert sent[0][0][0] == [(reg, 0xA55A ^ (0x8000 if timer % 2 == 0 else 0x80), None)]
    assert sent[0][1]['mask_baselines'] == {M_TIMER_CODES[reg]: 0xA55A}
    d.close()


def run_m(commands, baselines=None, guard=None):
    worker = WarmLinkCloudCommandWorker('user', 'unused', 'device', *commands[0],
        dry_run=False, commands=commands, mask_baselines=baselines, write_guard=guard)
    results, errors = [], []
    worker.result.connect(results.append); worker.error.connect(errors.append)
    worker.run()
    return results, errors


def test_mixed_disable_enable_uses_verified_barriers_without_changing_partner(command_api):
    commands = (('M1 Heating Target', '50.5'), ('M1_2 Enalbe', f'{0x8001:016b}'))
    r, e = run_m(commands, {'M1_2 Enalbe': 0x0181})
    assert not e and r[-1]['sequence_complete']
    writes = [c[2] for c in CommandApi.created[0].calls if c[0] == 'write']
    assert writes == [(('M1 Heating Target', '50.5'),), (('M1_2 Enalbe', f'{0x8001:016b}'),)]
    assert r[0]['confirmed_codes'] == ['M1 Heating Target']
    assert r[-1]['confirmed_codes'] == ['M1 Heating Target', 'M1_2 Enalbe']
    commands = (('M1_2 Enalbe', f'{0xFF01:016b}'),)
    assert cloud_command_batches(commands, mask_baselines={'M1_2 Enalbe': 0xFF81}) == (commands,)


@pytest.mark.parametrize('failure', ['stale', 'missing', 'mismatch', 'exception'])
def test_barrier_failure_never_retries_writes_or_enables(command_api, monkeypatch, failure):
    def read(self, device, codes):
        self.calls.append(('readback', device, codes))
        if failure == 'exception': raise TimeoutError('synthetic')
        return {'isReusltSuc': True, 'objectResult': [] if failure == 'missing' else [
            {'code': codes[0], 'value': f'{0:016b}' if failure == 'mismatch' else self.values[codes[0]], 'stale': failure == 'stale'}]}
    monkeypatch.setattr(CommandApi, 'get_data_by_code', read)
    r, e = run_m((('M1_2 Enalbe', f'{0x8001:016b}'), ('M1 Heating Target', '50.5')), {'M1_2 Enalbe': 0x0181})
    assert not e and not r[-1]['sequence_complete']
    assert len([c for c in CommandApi.created[0].calls if c[0] == 'write']) == 1


def test_full_preflight_before_login_or_api_and_binary_payload(command_api):
    r, e = run_m((('M1 Heating Target', '41.0'), ('M2 Start', '60')))
    assert e and not CommandApi.created
    r, e = run_m((('M1_2 Enalbe', '0000000011111111'),))
    assert e and not CommandApi.created
    payload = WarmLinkCloudApi('u','p')._write_control_primary_payload('device','M1_2 Enalbe','0000000011111111')
    assert payload == {'appId':'16','param':[{'deviceCode':'device','protocolCode':'M1_2 Enalbe','value':'0000000011111111'}]}


def test_editor_real_batch_decimal_readback_and_newer_edit_protection(window, monkeypatch, command_api):
    d, _ = opened(window, monkeypatch)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **kw: pytest.fail('No Cloud confirmation'))
    monkeypatch.setattr(window, '_ask_control_confirmation', lambda *a, **kw: pytest.fail('No Cloud confirmation'), raising=False)
    f = d.fields[1]
    f['ww_temp'].setValue(50.5); f['power_kw'].setValue(0)
    d.send_values()
    f['ww_temp'].setValue(55)  # Returning to the OLD baseline is still a new draft.
    wait_for(lambda: window.cloud_write_thread is None)
    writes = [c[2] for c in CommandApi.created[0].calls if c[0] == 'write']
    assert writes == [(('M1 Hot Water Target','50.5'), ('M1 Max. Power','0'))]
    assert d._baseline[1283] == 505 and d._baseline[1287] == 0
    assert f['ww_temp'].value() == 55 and 1283 in d._dirty and 1287 not in d._dirty
    d.close()


def test_all_six_changed_masks_are_unique_and_readback_partial_keeps_dirty(window, monkeypatch):
    d, _ = opened(window, monkeypatch)
    for f in d.fields.values(): f['active_cb'].toggle()
    sent = []
    monkeypatch.setattr(window, 'control_write_registers', lambda *a, **kw: sent.append((a, kw)))
    d.send_all_values()
    assert len(sent[0][0][0]) == 3
    assert {reg for reg, _, _ in sent[0][0][0]} == {1323, 1324, 1325}
    reg, raw, _ = sent[0][0][0][0]
    d.write_readback_result(reg, {'readback_verified': True, 'readback': cloud_row(f'{raw:016b}', M_TIMER_CODES[reg])})
    assert reg not in d._pending and len(d._pending) == 2
    assert d._dirty_days
    d.close()


@pytest.mark.parametrize('change', ['device','account','local','close'])
def test_late_snapshots_and_writes_cannot_touch_changed_context(window, monkeypatch, change):
    d, req = opened(window, monkeypatch)
    d.fields[1]['heat_temp'].setValue(50.5)
    d.read_from_wp(); old = req[-1]
    if change == 'close': d.close()
    elif change == 'device': window.set_cloud_connection_state(True, 'other')
    elif change == 'account': window.settings['warmlink_cloud']['username'] = 'other'; window._notify_control_connection_changed()
    else: window.connected = True; window._notify_control_connection_changed()
    assert old.cancelled.is_set()
    d.cloud_read_finished(old.cycle_id, rows(), '')
    if change != 'close': assert not d._baseline and not d._dirty
    d.close()


@pytest.mark.parametrize('backend', ['standard_modbus','warmlink_raw','display_modbus'])
def test_local_initial_read_delay_partner_and_dirty_after_focus_loss(window, monkeypatch, backend):
    window.backend_combo.blockSignals(True)
    window.backend_combo.setCurrentIndex(window.backend_combo.findData(backend)); window.backend_combo.blockSignals(False)
    prerequisite = []
    monkeypatch.setattr(window, '_display_wait_for_param_blocks_before_popup', lambda *a: prerequisite.append(a) or True)
    reads, writes = [], []
    monkeypatch.setattr(window, 'send_read_request', lambda *a, **kw: reads.append((a,kw)))
    monkeypatch.setattr(window, 'send_timer_values', lambda *a, **kw: writes.append((a,kw)))
    window.open_timer_editor(); d = window.timer_dialog
    QTest.qWait(300)
    assert prerequisite and reads[0][0] == (1281,45)
    for row in rows():
        reg = M_CODE_REGISTERS[row['code']]
        d.update_from_live_register(SimpleNamespace(reg=reg, raw_value=m_timer_word(row['code'],row['value'])))
    d.fields[1]['heat_temp'].setValue(50.5); d.fields[1]['heat_temp'].clearFocus()
    d.update_from_live_register(SimpleNamespace(reg=1284, raw_value=420), force=True)
    assert d.fields[1]['heat_temp'].value() == 50.5
    window.open_timer_editor(); assert d.fields[1]['heat_temp'].value() == 50.5
    d.send_values()
    assert writes[0][0] == (0x63, [(1284,505,'Timer 1')],1200)
    d.fields[1]['heat_temp'].setValue(42)  # Old baseline while write is pending.
    d.update_from_live_register(SimpleNamespace(reg=1284, raw_value=420), force=True)
    assert 1284 in d._dirty  # Old automatic response must not clear the newer draft.
    d.update_from_live_register(SimpleNamespace(reg=1284, raw_value=505), force=True)
    assert d.fields[1]['heat_temp'].value() == 42 and 1284 in d._dirty
    d.close()


def test_all_45_changed_values_use_one_parameter_batch_three_unique_mask_words(window, monkeypatch, command_api):
    d, _ = opened(window, monkeypatch)
    for f in d.fields.values():
        f['on_min'].setValue(1); f['off_min'].setValue(58)
        f['ww_temp'].setValue(50.5); f['heat_temp'].setValue(-1.5); f['cool_temp'].setValue(8)
        f['mode_combo'].setCurrentIndex(f['mode_combo'].findData(1))
        f['power_kw'].setValue(2.3); f['active_cb'].toggle()
    d.send_all_values()
    wait_for(lambda: window.cloud_write_thread is None)
    batches = [c[2] for c in CommandApi.created[0].calls if c[0] == 'write']
    sent = [item for batch in batches for item in batch]
    assert len(sent) == 45 and len(dict(sent)) == 45
    assert len([batch for batch in batches if len(batch) == 42]) == 1
    assert len([code for code, _ in sent if code in M_MASK_CODES]) == 3
    assert dict(sent)['M1 Heating Target'] == '-1.5'
    assert dict(sent)['M1 Max. Power'] == '2.3'
    assert not d._dirty and not d._dirty_days and not d._pending
    d.close()


def test_pure_disable_precedes_parameters_and_keeps_active_partner(command_api):
    commands = (('M1 Heating Target', '41'), ('M1_2 Enalbe', f'{0xFF01:016b}'))
    r, e = run_m(commands, {'M1_2 Enalbe': 0xFF81})
    assert not e and r[-1]['sequence_complete']
    assert [c[2] for c in CommandApi.created[0].calls if c[0] == 'write'] == [
        (('M1_2 Enalbe', f'{0xFF01:016b}'),), (('M1 Heating Target','41'),)]


@pytest.mark.parametrize('kind', ['device', 'account', 'close'])
def test_real_inflight_write_guard_stops_later_activation(window, monkeypatch, command_api, kind):
    d, _ = opened(window, monkeypatch)
    f = d.fields[2]; f['heat_temp'].setValue(50.5); f['active_cb'].setChecked(True)
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        # Cancel the existing Python event from inside the worker, without Qt calls.
        window._control_cloud_write_cancelled.set()
        return result
    monkeypatch.setattr(CommandApi, 'get_data_by_code', read)
    d.tabs.setCurrentIndex(1); d.send_values()
    if kind == 'device': window.set_cloud_connection_state(True, 'other')
    elif kind == 'account': window.settings['warmlink_cloud']['username'] = 'other'; window._notify_control_connection_changed()
    else: d.close()
    wait_for(lambda: window.cloud_write_thread is None)
    if CommandApi.created:
        writes = [item for c in CommandApi.created[0].calls if c[0] == 'write' for item in c[2]]
        assert not any(code in M_MASK_CODES for code, _ in writes)
    d.close()


def test_unread_partner_and_invalid_clock_cannot_send_locally(window, monkeypatch):
    monkeypatch.setattr(window, '_display_wait_for_param_blocks_before_popup', lambda *a: True)
    window.open_timer_editor(); d = window.timer_dialog; d.initial_read_timer.stop()
    monkeypatch.setattr(window, 'send_timer_values', lambda *a, **kw: pytest.fail('Unread partner'))
    for reg in range(1281, 1288):
        raw = 9 if reg == 1286 else 100 if reg not in (1281,1282) else 0
        d.update_from_live_register(SimpleNamespace(reg=reg, raw_value=raw))
    d.fields[1]['heat_temp'].setValue(50.5)
    d.send_values(); assert 'Partner-Byte' in d.status_label.text()
    d.update_from_live_register(SimpleNamespace(reg=1323, raw_value=0))
    d.update_from_live_register(SimpleNamespace(reg=1281, raw_value=60))
    assert 1281 not in d._baseline and d.fields[1]['on_min'].text() == '—'
    d.send_values(); assert 'unvollständig' in d.status_label.text()
    d.close()


def test_partial_worker_readback_keeps_only_unconfirmed_editor_fields_dirty(window, monkeypatch, command_api):
    d, _ = opened(window, monkeypatch)
    original = CommandApi.get_data_by_code
    def read(self, device, codes):
        result = original(self, device, codes)
        result['objectResult'] = [r for r in result['objectResult'] if r['code'] != 'M1 Max. Power']
        return result
    monkeypatch.setattr(CommandApi, 'get_data_by_code', read)
    d.fields[1]['heat_temp'].setValue(50.5); d.fields[1]['power_kw'].setValue(2.3)
    d.send_values(); wait_for(lambda: window.cloud_write_thread is None)
    assert 1284 not in d._dirty and 1287 in d._dirty
    assert d._baseline[1284] == 505 and d._baseline[1287] == 12
    assert 'fehlt' in d.status_label.text() and d.fields[1]['power_kw'].value() == 2.3
    assert len([c for c in CommandApi.created[0].calls if c[0] == 'write']) == 1
    d.close()


def test_local_cancel_does_not_leave_a_phantom_pending_write(window, monkeypatch):
    monkeypatch.setattr(window, '_display_wait_for_param_blocks_before_popup', lambda *a: True)
    window.open_timer_editor(); d = window.timer_dialog; d.initial_read_timer.stop()
    for row in rows():
        d.update_from_live_register(SimpleNamespace(reg=M_CODE_REGISTERS[row['code']], raw_value=m_timer_word(row['code'],row['value'])))
    import foxair_phnix_control as gui
    monkeypatch.setattr(gui, 'ask_yes_no', lambda *a, **kw: False)
    d.fields[1]['heat_temp'].setValue(50.5); d.send_values()
    assert not d._pending and 1284 in d._dirty
    d.fields[1]['heat_temp'].setValue(41)
    assert not d._dirty and not d.send_btn.isEnabled()
    d.close()


def test_quick_and_register_conversion_preserve_m_engineering_units_and_binary():
    from cloud.cloud_write_helpers import cloud_write_value_from_user_input, cloud_write_value_from_register_value
    register = SimpleNamespace(dtype='TEMP1')
    assert cloud_write_value_from_register_value('M1 Heating Target',41,register,41) == '41'
    assert cloud_write_value_from_register_value('M1 Heating Target',410,register) == '41'
    assert cloud_write_value_from_user_input('M1_2 Enalbe','0000000011111111', register,
        lambda text: pytest.fail('M-code formats do not use an ambiguous local parser')) == '0000000011111111'
    assert cloud_write_value_from_user_input('M1 Heating Target','50,5',register,lambda text: 505) == '50.5'


def test_fresh_reload_resolves_ambiguous_write_without_losing_returned_draft(window, monkeypatch):
    d, req = opened(window, monkeypatch)
    monkeypatch.setattr(window, 'control_write_registers', lambda *a, **kw: None)
    d.fields[1]['heat_temp'].setValue(50.5); d.send_values()
    d.fields[1]['heat_temp'].setValue(41)
    assert d._pending and 1284 in d._dirty
    d.read_from_wp(); d.cloud_read_finished(req[-1].cycle_id, rows(), '')
    assert not d._pending and not d._dirty and not d.send_btn.isEnabled()
    d.close()
