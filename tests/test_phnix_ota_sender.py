import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

from devtools.phnix_ota_sender import (
    Firmware,
    FrameReader,
    TransferSpec,
    build_c350,
    build_c357,
    build_c371_ack,
    build_c5a8,
    compare_capture,
    decode_c371,
    decode_fc10,
    fc10_frame,
    has_valid_crc,
    JsonlLog,
    normalize_version,
    run_live_transfer,
    SerialTransport,
    simulate,
    with_crc,
)


class FragmentedTransport:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read(self, _size, _timeout):
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, _data):
        raise AssertionError("reader test must not write")

    def close(self):
        pass


class SimulatedBoardTransport:
    def __init__(self, spec):
        self.spec = spec
        self.pending = bytearray()
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        register, payload = decode_fc10(data)
        if register in (0xC350, 0xC357):
            quantity = int.from_bytes(data[4:6], "big")
            self.pending.extend(
                with_crc(b"\x63\x10" + register.to_bytes(2, "big") + quantity.to_bytes(2, "big"))
            )
            status = 1 if register == 0xC350 else 2
            status_payload = self.spec.ssid.to_bytes(2, "big") + status.to_bytes(2, "big")
            self.pending.extend(fc10_frame(0xC36E, status_payload))
        elif register == 0xC5A8:
            block = int.from_bytes(payload[4:6], "big")
            self.pending.extend(build_c371_ack(self.spec, block))
        else:
            raise AssertionError(f"unexpected write 0x{register:04X}")

    def read(self, size, _timeout):
        chunk = bytes(self.pending[:size])
        del self.pending[:size]
        return chunk

    def close(self):
        pass


class PhnixOtaSenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "firmware.bin"
        self.data = bytes(range(256)) + b"fixture-data" * 19
        self.path.write_bytes(self.data)
        self.firmware = Firmware.load(self.path)
        self.spec = TransferSpec(self.firmware, "82400644", "V3.4", 0x0063)

    def tearDown(self):
        self.temp.cleanup()

    def test_version_conversion(self):
        self.assertEqual(normalize_version("V3.4"), "0034")
        self.assertEqual(normalize_version("0034"), "0034")

    def test_v33_known_c350_frame(self):
        spec = TransferSpec(self.firmware, "82400644", "V3.3", 0x0063)
        self.assertEqual(
            build_c350(spec).hex(" ").upper(),
            "63 10 C3 50 00 07 0E 00 63 38 32 34 30 30 36 34 34 30 30 33 33 59 4D",
        )

    def test_c357_contains_size_and_lowercase_md5(self):
        frame = build_c357(self.spec)
        register, payload = decode_fc10(frame)
        self.assertEqual(register, 0xC357)
        self.assertEqual(int.from_bytes(payload[2:6], "big"), len(self.data))
        self.assertEqual(payload[6:], hashlib.md5(self.data).hexdigest().encode("ascii"))

    def test_blocks_reconstruct_and_final_padding_is_ff(self):
        reconstructed = bytearray()
        for block in range(1, self.spec.total_blocks + 1):
            frame = build_c5a8(self.spec, block)
            self.assertTrue(has_valid_crc(frame))
            register, payload = decode_fc10(frame)
            self.assertEqual(register, 0xC5A8)
            self.assertEqual(int.from_bytes(payload[4:6], "big"), block)
            remaining = len(self.data) - len(reconstructed)
            real = min(self.spec.block_size, remaining)
            reconstructed.extend(payload[6 : 6 + real])
            if block == self.spec.total_blocks:
                self.assertEqual(payload[6 + real :], b"\xFF" * (self.spec.block_size - real))
        self.assertEqual(bytes(reconstructed), self.data)

    def test_ack_b_two_only_for_final_block(self):
        for block in range(1, self.spec.total_blocks + 1):
            _, payload = decode_fc10(build_c371_ack(self.spec, block))
            ssid, ack_a, ack_b, ack_block = decode_c371(payload)
            self.assertEqual((ssid, ack_a, ack_block), (0x0063, 1, block))
            self.assertEqual(ack_b, 2 if block == self.spec.total_blocks else 1)

    def test_internal_simulation(self):
        result = simulate(self.spec)
        self.assertTrue(result["verified"])
        self.assertEqual(result["sha256"], hashlib.sha256(self.data).hexdigest().upper())
        self.assertEqual(result["finalAckB"], 2)

    def test_frame_reader_handles_fragmented_extended_frame(self):
        frame = build_c371_ack(self.spec, 1)
        reader = FrameReader(FragmentedTransport([b"noise", frame[:4], frame[4:11], frame[11:]]))
        self.assertEqual(reader.read_frame(1.0), frame)

    def test_capture_comparison_allows_unrelated_bytes_between_frames(self):
        capture = Path(self.temp.name) / "capture.bin"
        expected = [build_c350(self.spec), build_c357(self.spec)]
        expected.extend(build_c5a8(self.spec, block) for block in range(1, self.spec.total_blocks + 1))
        capture.write_bytes(b"startup-noise" + b"other".join(expected) + b"tail")
        result = compare_capture(self.spec, capture)
        self.assertTrue(result["byteExactAndInOrder"])
        self.assertEqual(result["matchedFrames"], self.spec.total_blocks + 2)

    def test_complete_transport_state_machine_stops_without_c37b(self):
        board = SimulatedBoardTransport(self.spec)
        log = JsonlLog(None)
        run_live_transfer(self.spec, board, timeout=1.0, log=log)
        registers = [decode_fc10(frame)[0] for frame in board.writes]
        self.assertEqual(registers[:2], [0xC350, 0xC357])
        self.assertEqual(registers.count(0xC5A8), self.spec.total_blocks)
        self.assertNotIn(0xC37B, registers)

    def test_default_live_boundary_can_stop_before_first_firmware_block(self):
        board = SimulatedBoardTransport(self.spec)
        run_live_transfer(self.spec, board, timeout=1.0, log=JsonlLog(None), stop_after="handshake")
        registers = [decode_fc10(frame)[0] for frame in board.writes]
        self.assertEqual(registers, [0xC350, 0xC357])

    def test_usb_rs485_transport_uses_9600_8n1_and_flushes(self):
        instances = []

        class FakeSerialPort:
            def __init__(self, **settings):
                self.settings = settings
                self.timeout = settings["timeout"]
                self.flushed = False
                self.closed = False
                self.written = bytearray()
                instances.append(self)

            def write(self, data):
                self.written.extend(data)

            def flush(self):
                self.flushed = True

            def read(self, size):
                return b"reply"[:size]

            def close(self):
                self.closed = True

        fake_serial = types.SimpleNamespace(
            Serial=FakeSerialPort,
            EIGHTBITS=8,
            PARITY_NONE="N",
            STOPBITS_ONE=1,
        )
        original = sys.modules.get("serial")
        sys.modules["serial"] = fake_serial
        try:
            transport = SerialTransport("COM5", 9600, 2.0)
            transport.write(b"test")
            self.assertEqual(transport.read(5, 1.0), b"reply")
            transport.close()
        finally:
            if original is None:
                del sys.modules["serial"]
            else:
                sys.modules["serial"] = original
        port = instances[0]
        self.assertEqual(
            (port.settings["port"], port.settings["baudrate"], port.settings["bytesize"], port.settings["parity"], port.settings["stopbits"]),
            ("COM5", 9600, 8, "N", 1),
        )
        self.assertEqual(bytes(port.written), b"test")
        self.assertTrue(port.flushed)
        self.assertTrue(port.closed)


if __name__ == "__main__":
    unittest.main()
