# AGENTS.md

This repository builds and flashes UASP + TRIM firmware for JMicron JMS561U USB-SATA enclosures (USB `152d:1561`, tested on the Ugreen CM198). You work for the person who owns the enclosure. The enclosure, the disks in it and their data are theirs.

## Hardware safety

The enclosure can be bricked, and a disk behind it can lose data. These rules hold on every step:

- **Consent per write.** Every flash write waits for the owner's explicit yes on the exact image (its sha256) and the method (clip or USB). Prepare the rollback image before you ask.
- **Copy 0 and the parameter pages change only through the SPI clip.** Over USB, write copy 1 only and never send an erase: a USB chip erase bricked the enclosure this project was built on.
- **Backups are sacred.** A flash read gets a unique timestamped name and turns read-only at once (`tools/jms561-clip` does both). The owner's original read is the only source of their parameter pages.
- **Unmount every disk of the enclosure** before a USB reset, power cycle, driver rebind or write, not only the disk under test.
- **A test disk is one the owner named.** `tools/jms561_trim_test.py --labels` takes only labels the owner gave you.
- **Cold boot counts.** A boot test is: 12 V off, clip off, disk in a bay, 12 V on, USB into a USB 3 port directly. A replug with power on proves nothing.
- **Running is observed, not assumed.** "Written and verified" means the chip holds the bytes. "Works" means `lsusb` shows "JMS56T Series" and `tools/jms561-status` shows the expected answers.

## Map

- `docs/README.md`: which document answers which question. Facts about the flash layout, CRCs and boot: `docs/firmware-layout.md`. The patch, row by row: `docs/trim.md`.
- `tools/jms561_inspect.py`: run it on any flash read first. Its verdict picks the path (`docs/your-enclosure.md`).
- `patches/trim.rows`: the patch. `tools/jms561u_build.py`: the only supported way to build an image.
- `.agents/skills/`: `jms561-build` (change or rebuild an image), `jms561-clip` (read or write the flash with the programmer), `jms561-usb` (a powered enclosure over USB).
- `make test`: offline checks. It downloads Ugreen's firmware into `vendor/` first. The simulator tests need `s51` from `tools/setup-ucsim` (export `S51`).

## Done

A change is done when `make test` is green. A hardware step is done when its observation (sha256 read back, `lsusb` product string, `tools/jms561-status` output) is written down for the owner. Images, backups and logs of the owner's enclosure stay out of git: they carry its serial number.
