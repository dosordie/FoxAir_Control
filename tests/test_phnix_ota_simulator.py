import os
import tempfile
import unittest
from pathlib import Path

from tools.phnix_ota import phnix_ota_simulator as simulator


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("PHNIX_OTA_SIM_HOME")
        os.environ["PHNIX_OTA_SIM_HOME"] = self.temp.name

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("PHNIX_OTA_SIM_HOME", None)
        else:
            os.environ["PHNIX_OTA_SIM_HOME"] = self.previous
        self.temp.cleanup()

    def test_reset_creates_idle_valid_state(self):
        simulator.reset_state("success")
        raw = simulator.root_path("/data/phnixIot_device_OTA_INFO").read_bytes()
        self.assertEqual(len(raw), 220)
        self.assertEqual(int.from_bytes(raw[:4], "little"), simulator.crc16_x25(raw[4:]))
        self.assertEqual(simulator.config()["scenario"], "success")

    def test_update_info_sets_expected_metadata(self):
        simulator.reset_state("success")
        simulator.update_info(32_000)
        raw = simulator.root_path("/data/phnixIot_device_OTA_INFO").read_bytes()
        self.assertEqual(raw[165:197].decode(), simulator.EXPECTED_MD5)
        self.assertEqual(int.from_bytes(raw[212:216], "little"), 32_000)


if __name__ == "__main__":
    unittest.main()
