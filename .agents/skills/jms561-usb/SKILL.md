---
name: jms561-usb
description: Work with a powered JMS561U enclosure over USB on Linux. Use to check UASP and TRIM after a flash, run the exact-block TRIM test, read the flash or bridge memory with vendor commands, or write copy 1 over USB.
---

# A live enclosure over USB

The enclosure has two bays, each its own LUN. Find every disk behind `152d:1561` first (`lsblk -o NAME,TRAN,MOUNTPOINTS`, `tools/jms561-status`).

## Check

`sudo tools/jms561-status` is read-only. UASP + TRIM works when Linux set everything by itself: `driver uas`, product "JMS56T Series", `provisioning_mode unmap`, `lbpme=1`, max unmap LBA count `0xffc0`, `LBPU=1`. An SSD shows `rotational 0`, a hard disk should show `rotational 1` and no unmap.

## Exact-block test

Only on disks the owner named as expendable: `sudo tools/jms561_trim_test.py /dev/sdX [/dev/sdY] --labels <their labels>`. Done when the log in `logs/` ends with `RESULT PASS`. A target that kept its pattern means the drive returns old data after TRIM: report that exactness was not shown.

## Vendor commands (root)

`tools/jms561u-usb` (build with `cargo build --release --manifest-path tools/jms561u-usb/Cargo.toml`): `info <dev>`, `read <dev> <offset> <len> <out>`. Commands are listed in `docs/vendor-usb-protocol.md`. Save raw answers in files with a timestamp in the name.

## Write over USB (after the owner's yes on the sha256 and this method)

`write` puts a 128 KiB bank into copy 1 and leaves copy 0 alone, so it cannot install the TRIM image. Use it only for an experiment that targets copy 1, with the clip and the owner's backup ready:

1. Run `write <dev> <image> <sha256>` without `--go` and compare the printed CDBs with `docs/vendor-usb-protocol.md`.
2. Unmount every disk of the enclosure, then run it with `--go`. Done when it prints `VERIFIED`.
3. The owner power-cycles 12 V, then run the check above.
