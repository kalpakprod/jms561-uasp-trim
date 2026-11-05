#!/usr/bin/env python3
"""Build a UASP or UASP+TRIM flash image for a JMicron JMS561U enclosure (Ugreen CM198).

    jms561u_build.py --backup MY-FLASH.bin --out NEW.bin            UASP + TRIM (default)
    jms561u_build.py --backup MY-FLASH.bin --out NEW.bin --uas-only UASP only, vendor 2018 code

Run tools/jms561_inspect.py on your backup first: it tells you whether this builder fits.

Inputs:
  --vendor  Ugreen's own 2018 release CM198-v167.001.000.004-20180730-meta.bin (256 KiB),
            fetched by tools/fetch-ugreen-2018. Default: vendor/<that name>.
  --backup  a full 512 KiB read of YOUR enclosure's SPI flash (tools/jms561-clip read).
            Only its parameter pages (0x40000..0x7FFFF) are used: they hold the USB IDs,
            serial number and the settings the bridge needs to offer UASP. They are specific
            to each enclosure, which is why no ready-made image is published.
  --other-board  needed when your backup holds firmware other than Ugreen's CM198 code
            (2018, 2020 or this project's). Ugreen's code was tested on the CM198 board
            only: buttons, LEDs and clone mode on another board may not work.

Output (512 KiB, for an SPI programmer):
  0x00000  copy 0: vendor 2018 code + patches/trim.rows, every CRC recomputed
           (with --uas-only: vendor 2018 code unchanged)
  0x20000  copy 1: vendor 2018 code unchanged
  0x40000  parameter pages from your backup, byte for byte

The first 256 KiB of the output must equal a published hash; the tool checks it, so a
build that prints OK is byte-identical to the image tested on real hardware.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jms561_apply import apply, rows  # noqa: E402
from jms561_crc_rows import check_bank, pack_bank  # noqa: E402
from jms561_inspect import inspect  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR_NAME = "CM198-v167.001.000.004-20180730-meta.bin"
VENDOR_SHA = "57099a24904f87afc5fe8ccd195c554a002eda058ed3e0c111594325243e64e7"
TRIM_ROWS = os.path.join(ROOT, "patches", "trim.rows")
# sha256 of output[0x00000:0x40000] for each mode (both copies, no parameter pages)
CODE_SHA = {
    "trim": "6855b9b5625f1570e1f52c67d05a194b66994213dadc52aa70bf9e39c04d440c",
    "uas": VENDOR_SHA,
}
PARAM_PAGES = {0x41000: b"IVP0", 0x44000: b"IPP0", 0x45000: b"IUP0", 0x46000: b"WDq1"}
KNOWN = {
    "388672c1f9c28dba9fb4889f06f017a165824f408b0bc1f59022ef0a9bb04801": "Ugreen stock 167.2.0.21 (2020, no UASP)",
    VENDOR_SHA: "Ugreen 167.1.0.4 (2018, UASP, no TRIM)",
    CODE_SHA["trim"]: "this project's UASP + TRIM image",
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def version(img):
    """Firmware version from the bank 0 header, e.g. 167.2.0.21."""
    return ".".join(str(x) for x in img[0x19:0x1D])


def check_backup(b, other_board=False):
    if len(b) != 0x80000:
        raise SystemExit(f"backup is {len(b)} bytes, expected a full 524288-byte (512 KiB) flash read")
    r = inspect(b)
    if r["verdict"] == "other-family":
        raise SystemExit("backup is from a JMS561 / JMS561B (header 0561), not a JMS561U: " + r["advice"])
    if r["verdict"] == "same-layout" and not other_board:
        raise SystemExit("backup holds firmware other than Ugreen's CM198 code. " + r["advice"]
                         + " See docs/your-enclosure.md.")
    missing = [f"{tag.decode()} at {off:#x}" for off, tag in PARAM_PAGES.items() if b[off:off + 4] != tag]
    if missing:
        raise SystemExit("backup has no parameter pages (" + ", ".join(missing) + "). Without them the "
                         "bridge loses UASP and its USB IDs. Use a read of the original chip.")


def build(vendor, backup, mode, other_board=False):
    if sha(vendor) != VENDOR_SHA:
        raise SystemExit(f"vendor file sha256 {sha(vendor)} is not {VENDOR_SHA}: wrong file")
    check_backup(backup, other_board)
    base = vendor + backup[0x40000:]
    if mode == "uas":
        out = base
    else:
        with open(TRIM_ROWS) as f:
            raw = apply(base, rows(f.read()))
        out = pack_bank(raw, base, 0x00000)
    bad = check_bank(out, 0x00000, verbose=False) + check_bank(out, 0x20000, verbose=False)
    if bad:
        raise SystemExit(f"CRC check failed: {bad}")
    if sha(out[:0x40000]) != CODE_SHA[mode]:
        raise SystemExit(f"code part sha256 {sha(out[:0x40000])} is not the published {CODE_SHA[mode]}")
    if out[0x40000:] != backup[0x40000:]:
        raise SystemExit("parameter pages changed: internal error")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vendor", default=os.path.join(ROOT, "vendor", VENDOR_NAME))
    ap.add_argument("--backup", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--uas-only", action="store_true", help="vendor 2018 code without the TRIM patch")
    ap.add_argument("--other-board", action="store_true",
                    help="accept a backup whose firmware is not Ugreen's CM198 code (untested board)")
    a = ap.parse_args(argv)
    if not os.path.exists(a.vendor):
        raise SystemExit(f"{a.vendor} not found: run tools/fetch-ugreen-2018 first")
    with open(a.vendor, "rb") as f:
        vendor = f.read()
    with open(a.backup, "rb") as f:
        backup = f.read()
    mode = "uas" if a.uas_only else "trim"
    out = build(vendor, backup, mode, a.other_board)
    with open(a.out, "xb") as f:
        f.write(out)
    names = sorted({c["known_name"] or "unknown firmware" for c in inspect(backup)["copies"] if c.get("project")})
    print(f"backup  {sha(backup)}  firmware {version(backup)}: {'; '.join(names)}")
    print(f"code    {sha(out[:0x40000])}  {KNOWN[CODE_SHA[mode]]} (matches the published hash)")
    print(f"OK      {sha(out)}  {a.out}")
    print("Write it with an SPI programmer: tools/jms561-clip write", a.out, sha(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
