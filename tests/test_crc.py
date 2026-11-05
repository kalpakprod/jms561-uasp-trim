"""The fast JMicron CRC matches a bit-by-bit implementation of the algorithm as recovered."""
import unittest

from tests.common import TOOLS  # noqa: F401  (puts tools/ on sys.path)
from jms561_crc import crc


def bitwise(data, initial=0xffffffff):
    """The algorithm as recovered from JMMassProd, one bit at a time."""
    state = initial
    for at in range(0, len(data), 4):
        for byte in data[at:at + 4][::-1]:
            for bit in range(8):
                feedback = (state >> 31) ^ ((byte >> bit) & 1)
                state = (state << 1) & 0xffffffff
                if feedback:
                    state ^= 0x04c11db7
    return state


class TestCrc(unittest.TestCase):
    def test_matches_bitwise_algorithm(self):
        for data in (bytes(4), bytes(range(256)) * 16, b"EXROMEND" * 3):
            for initial in (0xffffffff, 0, 0x12345678):
                self.assertEqual(crc(data, initial), bitwise(data, initial))

    def test_rejects_partial_dword(self):
        with self.assertRaises(ValueError):
            crc(b"abc")


if __name__ == "__main__":
    unittest.main()
