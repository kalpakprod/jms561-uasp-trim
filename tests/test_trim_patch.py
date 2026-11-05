"""The TRIM patch: its stubs behave in an 8051 simulator (uCsim), the UNMAP guard refuses what it
must, the hook disassembles as intended, and Ghidra shows the vendor's own DSM builder."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.common import ROOT, built, find_s51, needs_vendor

S51 = find_s51()
if os.environ.get("REQUIRE_S51") and not S51:
    raise RuntimeError("REQUIRE_S51 is set but no s51 found (tools/setup-ucsim)")
HARNESS = 0xF000  # zero padding in window2; LCALL <stub>; SJMP $


def ihex(data: bytes) -> str:
    out = []
    for a in range(0, len(data), 16):
        chunk = data[a:a + 16]
        if any(chunk):
            rec = bytes([len(chunk), a >> 8, a & 0xFF, 0]) + chunk
            out.append(":" + rec.hex().upper() + "%02X" % (-sum(rec) & 0xFF))
    return "\n".join(out + [":00000001FF"]) + "\n"


def simulate(stub: int, setup: list[str], dumps: list[str]) -> dict:
    """Call one stub of the TRIM image's copy 0 from a harness and return {address: byte} for the dumps."""
    code = bytearray(built("trim")[0x10000:0x20000])
    code[HARNESS:HARNESS + 5] = bytes([0x12, stub >> 8, stub & 0xFF, 0x80, 0xFE])
    with tempfile.TemporaryDirectory() as d:
        hexf = Path(d, "w.hex")
        hexf.write_text(ihex(bytes(code)))
        cmds = setup + ["set mem sfr 0x81 0x6f", f"pc {HARNESS:#x}", f"break {HARNESS + 3:#x}", "run"]
        cmds += [f"dump {kind} {a} {a}" for kind, a in (x.split() for x in dumps)] + ["quit"]
        out = subprocess.run([S51, "-t", "8052", "-X", "24M", str(hexf)], input="\n".join(cmds) + "\n",
                             capture_output=True, text=True, timeout=30).stdout
    if f"Stop at {HARNESS + 3:#08x}" not in out:
        raise AssertionError("stub did not return to the harness:\n" + out)
    out = out.split(f"Stop at {HARNESS + 3:#08x}", 1)[1]  # "set mem" echoes values too; read after the stop
    got = {}
    for kind, a in (x.split() for x in dumps):
        # plain bytes: "0x3faa   01 ."; named SFRs: "0xe0 ACC:   0b00000000 0x00 ..."
        m = re.search(rf"^{a}(?:\s+\w+:\s+0b[01]+\s+0x([0-9a-f]{{2}})|\s+([0-9a-f]{{2}})\b)", out, re.M)
        got[f"{kind} {a}"] = int(m.group(1) or m.group(2), 16)
    return got


ACCEPT, REJECT = 0x2DAD, 0x2CAC  # UNMAP stage 2 exits: schedule the descriptor parse / CHECK CONDITION


def unmap_exit(image: bytes, lba: int, count: int) -> int:
    """Run UNMAP stage 2 (0x2C6A) of copy 0 on a one-descriptor parameter list; return the exit taken."""
    code = image[0x10000:0x20000]
    plist = (22).to_bytes(2, "big") + (16).to_bytes(2, "big") + bytes(4)
    plist += lba.to_bytes(8, "big") + count.to_bytes(4, "big") + bytes(4)
    with tempfile.TemporaryDirectory() as d:
        hexf = Path(d, "w.hex")
        hexf.write_text(ihex(code))
        cmds = ["set mem sfr 0x81 0x6f", "set mem sfr 0xd0 0",
                "set mem xram 0x3a00 " + " ".join(f"{b:#04x}" for b in plist),
                "pc 0x2c6a", f"break {ACCEPT:#x}", f"break {REJECT:#x}", "run", "quit"]
        out = subprocess.run([S51, "-t", "8052", "-X", "24M", str(hexf)], input="\n".join(cmds) + "\n",
                             capture_output=True, text=True, timeout=30).stdout
    m = re.search(r"Stop at (0x[0-9a-f]+): \(\d+\) Breakpoint", out)
    if not m:
        raise AssertionError("stage 2 hit no exit:\n" + out)
    return int(m.group(1), 16)


