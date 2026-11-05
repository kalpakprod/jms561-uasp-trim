"""The ATA slot scanner finds JMicron's own DSM/TRIM taskfile in the 2018 firmware."""
import unittest

from tests.common import TOOLS, VENDOR, needs_vendor, run_tool, synthetic_backup


@needs_vendor
class TestAtaSlots(unittest.TestCase):
    def test_2018_issues_dsm_from_the_identify_taskfile(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            img = Path(d, "img.bin")
            img.write_bytes(synthetic_backup(VENDOR.read_bytes()))
            out = run_tool(TOOLS / "jms561_ata_slots.py", img, "--bank", "0", check=True).stdout
        self.assertIn("slot 0x342e", out)
        self.assertRegex(out, r"0x06 DSM +at 0xccd9\n")
        self.assertRegex(out, r"0xec IDENTIFY +at 0xc7f4\n")


if __name__ == "__main__":
    unittest.main()
