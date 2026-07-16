from __future__ import annotations

import json

from core.udp_diagnostics import UdpDiagnosticSender


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.raise_on_send = False
        self.closed = False

    def sendto(self, data, target):
        if self.raise_on_send:
            raise OSError("boom")
        self.sent.append((data, target))

    def close(self):
        self.closed = True


class SocketFactory:
    def __init__(self, sock):
        self.sock = sock
        self.calls = 0

    def __call__(self, family, socktype):
        self.calls += 1
        return self.sock


def decode_packet(sock, idx=0):
    return json.loads(sock.sent[idx][0].decode("utf-8"))


def test_udp_disabled_does_not_call_sendto():
    sock = FakeSocket()
    sender = UdpDiagnosticSender({"enabled": False}, socket_factory=SocketFactory(sock))

    sender.send({"event": "x"})

    assert sock.sent == []


def test_register_change_enabled_sends_exactly_one_datagram_for_one_change():
    sock = FakeSocket()
    sender = UdpDiagnosticSender(
        {"enabled": True, "send_register_changes": True, "send_raw_bus": False},
        socket_factory=SocketFactory(sock),
    )

    sender.send_register_change(
        backend="display_modbus",
        reg=2137,
        old_raw=7,
        raw=8,
        value="0.8 kW",
        name="Elektrische Leistung",
    )
    # Unveränderter Wert wird von der App nicht erneut an die Hilfsfunktion übergeben.

    assert len(sock.sent) == 1
    packet = decode_packet(sock)
    assert packet["event"] == "register_change"
    assert packet["backend"] == "display_modbus"
    assert packet["reg"] == 2137
    assert packet["old_raw"] == 7
    assert packet["raw"] == 8
    assert packet["hex"] == "0x0008"
    assert packet["value"] == "0.8 kW"
    assert packet["name"] == "Elektrische Leistung"


def test_raw_output_disabled_sends_no_datagrams():
    sock = FakeSocket()
    sender = UdpDiagnosticSender(
        {"enabled": True, "send_raw_bus": False},
        socket_factory=SocketFactory(sock),
    )

    sender.send_raw_bus(backend="display_modbus", direction="rx", data=b"\x01\x03")

    assert sock.sent == []


def test_raw_output_enabled_rx_and_tx_fields():
    sock = FakeSocket()
    sender = UdpDiagnosticSender(
        {"enabled": True, "send_raw_bus": True, "send_register_changes": False},
        socket_factory=SocketFactory(sock),
    )

    sender.send_raw_bus(backend="display_modbus", direction="rx", data=b"\x01\x03\x04")
    sender.send_raw_bus(backend="display_modbus", direction="tx", data=b"\x05\x06")

    assert len(sock.sent) == 2
    rx = decode_packet(sock, 0)
    tx = decode_packet(sock, 1)
    assert rx["event"] == "raw_bus"
    assert rx["backend"] == "display_modbus"
    assert rx["direction"] == "rx"
    assert rx["hex"] == "01 03 04"
    assert "ts" in rx
    assert tx["event"] == "raw_bus"
    assert tx["direction"] == "tx"
    assert tx["hex"] == "05 06"


def test_sendto_error_is_swallowed():
    sock = FakeSocket()
    sock.raise_on_send = True
    sender = UdpDiagnosticSender({"enabled": True}, socket_factory=SocketFactory(sock))

    sender.send({"event": "x"})

    assert sock.sent == []
