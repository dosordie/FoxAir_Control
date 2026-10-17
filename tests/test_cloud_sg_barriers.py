"""SG01 barriers must depend on fresh state, including ambiguous write outcomes."""
import pytest

from test_configuration_cloud_writes import run_commands
from test_control_transport import command_api, CommandApi


PARAMETERS = (("SG02", "6"), ("SG03", "4.5"), ("SG08", "1"))


@pytest.mark.parametrize("activating", [True, False], ids=["activate", "disable"])
@pytest.mark.parametrize("outcome", [
    "success", "missing", "mismatch", "stale", "cached", "read_timeout",
    "write_timeout_unapplied", "write_timeout_partial", "write_timeout_confirmed",
    "api_error_unapplied", "api_error_partial", "api_error_confirmed",
])
def test_sg_barriers_never_run_following_write_without_complete_fresh_readback(
        command_api, monkeypatch, activating, outcome):
    original_init = CommandApi.__init__
    original_write = CommandApi.write_control_batch
    original_read = CommandApi.get_data_by_code
    initial = {"SG01": "0" if activating else "7", "SG02": "5", "SG03": "4", "SG08": "0"}
    first = PARAMETERS if activating else (("SG01", "0"),)
    following = (("SG01", "7"),) if activating else PARAMETERS

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.values.update(initial)

    def write(self, device, commands):
        response = original_write(self, device, commands)
        if tuple(commands) != first:
            return response
        if outcome.startswith(("write_timeout", "api_error")):
            # Partial takeover is ambiguous even for the single SG01 command:
            # without an applied value it must not authorize dependent writes.
            applied = len(commands) if outcome.endswith("confirmed") else 1 if (
                outcome.endswith("partial") and activating) else 0
            for code, _value in commands[applied:]:
                self.values[code] = initial[code]
            if outcome.startswith("write_timeout"):
                raise TimeoutError("Synthetic uncertain write response")
            return {"isReusltSuc": False, "error_code": "denied", "http_status": 200}
        return response

    def read(self, device, codes):
        response = original_read(self, device, codes)
        if codes != [code for code, _ in first]:
            return response
        if outcome == "read_timeout":
            raise TimeoutError("Synthetic readback timeout")
        row = response["objectResult"][-1]
        if outcome == "missing":
            response["objectResult"].pop()
        elif outcome == "mismatch":
            row["value"] = initial[row["code"]]
        elif outcome in ("stale", "cached"):
            row[outcome] = True
        return response

    monkeypatch.setattr(CommandApi, "__init__", init)
    monkeypatch.setattr(CommandApi, "write_control_batch", write)
    monkeypatch.setattr(CommandApi, "get_data_by_code", read)
    # Intentionally put the activation command first at the call site. The
    # existing central plan must still place it after the parameter barrier.
    commands = (("SG01", "7"), *PARAMETERS) if activating else (*PARAMETERS, ("SG01", "0"))
    results, errors = run_commands(commands)
    assert not errors
    api = CommandApi.created[0]
    confirmed = outcome in ("success", "write_timeout_confirmed", "api_error_confirmed")
    expected_calls = [("write", "device", first)]
    expected_calls += [("readback", "device", [code for code, _ in first])] * (1 if confirmed else 3)
    if confirmed:
        expected_calls += [("write", "device", following),
                           ("readback", "device", [code for code, _ in following])]
    # Exact call sequence excludes automatic write replay, rollback and an
    # activation/dependent write slipping through before complete readback.
    assert api.calls == expected_calls
    assert results[-1]["sequence_complete"] is confirmed
    if confirmed:
        assert set(results[-1]["confirmed_codes"]) == {code for code, _ in commands}
    elif activating:
        assert api.values["SG01"] == "0"
    else:
        assert {code: api.values[code] for code, _ in PARAMETERS} == {
            code: initial[code] for code, _ in PARAMETERS}
    if outcome in ("missing", "mismatch", "stale", "cached", "read_timeout"):
        assert all(api.values[code] == value for code, value in first)  # No rollback.
    if outcome in ("write_timeout_partial", "api_error_partial") and activating:
        assert results[-1]["confirmed_codes"] == ["SG02"]
        assert api.values["SG02"] == "6"  # Confirmed partial takeover is retained.
    if outcome.startswith(("write_timeout", "api_error")):
        assert results[0]["api_success"] is False
