# JMicron vendor commands over USB (JMS561U)

The JMS561U answers a few vendor-specific SCSI commands. On Linux you send them through SG_IO as root. The `DF`/`E0`/`FF` family is the same one projectgus documented for the JMS567 in jms567ctl. We checked every command below on our CM198 with the stock firmware; xRetia's notes say these commands work only over BOT, not UAS, which we haven't tested.

| Command | CDB | What it does |
|---|---|---|
| Chip info | `E0 F4 E7 00 00 00 00 00 00 00 00 00` | 16 bytes back. `[5]` = family (`0x65` 'e' on the JMS561U), `[6]` = mode (3 = normal firmware), last 4 bytes = firmware version from the data bank's header |
| Flash read | `DF 10 00 <len:2 BE> 00 00 00 <addr:3 BE> FA` | up to 4 KiB per command, the address is masked to 19 bits. A nonzero CDB byte 2 resets the bridge |
| XRAM read | `DF 10 00 <len:2> 00 <addr:2> 00 00 00 FD` | reads bridge RAM, the image header sits at XRAM `0x3600` |
| JEDEC ID | `FF 04 15 04 9F 00 …` | `85 60 13 85` for the P25D40SH |
| READ BUFFER | `3C 01 …` | returns **flash** contents (0x200..0x3FF zeroed), not RAM. It can't show you the running code |
| Chip erase | `DF 03 FB …` | erases the whole 512 KiB, parameter pages included. **This bricked our enclosure.** Never send it |

## The update sequence of Ugreen's JMMassProd 1.16.15.7

Reversed from the Windows tool and replayed by [`tools/jms561u-usb`](../tools/jms561u-usb):

1. `3C 03` READ BUFFER descriptor: the bridge answers `0c 02 00 00` (4 KiB blocks, 128 KiB buffer).
2. `3B 0E` WRITE BUFFER, 32 blocks of 4 KiB, strictly in order from offset 0, `0x20000` bytes in total. The first block erases the target bank, so give it a long timeout.
3. `3B 0F` commit.

What the bridge does with it:

- It writes the image into **copy 1** (flash `0x20000`), marks `0x207 = 01` there and leaves copy 0 alone.
- It checks the footer CRC and refuses the last block with sense `5/0x26` if it's wrong. It doesn't check the code CRC.
- The upload has to be in release format: zeros at `0x200..0x3FF`, the bridge fills in that metadata itself. After a commit, `0x800..0xFFF` of the bank reads `FF` (the release files have zeros there).

jmm.exe also contains a mask-ROM recovery path (a 64 KiB service image, mode 6). We didn't try it.

## Reading your flash over USB

On stock firmware, `jms561u-usb read /dev/sdX 0 0x80000 flash.bin` reads all 512 KiB without opening the case. That's a fine way to look at your firmware and your parameter pages. For the TRIM image you still need the clip to write, so we took our backups with the clip.

## Linux side

- You need `sg3_utils` only for the checks: `sg_readcap -l`, `sg_vpd -p bl|lbpv|bdc`, `sg_unmap`.
- ATA pass-through (`85`/`A1`, handler at CPU `0x4150` in the 2018 code) accepts protocols 0, 1, 3, 4, 5, 10, 11 and 15 and refuses 6 (DMA). That's why `hdparm --trim-sector-ranges` fails on this bridge: hdparm 9.65 sends DSM with protocol 6.
