# FAQ

### How do I enable TRIM on a JMS561U enclosure such as the Ugreen CM198?

Flash firmware that reports it. Stock firmware never does: it reports `lbpme=0` and no unmap limits, and it rejects SCSI UNMAP. This repository builds Ugreen's 2018 firmware with JMicron's own TRIM path switched on, using your enclosure's settings, and you write it with an SPI programmer. Start with [flashing.md](flashing.md).

### `fstrim: /mnt: the discard operation is not supported`. Can I fix it on the host?

Not on this bridge. The usual advice for USB SSDs is a udev rule that sets `provisioning_mode` to `unmap`. That works on bridges that already execute UNMAP. The stock JMS561U answers UNMAP with "invalid command operation code", so the discards just fail. Over usb-storage (BOT) Linux doesn't even ask the bridge about provisioning for disks under 2 TB. Details: [trim.md](trim.md).

### Why does my enclosure use `usb-storage` instead of `uas`?

Ugreen's current CM198 firmware (167.2.0.21) has no UAS interface. Their 2018 firmware (167.1.0.4) does. `tools/jms561u_build.py --uas-only` builds it with your enclosure's own settings. [uasp.md](uasp.md).

### Does the JMS561 / JMS561U support UASP and TRIM at all?

The chip does. JMicron's brief lists UASP 1.0, and its firmware contains a complete UNMAP to ATA TRIM translation, switched off in every JMS561 and JMS561U build we checked. With the patch, our CM198 runs UASP and TRIM on both bays.

### Is there a JMS561U firmware update with TRIM?

Not from JMicron or Ugreen, as far as we could find in November 2026. [firmware-catalog.md](firmware-catalog.md) lists every JMS561/JMS561U firmware we came across. All of them have the TRIM code and clear the same flag to switch it off.

### Will it work on my enclosure (Acasis, Sabrent, VINIK, an unbranded dock)?

Read your flash over USB, which doesn't need opening the case on stock firmware, and run `tools/jms561_inspect.py` on it. It names your firmware and says whether you're on the tested path, on an untested board with the same layout, or on a different chip family. [your-enclosure.md](your-enclosure.md).

### Can I flash it over USB without opening the enclosure?

Not this image, not yet. Ugreen's updater writes copy 1 of the firmware, and the bridge runs copy 0, which this image changes. You need an SPI programmer (we used a CH347T with a SOIC-8 clip). [flashing.md](flashing.md#why-not-over-usb).

### What does "JMS56T Series" in `lsusb` mean?

It's the marker the patch puts into the product string. It means the patched code is running. Ugreen's 2018 code says "JMS56x Series", the 2020 code "Ugreen Storage Device".

### Why did my SSD write so slowly in the enclosure?

Ours wrote 42.7 MiB/s before its first TRIM and 389 MiB/s after it, reading at about 370 to 380 MiB/s throughout. The filesystem was only 2% full. Most likely the drive's flash was clogged with deleted but never trimmed blocks after years behind bridges without TRIM. [testing.md](testing.md).

### Does it work with hard disks?

It should behave like stock. The patch enables TRIM only for a drive whose IDENTIFY data says it supports TRIM, and reports the rotation rate from the drive. We haven't tested an HDD yet.

### `hdparm --trim-sector-ranges` fails with "Invalid exchange". Why?

hdparm sends DSM with ATA pass-through protocol 6 (DMA), and this bridge's pass-through refuses protocol 6. With the patched firmware you don't need hdparm: use `fstrim` or `blkdiscard`.

### Does SMART work?

SMART pass-through (`smartctl -d sat`) worked with the 2018 firmware on our enclosure. Be careful with pass-through commands that write to the second bay: on one two-bay JMicron bridge (`152d:2352`) they reportedly went to port 0 whatever LUN was used.

### Does the clone button / sleep timer still work?

We didn't change either, and didn't test them with the patched firmware. Ugreen's package that carries the 2018 firmware is a "turn off sleep mode" tool, so the 2018 firmware may sleep differently from the 2020 one.

### Windows and macOS?

The firmware runs in the enclosure, so it's the same for every host. Whether Windows or macOS send UNMAP to it, we haven't checked. Everything in this repository was tested on Linux.

### What about JMS561 RAID?

The JMS561 can run RAID. In that mode it changes its USB ID to `152d:a561` and hides the member disks (smartmontools #656). The CM198 exposes the two disks as two LUNs, and that's the only mode we used.

### Can I brick it?

Yes. A bad image means opening the case and writing a backup with the programmer. Keep the clip and your backup ready. [recovery.md](recovery.md).

### How was this found?

By reverse engineering the 8051 code with Ghidra, rizin and a simulator, and by testing every candidate image on the hardware. [methods.md](methods.md) explains how, [lessons.md](lessons.md) what went wrong on the way.
