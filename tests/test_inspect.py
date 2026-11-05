"""Inspector: the verdict for each kind of flash read, the serial never printed, the builder's gate."""
import json
import tempfile
import unittest
from pathlib import Path

from tests.common import TOOLS, VENDOR, built, needs_vendor, other_firmware, run_tool, synthetic_backup
from jms561_inspect import inspect
import jms561u_build as b


@needs_vendor
class TestVerdict(unittest.TestCase):
    def setUp(self):
        self.vendor = VENDOR.read_bytes()
        self.backup = synthetic_backup(self.vendor)

    def test_cm198_read_is_ready(self):
        r = inspect(self.backup)
        self.assertEqual(r["verdict"], "ready")
        self.assertEqual(r["boots"], "copy 0")
        c0 = r["copies"][0]
        self.assertEqual((c0["known"], c0["version"], c0["uasp"]), ("ugreen-2018", "167.1.0.4", True))
        self.assertEqual(c0["trim_flag_cleared_at"], ["0x2527"])
        self.assertEqual(c0["trim_translation_at"], "0xccd9")
        self.assertEqual(r["pages"]["usb_id"], "152d:1561")
        self.assertFalse(r["pages"]["uas_disabled"])

    def test_trim_image_is_recognised(self):
        c0, c1 = inspect(built("trim"))["copies"]
        self.assertEqual(c0["known"], "this-trim")
        self.assertTrue(c0["trim"].startswith("on"))
        self.assertEqual(set(c0["trim_flag_reads"].values()), {"port"})
        self.assertEqual(c1["known"], "ugreen-2018")

    def test_stale_code_crc_moves_boot_to_copy_1(self):
        img = bytearray(self.backup)
        img[0x1E30E] ^= 0xFF
        r = inspect(bytes(img))
        self.assertFalse(r["copies"][0]["code_crc_ok"])
        self.assertEqual(r["boots"], "copy 1")

    def test_other_firmware_same_layout(self):
        self.assertEqual(inspect(other_firmware(self.backup))["verdict"], "same-layout")

    def test_jms561_family(self):
        self.assertEqual(inspect(other_firmware(self.backup, b"0561"))["verdict"], "other-family")

    def test_release_file(self):
        self.assertEqual(inspect(self.vendor)["verdict"], "release-file")

    def test_erased_pages(self):
        r = inspect(self.vendor + b"\xff" * 0x40000)
        self.assertEqual(r["verdict"], "no-pages")
        self.assertTrue(r["pages"]["blank"])

    def test_failed_read(self):
        self.assertEqual(inspect(b"\xff" * 0x80000)["verdict"], "unreadable")

    def test_wrong_size_refused(self):
        with self.assertRaises(SystemExit):
            inspect(b"\x00" * 1000)

    def test_report_hides_serial(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "read.bin")
            p.write_bytes(self.backup)
            for args in ((), ("--json",)):
                r = run_tool(TOOLS / "jms561_inspect.py", p, *args)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn("SYNTHSERIAL", r.stdout)
                self.assertIn("15 characters (hidden)", r.stdout)
            self.assertEqual(json.loads(r.stdout)["verdict"], "ready")


@needs_vendor
class TestBuilderGate(unittest.TestCase):
    def setUp(self):
        self.vendor = VENDOR.read_bytes()
        self.backup = synthetic_backup(self.vendor)

    def test_other_board_needs_the_flag(self):
        other = other_firmware(self.backup)
        with self.assertRaisesRegex(SystemExit, "other than Ugreen"):
            b.build(self.vendor, other, "trim")
        out = b.build(self.vendor, other, "trim", other_board=True)
        self.assertEqual(out[0x40000:], other[0x40000:])
        self.assertEqual(out[:0x40000], built("trim")[:0x40000])

    def test_jms561_family_refused_even_with_the_flag(self):
        with self.assertRaisesRegex(SystemExit, "not a JMS561U"):
            b.build(self.vendor, other_firmware(self.backup, b"0561"), "trim", other_board=True)


if __name__ == "__main__":
    unittest.main()
