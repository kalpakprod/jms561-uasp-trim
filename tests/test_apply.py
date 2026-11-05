"""Row applier: wrong before-bytes, overlaps and CRC words are refused."""
import unittest

from tests.common import VENDOR, needs_vendor, synthetic_backup
import jms561_apply as ap


@needs_vendor
class TestApply(unittest.TestCase):
    def setUp(self):
        self.base = synthetic_backup(VENDOR.read_bytes())

    def test_applies_matching_row(self):
        out = ap.apply(self.base, ap.rows("1c255 78 54  # marker\n"))
        self.assertEqual(out[0x1C255], 0x54)
        self.assertEqual(out[:0x1C255], self.base[:0x1C255])

    def test_wrong_before_byte_refused(self):
        with self.assertRaises(SystemExit):
            ap.apply(self.base, ap.rows("1c255 00 54\n"))

    def test_crc_word_refused(self):
        word = self.base[0x1FFF8:0x1FFFC].hex()
        with self.assertRaises(SystemExit):
            ap.apply(self.base, ap.rows(f"1fff8 {word} 00000000\n"))

    def test_overlap_refused(self):
        with self.assertRaises(SystemExit):
            ap.apply(self.base, ap.rows("1c255 78 54\n1c255 78 54\n"))


if __name__ == "__main__":
    unittest.main()
