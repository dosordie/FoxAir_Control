import unittest

from tools.phnix_ota.phnix_local_ota_controller import (
    EXPECTED_MD5,
    EXPECTED_SIZE,
    command_payload,
    crc16_x25,
    parse_ota_info,
)


class OtaInfoTests(unittest.TestCase):
    def make_info(self) -> bytearray:
        raw = bytearray(220)
        raw[28:34] = b"V1.2\0\0"
        raw[165:198] = EXPECTED_MD5.encode("ascii") + b"\0"
        raw[198:207] = b"82400644\0"
        raw[207:212] = b"0033\0"
        raw[212:216] = (168).to_bytes(4, "little")
        raw[216:220] = EXPECTED_SIZE.to_bytes(4, "little")
        raw[0:4] = crc16_x25(raw[4:220]).to_bytes(4, "little")
        return raw

    def test_parses_crc_and_fw33_metadata(self):
        info = parse_ota_info(bytes(self.make_info()))
        self.assertTrue(info.crc_ok)
        self.assertEqual(info.md5, EXPECTED_MD5)
        self.assertEqual(info.software_code, "82400644")
        self.assertEqual(info.software_version, "0033")
        self.assertEqual(info.offset, 168)
        self.assertEqual(info.length, EXPECTED_SIZE)

    def test_detects_corruption(self):
        raw = self.make_info()
        raw[100] ^= 0x01
        self.assertFalse(parse_ota_info(bytes(raw)).crc_ok)

    def test_0033_is_protocol_code_not_version_field(self):
        payload = command_payload("http://127.0.0.1:8081/FW3.3.bin")
        self.assertEqual(payload["code"], "0033")
        self.assertEqual(payload["param"]["softwareVer"], "V3.3")


if __name__ == "__main__":
    unittest.main()
