#!/usr/bin/env python3
"""Stand-in for flashrom -p ch347_spi -c P25D40SH, modelling the rules jms561-clip relies on.

The chip is the file in $FAKE_CHIP (512 KiB). Like flashrom cli_classic.c, a -w/-r/-v
file argument is a whole-chip image: -w refuses a file of any other size before touching
the chip. --include rNN[:file] limits the operation to one layout region.
"""
import os, sys

SIZE = 0x80000
args = sys.argv[1:]
chip_path = os.environ["FAKE_CHIP"]
layout, include, op, path = None, None, None, None
i = 0
while i < len(args):
    a = args[i]
    if a in ("-p", "-c"): i += 2; continue
    if a == "-l": layout = args[i + 1]; i += 2; continue
    if a == "--include": include = args[i + 1]; i += 2; continue
    if a in ("-r", "-w", "-v"): op, path = a, args[i + 1]; i += 2; continue
    sys.exit(f"fake flashrom: unexpected argument {a}")

regions = {}
for line in open(layout):
    span, name = line.split()
    lo, hi = (int(x, 16) for x in span.split(":"))
    regions[name] = (lo, hi + 1)
name, _, region_file = include.partition(":")
lo, hi = regions[name]
chip = bytearray(open(chip_path, "rb").read())

if op == "-w":
    data = open(path, "rb").read()
    if len(data) != SIZE:
        sys.exit(f"Error: Image size ({len(data)} B) doesn't match the expected size ({SIZE} B)!")
    chip[lo:hi] = data[lo:hi]
    open(chip_path, "wb").write(chip)
elif op == "-r":
    buf = bytes(lo) + chip[lo:hi] + bytes(SIZE - hi)
    open(path, "wb").write(buf)
    if region_file:
        open(region_file, "wb").write(chip[lo:hi])
else:
    sys.exit(f"fake flashrom: unsupported op {op}")
