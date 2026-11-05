#!/usr/bin/env python3
"""Inspect a JMicron JMS561 / JMS561U flash read and say which path in this repository fits it.

    jms561_inspect.py MY-FLASH.bin           a report for people
    jms561_inspect.py MY-FLASH.bin --json    the same as JSON, for scripts and coding agents

Input: a full 512 KiB read of the enclosure's SPI flash (tools/jms561-clip read), or a
256 KiB release file (both copies, no parameter pages) to identify a firmware you downloaded.

It never writes anything. The USB serial number from the parameter pages is masked, so
the report is safe to paste into an issue.

What it reports:
  - each of the two firmware copies: chip family, version, checksums, which known firmware
    it is (by the sha256 of its 8051 code window), whether it offers UASP, whether it has
    the UNMAP -> ATA TRIM translation and how TRIM is switched off or on
  - the parameter pages: where they are, the USB ID and the "UAS disabled" byte
  - the verdict: ready (tested path), same-layout (builds, untested board), no-pages,
    release-file, other-family or unreadable. docs/your-enclosure.md explains each one.
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jms561_crc_rows import bank_k, check_bank, code_crc  # noqa: E402

BANKS = (0x00000, 0x20000)
FLASH = 0x80000
RELEASE = 0x40000
PAGES = {0x41000: "IVP0", 0x44000: "IPP0", 0x45000: "IUP0", 0x46000: "WDq1"}
USB_ID_AT = 0x4400C      # IPP0: vendor and product ID, big-endian
SERIAL_AT = 0x44040      # IPP0: USB serial number, 20 ASCII characters
UAS_OFF_AT = 0x46008     # WDq1: nonzero = UAS disabled

# sha256 of the 8051 code window of one copy (bank + 0x10000 .. bank + 0x1FFEF)
KNOWN_CODE = {
    "c3677bdc1adb5d3bc331a4063baff6021aa90f4b332adc0a1af89707887eb94f":
        ("ugreen-2018", "Ugreen CM198 167.1.0.4 (2018): UASP, TRIM off"),
    "a2943befc50267556cad8098afc3dc4d078cbce5739c9f4769fe13c1145627ff":
        ("ugreen-2020", "Ugreen CM198 167.2.0.21 (2020, as shipped): no UASP, TRIM off"),
    "d207c997f7d6d663c7825a11f97d4d7f68b3c660fe4944632e0e060bda75c500":
        ("this-trim", "this project: Ugreen 167.1.0.4 + patches/trim.rows (UASP + TRIM)"),
    "4571f205a3dc3e258796d64a731f405ee6ffcde940e2eb0f49111d3095063950":
        ("jmicron-20.3.2.2", "JMicron reference 20.3.2.2 (FwUpdater561U)"),
    "4a9b0eb5d06cf911e8d3d1b85d3a3782c0763112142657bf48c2dc5477d5cf22":
        ("jmicron-20.3.2.4", "JMicron reference 20.3.2.4 (FwUpdater561U)"),
    "a1bad2f7e9565233c52356091bbc0d82e61004de58e35548bfd65e01c62377d5":
        ("jms561u-09.1.2.2", "JMS561U 09.1.2.2"),
    "cf310f9d0b555a4944df0a732b70076c7d4d62d527769209390843cbd4419268":
        ("hardkernel-158.1.0.1", "Hardkernel JMS561 158.1.0.1 (Odroid CloudShell2)"),
    "6c04c945ea0502c9fd32d7a6c0a1260e66ab90c4c13471442d7e7801f1d17139":
        ("jms561b-8.1.3.6", "JMS561B 8.1.3.6"),
    "681bc8f1b027ff8608c67ac10a330cb956fcbd608479e5075b85b38fa2d9bd6a":
        ("ce702-107.1.0.3", "JMS561 CE702 107.1.0.3 (2018)"),
    "36cfc403c4128a455607f96dca62e3ae7e41f152575ca9620acf998400991f12":
        ("ce702-107.1.0.4", "JMS561B Coltech CE702 107.1.0.4 (2024)"),
}
# Ugreen CM198 code bases: an enclosure that ran one of these is a CM198 or a close clone
CM198_CODE = {"ugreen-2018", "ugreen-2020", "this-trim"}

# 8051 byte patterns, searched in the code window
UASP_IFACE = re.compile(rb"\x09\x04\x00\x01.\x08\x06\x62", re.S)   # interface 0, alt 1, mass storage, UAS
DSM_TASKFILE = re.compile(rb"\x90\x34\x2e\x74\x06\xf0\xa3\x74\x01\xf0\x90\x34\x2c\xf0\x90\x34\x33\x74\x40\xf0")
# DPTR = 0x3FA9 + index; then CLR A; MOVX @DPTR,A (stock) or LCALL stub (this project)
FLAG_STORE = re.compile(rb"(?:\x24\xa9|\x74\xa9\x25.)\xf5\x82\xe4\x34\x3f\xf5\x83(\xe4\xf0|\x12..)", re.S)
FLAG_READ = re.compile(rb"\x74\xa9\x25([\x40-\x4f])\xf5\x82\xe4\x34\x3f\xf5\x83\xe0", re.S)
TRIM_MARKER = b"JMS56T Series"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def version(h):
    """Version from a bank header: binary (a7 01 00 04 -> 167.1.0.4) or ASCII digits ('9122')."""
    v = h[0x19:0x1D]
    if all(0x30 <= c <= 0x39 for c in v):
        return ".".join(chr(c) for c in v) + " (ASCII)"
    return ".".join(str(c) for c in v)


def code_window(img, b):
    return img[b + 0x10000:b + 0x1FFF0]


def inspect_copy(img, b):
    c = {"offset": b}
    if img[b + 0x1FFF0:b + 0x1FFF8] != b"EXROMEND":
        c["valid"] = False
        c["problem"] = "no EXROMEND at +0x1FFF0: empty, erased or not a JMS56x copy"
        return c
    code = code_window(img, b)
    h = img[b:b + 0x20]
    c["project"] = h[2:6].decode("latin1")
    c["name"] = h[10:24].split(b"\x01")[0].split(b"\x00")[0].decode("latin1", "replace")
    c["version"] = version(h)
    c["code_sha256"] = sha(code)
    known = KNOWN_CODE.get(c["code_sha256"])
    c["known"] = known[0] if known else None
    c["known_name"] = known[1] if known else None
    c["code_crc_ok"] = img[b + 0x1FFF8:b + 0x1FFFC] == code_crc(img, b).to_bytes(4, "big")
    c["other_crc_bad"] = [name for _, name, _, _ in check_bank(img, b, verbose=False)
                          if not name.startswith("code")]
    c["footer_k"] = f"{bank_k(img, b):08x}"
    c["valid"] = c["code_crc_ok"] and not c["other_crc_bad"]
    c["uasp"] = bool(UASP_IFACE.search(code))
    m = DSM_TASKFILE.search(code)
    c["trim_translation_at"] = f"{m.start():#06x}" if m else None
    stores = [(m.start(1), m.group(1)) for m in FLAG_STORE.finditer(code)]
    c["trim_flag_cleared_at"] = [f"{a:#06x}" for a, op in stores if op == b"\xe4\xf0"]
    c["trim_flag_patched_at"] = [f"{a:#06x}" for a, op in stores if op[0] == 0x12]
    reads = [(m.start(), m.group(1)[0]) for m in FLAG_READ.finditer(code)]
    # the flag is indexed by LUN (RAM 0x40, vendor) or by port (RAM 0x43, this project's fix)
    c["trim_flag_reads"] = {f"{a:#06x}": ("LUN" if r == 0x40 else "port" if r == 0x43 else f"{r:#04x}")
                            for a, r in reads}
    c["trim_marker"] = TRIM_MARKER in code
    end = len(code.rstrip(b"\x00"))
    c["free_space"] = f"{end:#06x}..{len(code) - 1:#06x} ({len(code) - end} bytes of zero padding)"
    c["trim"] = trim_state(c)
    return c


def trim_state(c):
    if c["known"] == "this-trim" or (c["trim_flag_patched_at"] and c["trim_marker"]):
        return "on (this project's patch)"
    if not c["trim_translation_at"]:
        return "no UNMAP -> TRIM translation found"
    if c["trim_flag_cleared_at"]:
        return "translation present, switched off: the flag is cleared at " + ", ".join(c["trim_flag_cleared_at"])
    return "translation present, switch-off point not recognised (needs manual work)"


def inspect_pages(img):
    p = {"tags": {f"{off:#x}": img[off:off + 4].decode("latin1") for off in PAGES},
         "layout": "cm198" if all(img[off:off + 4] == t.encode() for off, t in PAGES.items()) else None}
    if p["layout"]:
        p["usb_id"] = "%04x:%04x" % (int.from_bytes(img[USB_ID_AT:USB_ID_AT + 2], "big"),
                                     int.from_bytes(img[USB_ID_AT + 2:USB_ID_AT + 4], "big"))
        serial = img[SERIAL_AT:SERIAL_AT + 20].split(b"\x00")[0].decode("latin1").strip()
        p["serial"] = f"present, {len(serial)} characters (hidden)" if serial.isprintable() and serial else None
        p["uas_disabled"] = img[UAS_OFF_AT] != 0
    else:
        found = [f"{off:#x} {img[off:off + 4].decode('latin1')}" for off in range(0x40000, FLASH, 0x1000)
                 if re.fullmatch(rb"[A-Za-z][A-Za-z0-9]{3}", img[off:off + 4])]
        p["other_tags"] = found
        tail = img[0x40000:]
        p["blank"] = tail.count(0xFF) == len(tail) or tail.count(0) == len(tail)
    return p


def verdict(r):
    copies = [c for c in r["copies"] if c["valid"] or c.get("project")]
    if not copies:
        return "unreadable", "Neither copy looks like JMS56x firmware. Check the read: clip contact, chip type, size."
    projects = {c["project"] for c in copies}
    if projects - {"0565"}:
        return "other-family", ("Header '%s': a JMS561 / JMS561B (USB 152d:0561 family), not the JMS561U. "
                                "The images here don't fit it." % "/".join(sorted(projects)))
    if r["size"] == RELEASE:
        return "release-file", "A 256 KiB release file without parameter pages. To build, read your own flash (512 KiB)."
    if r["pages"]["layout"] != "cm198":
        return "no-pages", ("The parameter pages are not where the CM198 keeps them. Without them the builder "
                            "can't preserve your enclosure's settings: stop and keep this read safe.")
    if any(c.get("known") in CM198_CODE for c in copies):
        return "ready", "Same firmware family and layout as the tested Ugreen CM198: tools/jms561u_build.py applies."
    return "same-layout", ("Same flash layout as the CM198, different firmware. The builder works with "
                           "--other-board, but Ugreen's code on your board is untested: clip and rollback ready.")


def inspect(img):
    if len(img) not in (FLASH, RELEASE):
        raise SystemExit(f"{len(img)} bytes: expected a 524288-byte flash read or a 262144-byte release file")
    r = {"size": len(img), "sha256": sha(img), "code_part_sha256": sha(img[:RELEASE]),
         "copies": [inspect_copy(img, b) for b in BANKS]}
    if len(set(img)) == 1:
        r["copies"] = [{"offset": b, "valid": False, "problem": f"every byte is {img[0]:#04x}"} for b in BANKS]
    if len(img) == FLASH:
        r["pages"] = inspect_pages(img)
    c0, c1 = r["copies"]
    r["boots"] = ("copy 0" if c0["valid"] else "copy 1" if c1["valid"] else "neither (no valid copy)")
    r["verdict"], r["advice"] = verdict(r)
    return r


def text(r, path):
    out = [f"file        {path}", f"size        {r['size']} bytes, sha256 {r['sha256']}"]
    for i, c in enumerate(r["copies"]):
        out.append(f"copy {i}      at {c['offset']:#07x}")
        if not c.get("project"):
            out.append(f"  problem   {c['problem']}")
            continue
        out.append(f"  firmware  {c['project']} '{c['name']}' version {c['version']}")
        out.append(f"  code      sha256 {c['code_sha256']}")
        out.append(f"  known as  {c['known_name'] or 'unknown to this repository (please report it)'}")
        crc = "OK" if c["valid"] else ("code CRC stale" if not c["code_crc_ok"] else "bad: " + ", ".join(c["other_crc_bad"]))
        out.append(f"  checksums {crc}  (footer K {c['footer_k']})")
        out.append(f"  UASP      {'yes (alternate setting 1, UAS)' if c['uasp'] else 'no (Bulk-Only only)'}")
        out.append(f"  TRIM      {c['trim']}")
        out.append(f"  free      {c['free_space']}")
        if c["trim_translation_at"]:
            reads = ", ".join(f"{a} by {k}" for a, k in c["trim_flag_reads"].items()) or "-"
            out.append(f"            DSM taskfile at {c['trim_translation_at']}, flag read at {reads}")
    out.append(f"boots       {r['boots']} (most likely: the bridge skips a copy with a stale code CRC)")
    p = r.get("pages")
    if p:
        if p["layout"]:
            out.append(f"pages       CM198 layout: {', '.join(t for t in p['tags'].values())}")
            out.append(f"  USB ID    {p['usb_id']}, serial {p['serial'] or '(none)'}, "
                       f"UAS {'DISABLED by the pages' if p['uas_disabled'] else 'allowed'}")
        else:
            out.append("pages       not at the CM198 offsets "
                       + ("(the area is blank)" if p["blank"] else f"(tags found: {', '.join(p['other_tags']) or 'none'})"))
    out.append(f"verdict     {r['verdict']}: {r['advice']}")
    out.append("            docs/your-enclosure.md explains what to do next.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with open(a.image, "rb") as f:
        r = inspect(f.read())
    print(json.dumps(r, indent=2) if a.json else text(r, a.image))
    return 0


if __name__ == "__main__":
    sys.exit(main())