@needs_vendor
@unittest.skipUnless(S51, "uCsim (s51) not installed")
class TestTrimStubs(unittest.TestCase):
    def identify(self, word169_lo):
        return simulate(0xE310, [f"set mem xram 0x3752 {word169_lo:#04x}", "set mem xram 0x3faa 0x5a",
                                 "set mem sfr 0x82 0xaa", "set mem sfr 0x83 0x3f"],
                        ["xram 0x3faa", "sfr 0x82", "sfr 0x83", "sfr 0x81"])

    def test_identify_stub_copies_word169_bit0_and_restores_dptr(self):
        for lo, flag in ((0x01, 1), (0x03, 1), (0x00, 0), (0xFE, 0)):
            got = self.identify(lo)
            self.assertEqual(got["xram 0x3faa"], flag, lo)
            self.assertEqual((got["sfr 0x83"], got["sfr 0x82"]), (0x37, 0xB3))  # MOV DPTR,#0x37B3 re-created
            self.assertEqual(got["sfr 0x81"], 0x6F)                            # stack balanced

    def rc16(self, flag):
        return simulate(0xE323, ["set mem iram 0x43 0x01", f"set mem xram 0x3faa {flag:#04x}",
                                 "set mem xram 0x3a0b 0x77", "set mem xram 0x3a0e 0x00"],
                        ["xram 0x3a0b", "xram 0x3a0e", "sfr 0xe0", "sfr 0x81"])

    def test_rc16_stub_sets_lbpme_only_for_a_trim_port(self):
        on, off = self.rc16(1), self.rc16(0)
        self.assertEqual((on["xram 0x3a0b"], on["xram 0x3a0e"], on["sfr 0xe0"]), (0, 0x80, 0))
        self.assertEqual((off["xram 0x3a0b"], off["xram 0x3a0e"], off["sfr 0xe0"]), (0, 0x00, 0))
        self.assertEqual(on["sfr 0x81"], 0x6F)


@needs_vendor
@unittest.skipUnless(S51, "uCsim (s51) not installed")
class TestUnmapDescriptorCheck(unittest.TestCase):
    """A high LBA must not alias a low one; counts above the advertised VPD limit are refused."""

    def test_vendor_code_accepts_the_aliasing_lba(self):
        self.assertEqual(unmap_exit(built("uas"), 0x0001_0000_0000_1000, 8), ACCEPT)

    def test_patch_accepts_valid_descriptors(self):
        for lba, count in ((0x1000, 8), (0x6F_C81A_B000, 1), (0xFFFF_FFFF_FFFF, 0xFFC0), (0x1000, 0xFF00),
                           (0x1000, 0xFEFF), (0x1000, 0)):
            self.assertEqual(unmap_exit(built("trim"), lba, count), ACCEPT, (hex(lba), hex(count)))

    def test_patch_rejects_high_lba_and_oversized_count(self):
        for lba, count in ((0x0001_0000_0000_1000, 8), (0x0100_0000_0000_1000, 8), (0x1000, 0xFFC1),
                           (0x1000, 0xFFFF), (0x1000, 0x1_0000), (0x1000, 0x100_0000), (0x1000, 0xFFFF_FFFF)):
            self.assertEqual(unmap_exit(built("trim"), lba, count), REJECT, (hex(lba), hex(count)))


@needs_vendor
@unittest.skipUnless(shutil.which("rizin"), "rizin not installed")
class TestListing(unittest.TestCase):
    def test_listing_shows_the_identify_hook(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d, "trim.bin")
            img.write_bytes(built("trim"))
            out = subprocess.run([str(ROOT / "tools/jms561-listing"), str(img), "0", "0x2527:0x252c"],
                                 capture_output=True, text=True, check=True).stdout
        self.assertIn("lcall 0xe310", out)
        self.assertEqual(out.count("nop"), 2)


GHIDRA = Path(os.environ.get("GHIDRA_INSTALL_DIR", Path.home() / ".local/opt/ghidra_12.1.4_PUBLIC"))


@needs_vendor
@unittest.skipUnless((GHIDRA / "support/analyzeHeadless").exists(), "Ghidra not installed")
class TestGhidraDecompile(unittest.TestCase):
    def test_decompiles_the_vendor_dsm_builder(self):
        with tempfile.TemporaryDirectory() as d:
            out, img = Path(d, "dec.c"), Path(d, "img.bin")
            img.write_bytes(built("uas"))
            subprocess.run([str(ROOT / "tools/jms561-ghidra-decompile"), str(img), "0", str(out), "0xccd6"],
                           capture_output=True, text=True, check=True)
            text = out.read_text()
        self.assertIn("uEXTMEM342e = 6;", text)
        self.assertIn("uEXTMEM342f = 1;", text)


if __name__ == "__main__":
    unittest.main()
