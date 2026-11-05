# Your JMS561 enclosure: find out what fits it

This project was built and tested on one Ugreen CM198. Many other two-bay enclosures use the same JMicron bridge with different firmware, and some of them will take this firmware and some won't. You don't have to guess: read your flash, run the inspector, and it tells you which of the cases below is yours.

## 1. Which chip do you have?

```sh
lsusb | grep -i 152d
```

| USB ID | Chip | This repository |
|---|---|---|
| `152d:1561` | JMS561U | the target, read on |
| `152d:0561` | JMS561 or JMS561B | different firmware family, see [the JMS561 family](#the-jms561-family-152d0561) |
| `152d:a561` and similar | a JMS561 in RAID mode hides its disks behind its own ID | switch the enclosure to JBOD / normal mode first and look again |
| `152d:0578`, `0567`, `0583` | JMS578 / JMS567 / JMS583, single-bay bridges | not this chip, see [firmware-catalog.md](firmware-catalog.md#neighbours-with-working-trim) |

## 2. Read your flash

You need a full 512 KiB read. There are two ways to get it.

Over USB you don't have to open the case. On stock firmware the bridge answers JMicron's flash-read command, and [`tools/jms561u-usb`](../tools/jms561u-usb) uses only that command here:

```sh
cd tools/jms561u-usb && cargo build --release && cd ../..
sudo tools/jms561u-usb/target/release/jms561u-usb info /dev/sdX
sudo tools/jms561u-usb/target/release/jms561u-usb read /dev/sdX 0 0x80000 my-flash.bin
```

Unmount the enclosure's disks first. Read twice and compare the sha256: two equal reads are your backup. This is enough to run the inspector and decide whether to go further. For writing the TRIM image you'll still need the clip ([flashing.md](flashing.md#why-not-over-usb)).

With an SPI programmer, follow [flashing.md](flashing.md). `tools/jms561-clip read original` makes two reads, compares them and keeps the result read-only.

Keep this read. It holds your enclosure's own parameter pages, its USB serial number among them, and it's the only way back if a later write goes wrong. Don't post the file itself anywhere.

## 3. Run the inspector

```sh
tools/jms561_inspect.py my-flash.bin
```

It only reads the file. For our CM198 as it came from the shop it printed:

```
copy 0      at 0x00000
  firmware  0565 'JMicron JMS565' version 167.2.0.21
  known as  Ugreen CM198 167.2.0.21 (2020, as shipped): no UASP, TRIM off
  checksums OK  (footer K 1bcc43a3)
  UASP      no (Bulk-Only only)
  TRIM      translation present, switched off: the flag is cleared at 0x24e4
  free      0xbb38..0xffef (17592 bytes of zero padding)
copy 1      ...
boots       copy 0 (most likely: the bridge skips a copy with a stale code CRC)
pages       CM198 layout: IVP0, IPP0, IUP0, WDq1
  USB ID    152d:1561, serial present, 12 characters (hidden), UAS allowed
verdict     ready: Same firmware family and layout as the tested Ugreen CM198: tools/jms561u_build.py applies.
```

The serial number is never printed, so the report is safe to paste into an issue. `--json` gives the same as JSON.

What the lines mean:

- **firmware**: the project ID and version from the header of each copy. JMS561U firmware says `0565 / JMicron JMS565`. Don't let that confuse you.
- **known as**: the inspector hashes the 8051 code of each copy and compares it with every firmware this project has seen ([firmware-catalog.md](firmware-catalog.md)). "Unknown" isn't bad news. It means nobody has reported that firmware yet.
- **checksums** and **boots**: a copy with a stale code CRC is most likely skipped at power-up ([firmware-layout.md](firmware-layout.md#boot)).
- **UASP**: whether the copy offers the UAS alternate setting at all. Without it Linux uses `usb-storage`, and over `usb-storage` it never asks a disk under 2 TB about TRIM ([trim.md](trim.md)).
- **TRIM**: whether the copy has JMicron's UNMAP to ATA TRIM translation, and where the firmware switches it off. Every firmware we've opened has the translation and switches it off.
- **free**: the zero padding after the last code byte. A patch puts its new code there.
- **pages**: the parameter pages, the USB ID they set and the byte that can disable UAS.

## 4. What the verdict means

### ready

Your flash has the CM198 layout and one of the firmwares that ran on the tested enclosure: Ugreen 2020, Ugreen 2018 or this project's image. That's the tested path: [flashing.md](flashing.md) from step 2.

### same-layout

Your parameter pages sit where the CM198 keeps them, but your firmware is something else, so your board is probably not a CM198. The builder will make an image from Ugreen's 2018 code and your pages, but only with `--other-board`, because nobody has run Ugreen's code on your board. Things that differ between boards and might not work: the clone button, the LEDs, power control of the bays, RAID switches. The bridge itself and the SATA side are the same chip, so the odds aren't bad, but it's an experiment:

- have the clip working and your backup checked before you write anything
- after the first boot, check `lsusb`, both bays, the LEDs and the buttons before you put data on it
- whatever happens, please [report it](../../../issues/new?template=enclosure-report.yml): one report turns "untested" into "works" or "doesn't" for every owner of that enclosure.

If your own firmware has UASP and you'd rather keep it, the alternative is to port the patch to it ([below](#porting-the-patch-to-another-firmware)).

### no-pages

The inspector didn't find the four parameter pages at `0x41000`, `0x44000`, `0x45000` and `0x46000`. Either your board keeps its settings elsewhere (the inspector lists any page tags it found), or that area was erased. The builder refuses this case: an image needs your own pages. Our enclosure, with these pages and copy 0 both erased, didn't enumerate at all. Keep the read, don't write anything, and open an issue with the inspector output.

### release-file

You gave it a 256 KiB file: a firmware release (both copies, no parameter pages), not a read of your chip. The inspector still tells you what the firmware is, whether it has UASP and where TRIM is switched off. To build, read your own flash.

### other-family

The header says `0561`: the file is for the JMS561 or JMS561B, a separate firmware family. The builder refuses it, see [the JMS561 family](#the-jms561-family-152d0561).

### unreadable

Neither copy looks like JMS56x firmware: all bytes equal, or no `EXROMEND` marker. With the clip that usually means bad contact or the wrong chip setting. Reseat the clip and read again before anything else.

## What the inspector finds in the firmware we hold

The same TRIM translation is in every image, with the flag cleared after the drive is identified. "Flag cleared at" is the `CLR A; MOVX @DPTR,A` that the patch replaces.

| Firmware | Header | UASP | TRIM translation | Flag cleared at | Free space |
|---|---|---|---|---|---|
| Ugreen CM198 167.1.0.4 (2018) | 0565 | yes | `0xCCD9` | `0x2527` | `0xE30D..` |
| Ugreen CM198 167.2.0.21 (2020) | 0565 | no | `0xA7B4` | `0x24E4` | `0xBB38..` |
| JMicron reference 20.3.2.2 | 0565 | yes | `0xCCF1` | `0x2535` | `0xE385..` |
| JMicron reference 20.3.2.4 | 0565 | yes | `0xCCC0` | `0x2535` | `0xE361..` |
| JMS561U 09.1.2.2 | 0565 | yes | `0xC842` | `0x1B97` | `0xDE03..` |
| Hardkernel JMS561 158.1.0.1 | 0561 | no | `0xA7B3` | `0x2774` | `0xBB4D..` |
| JMS561B 8.1.3.6 | 0561 | yes | `0xCD32` | `0x254E` | `0xE3B4..` |
| JMS561 CE702 107.1.0.3 | 0561 | yes | `0xD0C3` | `0x30D6` | `0xE7F0..` |
| JMS561B CE702 107.1.0.4 | 0561 | yes | `0xD3BC` | `0x2D08` | `0xE7E7..` |

JMicron's reference 20.3.2.x is a close relative of Ugreen's 2018 code: the three reads of the TRIM flag in the VPD handlers sit at the very same addresses (`0x1778`, `0x17B5`, `0x1829`), and the flag clear is 14 bytes further on. Porting the patch there should be mostly a matter of shifting addresses.

## Porting the patch to another firmware

This is for people who are comfortable reading 8051 code. Nobody has done it yet. The steps follow the six parts of the patch in [trim.md](trim.md). For each one, find the matching place in your firmware:

1. **The flag store.** The inspector gives its address. Replace `CLR A; MOVX @DPTR,A` and the following 3-byte instruction with `LCALL stub; NOP; NOP`, and make the stub copy IDENTIFY word 169 bit 0 into the flag and redo the overwritten instruction. In 2018 the IDENTIFY buffer starts at XRAM `0x3600`, so word 169's low byte is at `0x3752`. The ATA taskfile addresses are the same in every image above, but confirm the IDENTIFY buffer address in your firmware with a disassembler.
2. **LBPME** in the READ CAPACITY(16) reply: find where the handler clears reply byte 14 (XRAM `0x3A0E` in 2018).
3. **LUN versus port.** The inspector lists each read of the flag and whether it indexes by LUN (RAM `0x40`) or port (RAM `0x43`). Change the VPD B0, VPD B2 and UNMAP gate reads to port.
4. **Rotation rate** in VPD B1: point it at the word-217 table instead of the TRIM flag.
5. **A marker** in the USB product string, so `lsusb` tells you the patched copy runs.
6. **The UNMAP guard**: route the parser's accept exit through the LBA and count check. Don't skip this one. Without it, a high LBA silently trims a low one.

Put new code into the free space the inspector reports. Our stubs at `0xE310` in the 2018 code ran fine. In another firmware, check with a disassembler that nothing jumps into or reads from the range you use. Then:

- write your rows in the format of [`patches/trim.rows`](../patches/trim.rows) and apply them with [`tools/jms561_apply.py`](../tools/jms561_apply.py), which refuses rows whose "before" bytes don't match
- recompute every CRC of copy 0 with `tools/jms561_crc_rows.py pack` (it derives the release constant K from your own image)
- run your stubs in the 8051 simulator the way [`tests/test_trim_patch.py`](../tests/test_trim_patch.py) does, including the UNMAP guard cases
- change copy 0 only and leave copy 1 as it was, flash with the clip, keep the backup at hand, and run [`tools/jms561_trim_test.py`](../tools/jms561_trim_test.py) on a disk you can lose.

A pull request with `patches/trim-<firmware>.rows`, its test and a hardware report is very welcome. [methods.md](methods.md) shows how we found each place, and [AGENTS.md](../AGENTS.md) makes the repository usable for a coding agent if you work with one.

## The JMS561 family (`152d:0561`)

The JMS561 and JMS561B run firmware with header `0561`, a separate line from the JMS561U images. The builder refuses them: Ugreen's JMS561U code is not meant for that chip.

The idea still carries over. All four 0561 images in the table have the same UNMAP to TRIM translation, switched off in the same way, and three of the four offer UASP. A port to one of them is the same work as above, plus a 0561 board to test on.
