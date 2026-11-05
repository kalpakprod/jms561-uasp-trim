"""Builder: published code hashes, parameter pages kept, bad inputs refused."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tests.common import TOOLS, VENDOR, built, needs_vendor, run_tool, synthetic_backup
import jms561u_build as b


@needs_vendor
class TestBuild(unittest.TestCase):
    def test_trim_image_code_matches_published_hash_and_keeps_pages(self):
        out = built("trim")
        self.assertEqual(hashlib.sha256(out[:0x40000]).hexdigest(), b.CODE_SHA["trim"])
        self.assertEqual(out[0x40000:], synthetic_backup(VENDOR.read_bytes())[0x40000:])
        self.assertEqual(out[0x20000:0x40000], VENDOR.read_bytes()[0x20000:])  # copy 1 untouched
        self.assertEqual(out[0x1C255], ord("T"))                                 # "JMS56T Series"

    def test_uas_only_is_vendor_code(self):
        self.assertEqual(built("uas")[:0x40000], VENDOR.read_bytes())

    def test_wrong_vendor_file_refused(self):
        v = bytearray(VENDOR.read_bytes())
        v[0x100] ^= 1
        with self.assertRaises(SystemExit):
            b.build(bytes(v), synthetic_backup(VENDOR.read_bytes()), "trim")

    def test_backup_without_parameter_pages_refused(self):
        erased = VENDOR.read_bytes() + b"\xff" * 0x40000
        with self.assertRaisesRegex(SystemExit, "parameter pages"):
            b.build(VENDOR.read_bytes(), erased, "trim")

    def test_short_backup_refused(self):
        with self.assertRaisesRegex(SystemExit, "512 KiB"):
            b.build(VENDOR.read_bytes(), VENDOR.read_bytes(), "trim")

    def test_cli_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            bk, out = Path(d, "backup.bin"), Path(d, "out.bin")
            bk.write_bytes(synthetic_backup(VENDOR.read_bytes()))
            out.write_bytes(b"keep")
            r = run_tool(TOOLS / "jms561u_build.py", "--backup", bk, "--out", out)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(out.read_bytes(), b"keep")
            out.unlink()
            r = run_tool(TOOLS / "jms561u_build.py", "--backup", bk, "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("OK      " + hashlib.sha256(out.read_bytes()).hexdigest(), r.stdout)


if __name__ == "__main__":
    unittest.main()
