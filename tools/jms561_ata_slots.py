#!/usr/bin/env python3
"""List XRAM bytes that firmware code loads with ATA command opcodes.

A JMicron bridge builds ATA taskfiles in XRAM with `MOV DPTR,#slot; MOV A,#opcode; MOVX @DPTR,A`.
A slot that receives IDENTIFY (0xEC) is a taskfile command byte; every other opcode written to the
same slot is a command the firmware issues itself. On A-2018 this finds DSM/TRIM (0x06) at CPU 0xCCD9.

Usage: jms561_ata_slots.py <image> [--bank 0|1]   (512 KiB flash image; window2 = bank + 0x10000)
"""
import argparse
import sys

ATA_NAMES = {0x06: "DSM", 0x2F: "READ LOG EXT", 0x42: "READ VERIFY EXT", 0x25: "READ DMA EXT", 0x35: "WRITE DMA EXT", 0xB0: "SMART", 0xE0: "STANDBY IMM",
             0xE1: "IDLE IMM", 0xE4: "READ BUFFER", 0xE5: "CHECK POWER", 0xE7: "FLUSH CACHE",
             0xE8: "WRITE BUFFER", 0xEA: "FLUSH CACHE EXT", 0xEC: "IDENTIFY", 0xEF: "SET FEATURES"}


def window2(image: bytes, bank: int) -> bytes:
    base = bank * 0x20000 + 0x10000
    return image[base:base + 0x10000]


def command_slots(code: bytes) -> dict:
    """slot -> {opcode: [cpu addresses of the MOV DPTR]} for slots that receive 0xEC."""
    slots = {}
    for i in range(len(code) - 5):
        if code[i] == 0x90 and code[i + 3] == 0x74 and code[i + 5] == 0xF0:
            slot = (code[i + 1] << 8) | code[i + 2]
            slots.setdefault(slot, {}).setdefault(code[i + 4], []).append(i)
    return {s: ops for s, ops in slots.items() if 0xEC in ops}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image")
    ap.add_argument("--bank", type=int, choices=(0, 1), default=0)
    a = ap.parse_args(argv)
    for slot, ops in sorted(command_slots(window2(open(a.image, "rb").read(), a.bank)).items()):
        print(f"slot {slot:#06x}")
        for op, sites in sorted(ops.items()):
            print(f"  {op:#04x} {ATA_NAMES.get(op, '?'):16} at {' '.join(hex(s) for s in sites)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
