#!/usr/bin/env python3
"""Apply byte rows to a 512 KiB JMS561U flash image; every before-byte must match.

  jms561_apply.py BASE TABLE OUT

TABLE: one row per line, '<file offset hex> <before hex> <after hex> [reason...]',
'#' starts a comment. Rows must not overlap and must not touch CRC words; recompute
those afterwards with: jms561_crc_rows.py pack OUT --ref BASE --out FINAL --bank 0|1|both
"""
import hashlib
import sys

CRC_WORDS = [(b + o, b + o + 4) for b in (0x00000, 0x20000)
             for o in (0x208, 0x3FC, 0x7FC, 0xFFFC, 0x1FFF8, 0x1FFFC)]


def rows(text):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split('#', 1)[0].split()
        if not line:
            continue
        off, before, after = int(line[0], 16), bytes.fromhex(line[1]), bytes.fromhex(line[2])
        if len(before) != len(after):
            sys.exit(f'row {n}: before and after differ in length')
        out.append((off, before, after))
    return sorted(out)


def apply(base, table):
    img = bytearray(base)
    if len(img) != 0x80000:
        sys.exit('base is not 512 KiB')
    end = 0
    for off, before, after in table:
        if off < end:
            sys.exit(f'row at {off:#x} overlaps the previous row')
        if any(off < hi and lo < off + len(before) for lo, hi in CRC_WORDS):
            sys.exit(f'row at {off:#x} touches a CRC word')
        if img[off:off + len(before)] != before:
            sys.exit(f'row at {off:#x}: image has {img[off:off + len(before)].hex()}, table says {before.hex()}')
        img[off:off + len(after)] = after
        end = off + len(before)
    return bytes(img)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    base = open(sys.argv[1], 'rb').read()
    out = apply(base, rows(open(sys.argv[2]).read()))
    with open(sys.argv[3], 'xb') as f:
        f.write(out)
    print(hashlib.sha256(out).hexdigest(), sys.argv[3])
