"""Shared fixtures: Ugreen's 2018 release (fetched by tools/fetch-ugreen-2018) and images
built from it with a synthetic parameter-page tail, so no enclosure's private data is needed."""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
VENDOR = ROOT / "vendor" / "CM198-v167.001.000.004-20180730-meta.bin"
sys.path.insert(0, str(TOOLS))

needs_vendor = unittest.skipUnless(VENDOR.exists(), "run tools/fetch-ugreen-2018 first")


def find_s51():
    for name in (os.environ.get("S51"), "s51", "ucsim_51"):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def synthetic_backup(vendor: bytes) -> bytes:
    """A 512 KiB 'flash read': vendor code plus a fake tail carrying the four page tags."""
    tail = bytearray(b"\xff" * 0x40000)
    for off, tag in ((0x41000, b"IVP0"), (0x44000, b"IPP0"), (0x45000, b"IUP0"), (0x46000, b"WDq1")):
        tail[off - 0x40000:off - 0x40000 + 4] = tag
    tail[0x4400C - 0x40000:0x44010 - 0x40000] = bytes.fromhex("152d1561")   # USB ID in IPP0
    tail[0x44040 - 0x40000:0x44054 - 0x40000] = b"SYNTHSERIAL0042     "      # USB serial in IPP0
    tail[0x46008 - 0x40000] = 0                                              # UAS allowed
    return vendor + bytes(tail)


def run_tool(*args, **kw):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True, **kw)


def built(mode="trim") -> bytes:
    import jms561u_build
    return jms561u_build.build(VENDOR.read_bytes(), synthetic_backup(VENDOR.read_bytes()), mode)


def other_firmware(img: bytes, project: bytes = b"0565") -> bytes:
    """img with one code byte of each copy changed (an unknown firmware), the chip project ID in
    both headers set to project, and every CRC of both copies recomputed."""
    from jms561_crc_rows import pack_bank
    out = bytearray(img)
    for bank in (0x00000, 0x20000):
        out[bank + 0x1E30E] ^= 0xFF           # padding after the 2018 code: harmless, but new
        out[bank + 2:bank + 6] = project
    out = bytes(out)
    for bank in (0x00000, 0x20000):
        out = pack_bank(out, img, bank)
    return out
