"""CRC-32 used by JMicron JMS56x firmware banks.

Polynomial 0x04C11DB7, bits of each byte fed LSB first, the four bytes of every DWORD
fed in reverse order, initial value 0xFFFFFFFF unless given, no final XOR. Recovered
from JMMassProd and checked against every bank of the 2018 and 2020 Ugreen releases.

That is the standard CRC-32 (zlib) over the DWORD-reversed data, with the register bit
order reflected, so zlib does the work.
"""
import zlib


def _reflect(v):
    return int(f"{v:032b}"[::-1], 2)


def crc(data, initial=0xffffffff):
    if len(data) % 4:
        raise ValueError('CRC data must contain complete DWORDs')
    swapped = bytearray(data)
    swapped[0::4], swapped[1::4], swapped[2::4], swapped[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
    return _reflect(zlib.crc32(swapped, _reflect(initial) ^ 0xffffffff) ^ 0xffffffff)
