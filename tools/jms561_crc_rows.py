#!/usr/bin/env python3
"""Check and recompute every CRC field of a JMicron JMS561U firmware bank.

Flash layout of one 128 KiB bank, base B = 0x00000 (copy 0) or 0x20000 (copy 1):

  B+0x000..0x3FF   header             CRC at B+0x3FC = crc(B+0x000..B+0x3FB)
  B+0x400..0x7FF   config             CRC at B+0x7FC = crc(B+0x400..B+0x7FB)
  B+0x800..0xFFF   unused (zeros in every release image)
  B+0x1000..0xFFFB window1            CRC at B+0xFFFC = crc(B+0x1000..B+0xFFFB)
  B+0x10000..      window2 = 8051 code, CPU address = offset - B - 0x10000
  B+0x1FFF0        "EXROMEND"
  B+0x1FFF8        code CRC           crc(B+0x10000..B+0x1FFF7)
  B+0x1FFFC        footer             crc(B+0x400..B+0x1FFFB, init 0) XOR K
  B+0x208          copy of the footer (stamped by the host tool; zeros in release files)

All CRC words are stored big-endian. K is a per-release constant (2018 167.1.0.4:
0x79849691, 2020 167.2.0.21: 0x1BCC43A3); pack_bank() derives it from the pristine
reference image instead of hardcoding it.

Packing order matters: the code CRC lies inside the range the footer covers, so it is
recomputed first. A bank whose code CRC is stale is most likely skipped by the boot
loader (see docs/firmware-layout.md, "Boot"), which is how three early TRIM attempts of
this project silently ran unpatched code.

Usage:
  jms561_crc_rows.py check IMAGE...                     verify every field of every bank
  jms561_crc_rows.py pack PATCHED --ref REF --out OUT [--bank 0|1|both]
                                                        recompute the fields, write OUT
  jms561_crc_rows.py k IMAGE...                         print K per bank
"""
import argparse
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jms561_crc import crc  # noqa: E402

BANKS = (0x00000, 0x20000)
EXROMEND = b'EXROMEND'


def be(v):
    return int(v).to_bytes(4, 'big')


def u32(b):
    return int.from_bytes(b, 'big')


def bank_k(img, B):
    """Footer constant K of one bank: footer XOR crc(config..window2, 0)."""
    return u32(img[B + 0x1FFFC:B + 0x20000]) ^ crc(img[B + 0x400:B + 0x1FFFC], 0)


def code_crc(img, B):
    return crc(img[B + 0x10000:B + 0x1FFF8])


def check_bank(img, B, verbose=True):
    bad = []
    if img[B + 0x1FFF0:B + 0x1FFF8] != EXROMEND:
        if verbose:
            print('  bank B+0x%05X: no EXROMEND at +0x1FFF0 (%s), skipped'
                  % (B, img[B + 0x1FFF0:B + 0x1FFF8].hex()))
        return bad
    k = bank_k(img, B)
    want = [('code CRC +0x1FFF8', 0x1FFF8, be(code_crc(img, B)), 'crc(B+0x10000..B+0x1FFF7) BE'),
            ('footer +0x1FFFC', 0x1FFFC, be(crc(img[B + 0x400:B + 0x1FFFC], 0) ^ k),
             'crc(B+0x400..B+0x1FFFB,0) XOR K, K=%08x' % k),
            ('footer copy +0x208', 0x208, img[B + 0x1FFFC:B + 0x20000], 'host stamp, must equal footer'),
            ('header CRC +0x3FC', 0x3FC, be(crc(img[B:B + 0x3FC])), 'crc(B+0x000..B+0x3FB) BE'),
            ('config CRC +0x7FC', 0x7FC, be(crc(img[B + 0x400:B + 0x7FC])), 'crc(B+0x400..B+0x7FB) BE'),
            ('window1 CRC +0xFFFC', 0xFFFC, be(crc(img[B + 0x1000:B + 0xFFFC])), 'crc(B+0x1000..B+0xFFFB) BE')]
    stamped = img[B + 0x200:B + 0x204] == be(0x5ac369e1)
    for name, off, calc, note in want:
        stored = img[B + off:B + off + 4]
        ok = stored == calc
        if not stamped and name.startswith(('footer copy', 'header CRC')):
            ok = None  # release format: jmm adds these two host stamps later
            note += ' (release format, host stamp absent)'
        if ok is False:
            bad.append((B, name, stored.hex(), calc.hex()))
        if verbose:
            print('  bank B+0x%05X %s %-22s +0x%05X stored=%s calc=%s  %s'
                  % (B, {True: 'OK  ', False: 'BAD ', None: '----'}[ok], name.split(' ')[0] + ' ' + name.split(' ')[-1],
                     off, stored.hex(), calc.hex(), note))
    return bad


