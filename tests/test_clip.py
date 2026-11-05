"""tools/jms561-clip against a fake flashrom that enforces flashrom's whole-chip file rule."""
import hashlib
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest

from tests.common import ROOT

CLIP = ROOT / "tools" / "jms561-clip"
FAKE = ROOT / "tests" / "fixtures" / "fake_flashrom.py"


class ClipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.old = bytes(range(256)) * 2048           # what the chip holds now
        self.new = bytes(range(255, -1, -1)) * 2048   # the image to write
        self.chip = self.tmp / "chip.bin"
        self.chip.write_bytes(self.old)
        self.image = self.tmp / "image.bin"
        self.image.write_bytes(self.new)
        self.backups = self.tmp / "backups"

    def tearDown(self):
        for p in self.tmp.rglob("*"):
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
        shutil.rmtree(self.tmp)

    def run_clip(self, *args):
        env = dict(os.environ, FLASHROM=str(FAKE), FAKE_CHIP=str(self.chip), JMS561_BACKUPS=str(self.backups))
        return subprocess.run([str(CLIP), *args], env=env, capture_output=True, text=True)

    def test_write_puts_image_on_chip_and_keeps_read_only_backup(self):
        want = hashlib.sha256(self.new).hexdigest()
        r = self.run_clip("write", str(self.image), want)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"VERIFIED {want}", r.stdout)
        self.assertEqual(self.chip.read_bytes(), self.new)
        before = next(self.backups.glob("clip-*-write/before/image.bin"))
        self.assertEqual(before.read_bytes(), self.old)
        self.assertFalse(os.access(before, os.W_OK))

    def test_write_refuses_wrong_sha_without_touching_chip(self):
        r = self.run_clip("write", str(self.image), "0" * 64)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.chip.read_bytes(), self.old)

    def test_read_reports_chip_sha(self):
        r = self.run_clip("read", "state")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("READ " + hashlib.sha256(self.old).hexdigest(), r.stdout)


if __name__ == "__main__":
    unittest.main()
