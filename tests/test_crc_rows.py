"""CRC gate: vendor banks pass, a stale code CRC (the trap that hid three early attempts) is caught."""
import tempfile
import unittest
from pathlib import Path

from tests.common import TOOLS, VENDOR, needs_vendor, run_tool, synthetic_backup


@needs_vendor
class TestCrcRows(unittest.TestCase):
    def check(self, data):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "img.bin")
            p.write_bytes(data)
            return run_tool(TOOLS / "jms561_crc_rows.py", "check", p).stdout

    def test_vendor_release_passes(self):
        self.assertIn("RESULT OK", self.check(VENDOR.read_bytes()))

    def test_patched_code_with_old_code_crc_is_caught(self):
        img = bytearray(synthetic_backup(VENDOR.read_bytes()))
        img[0x1C255] = ord("T")  # change one code byte, leave every CRC as it was
        out = self.check(bytes(img))
        self.assertIn("RESULT BAD bank B+0x00000 code CRC +0x1FFF8", out)


if __name__ == "__main__":
    unittest.main()