def pack_bank(img, ref, B, keep_code_crc=False):
    """Return img with the four rows of bank B recomputed. ref supplies K.

    keep_code_crc leaves B+0x1FFF8 stale on purpose; only a boot-rule experiment wants that.
    """
    k0, k1 = bank_k(ref, 0x00000), bank_k(ref, 0x20000)
    if len(ref) >= 0x40000 and k0 != k1:
        raise SystemExit('reference banks disagree on K: %08x vs %08x' % (k0, k1))
    out = bytearray(img)
    if not keep_code_crc:
        out[B + 0x1FFF8:B + 0x1FFFC] = be(code_crc(out, B))        # step 2
    out[B + 0x1FFFC:B + 0x20000] = be(crc(bytes(out[B + 0x400:B + 0x1FFFC]), 0) ^ k0)  # step 3
    if ref[B + 0x200:B + 0x204] == be(0x5ac369e1):                # step 4, host-stamped images only
        out[B + 0x208:B + 0x20C] = out[B + 0x1FFFC:B + 0x20000]
    if ref[B + 0x3FC:B + 0x400] != bytes(4):                       # step 5, host-stamped images only
        out[B + 0x3FC:B + 0x400] = be(crc(bytes(out[B:B + 0x3FC])))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('check', 'pack', 'k'))
    ap.add_argument('image', nargs='+')
    ap.add_argument('--ref', help='pristine image of the same release (pack)')
    ap.add_argument('--out', help='where to write the packed image')
    ap.add_argument('--bank', choices=('0', '1', 'both'), default='both')
    ap.add_argument('--keep-code-crc', action='store_true',
                    help='pack: leave B+0x1FFF8 stale (boot-rule experiment only)')
    a = ap.parse_args()

    rc = 0
    if a.mode == 'k':
        for p in a.image:
            d = open(p, 'rb').read()
            for B in BANKS:
                if B + 0x20000 <= len(d) and d[B + 0x1FFF0:B + 0x1FFF8] == EXROMEND:
                    print('%s bank%d K=%08x' % (p, B // 0x20000, bank_k(d, B)))
        return 0

    if a.mode == 'check':
        for p in a.image:
            d = open(p, 'rb').read()
            print('== %s (%d bytes)' % (p, len(d)))
            bad = []
            for B in BANKS:
                if B + 0x20000 <= len(d):
                    bad += check_bank(d, B)
            for B, name, s, c in bad:
                print('  RESULT BAD bank B+0x%05X %s stored=%s calc=%s' % (B, name, s, c))
            print('  RESULT %s' % ('OK' if not bad else 'BAD (%d)' % len(bad)))
            rc |= 1 if bad else 0
        return rc

    # pack
    if not a.ref or not a.out:
        raise SystemExit('pack needs --ref and --out')
    img = open(a.image[0], 'rb').read()
    ref = open(a.ref, 'rb').read()
    sel = {'0': (0x00000,), '1': (0x20000,), 'both': BANKS}[a.bank]
    out = img
    for B in sel:
        out = pack_bank(out, ref, B, a.keep_code_crc)
    open(a.out, 'wb').write(out)
    print('packed %s -> %s banks=%s' % (a.image[0], a.out, [hex(b) for b in sel]))
    for B in sel:
        print('  bank B+0x%05X' % B)
        check_bank(out, B)
    body_diff = [i for i in range(len(img)) if img[i] != out[i]]
    print('  changed offsets: %s' % [hex(i) for i in body_diff])
    return 0


if __name__ == '__main__':
    sys.exit(main())
