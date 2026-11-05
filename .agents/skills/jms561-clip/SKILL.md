---
name: jms561-clip
description: Read or write the SPI flash of a JMS561U enclosure with a CH347T programmer and a SOIC-8 clip. Use for a backup read, writing an image, a rollback, or recovering a bricked enclosure.
---

# SPI flash through the clip

The clip reaches the flash in any state, so it is both the write path for the TRIM image and the rollback. `tools/jms561-clip` reads twice and compares, and verifies every write by reading back twice.

## 1. Host

`lsusb -d 1a86:55db` shows the CH347T. `$FLASHROM` (or `flashrom` in PATH) knows the `ch347_spi` programmer and the `P25D40SH` chip. Otherwise run `tools/setup-flashrom` and export the path it prints. Plug the CH347T into the host directly, on a different port from the enclosure.

## 2. The owner's hands

Give the owner numbered physical steps and wait for them to confirm:

1. Unmount every disk of the enclosure, unplug its USB cable and its 12 V supply.
2. Take the disks out and open the case.
3. Put the clip on U2 (8-pin chip below the JMS561U, marked PUYA), pin 1 on the dot. Photo: `assets/board/spi-flash-u2.jpg`.
4. Connect the CH347T.

When something fails, ask the owner what physically changed between attempts before you name a cause.

## 3. Read

`tools/jms561-clip read <label>` prints `READ <sha256> <path>`. Two reads that differ mean a bad contact: the owner reseats the clip, nothing is written. The first read of an enclosure is its original backup: tell the owner where it is and to copy it somewhere safe.

## 4. Write (after the owner's yes on this sha256 and the clip)

`tools/jms561-clip write <image> <sha256>`. Done when it prints `VERIFIED <sha256>`. A failed piece leaves the chip partly written: run the same command again before any power-up. Rollback is the same command with the owner's original read.

## 5. Boot

The owner: clip off, disk in a bay, 12 V on, USB into a USB 3 port directly. Then `jms561-usb`. Done when `lsusb` shows the enclosure and the product string matches the image ("JMS56T Series" for the TRIM image, "JMS56x Series" for `--uas-only`).
