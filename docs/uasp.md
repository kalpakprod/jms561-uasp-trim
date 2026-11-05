# UASP on the JMS561U: why your enclosure runs usb-storage and how to get uas

If `lsusb -t` shows `Driver=usb-storage` for your JMS561U (`152d:1561`), the enclosure is talking the old Bulk-Only Transport. That's what Ugreen's current firmware does. You can't fix it from the host: a BOT-only firmware doesn't offer the UAS interface at all, so there's nothing for the `uas` driver to bind to.

The fix is firmware that offers it. Ugreen's own 2018 firmware for the CM198 does. Their 2020 firmware dropped it.

## The two Ugreen firmwares

| | 2020, as shipped on our enclosure | 2018 |
|---|---|---|
| Version (chip info, header) | 167.2.0.21 (`v167.002.000.021`, 2020-01-03) | 167.1.0.4 (`CM198-v167.001.000.004-20180730`) |
| `bcdDevice` | 0.15 | 0.04 |
| USB strings | "Ugreen Storage Device" | "JMicron" / "JMS56x Series" |
| Interfaces | alt 0 BOT only, configuration `wTotalLength 0x2c` | alt 0 BOT + alt 1 UAS (protocol `0x62`), `wTotalLength 0x79` |
| Linux driver | usb-storage | uas |
| Where to get it | it's what ships | Ugreen's "turn off sleep mode" package, see [firmware-catalog.md](firmware-catalog.md) |

Both run on the same bridge with the same parameter pages. We flashed 167.1.0.4 onto our CM198 on 15 October 2026 and it came up with UASP at SuperSpeed (5 Gb/s), with `Driver=uas`, SMART pass-through working, write cache and DPO/FUA reported, and no `uas` errors in the kernel log.

## What 2020 removed

We compared the two code windows function by function (IDA and Ghidra, plus our own matcher). The UAS path is gone from 2020, not just hidden:

| 2018 | Role | 2020 |
|---|---|---|
| `0xBF89` SET_INTERFACE | selects alt 1 when XRAM `0x4C77` bit 4 is 0: `0x3410` = 1, R7 = 2 | `0xAB3F` handles alt 0 only |
| `0xA5C3` | mode switch, `0x346F` holds the current mode (1 BOT, 2 UAS) | `0x9572` (similarity 0.8), no UAS branch |
| `0x0026` | `SETB 21.7; LJMP 0x77DD`: enter UAS mode | different code at `0x0026` |
| `0x001E` | R7 = 1, `LJMP 0xB4B7`: leave UAS mode | missing |
| `0x77DD` (182 bytes) | hardware setup for UAS: `0x7803`, `0x5064`, `0x5056`, `0x781B`, `0x704A`, `0x7800/1`, `0x701E/F`, `0x5087` | missing (best match 0.27) |
| `0xC365` | SCSI opcode decoding for UAS (`0x35DF`: 08/0A/28/2A/88/8A) | missing |

Bit `RAM 0x21.7` means "UAS on". The 2018 code tests it at 24 places, 2020 tests it at 14 and never sets it. The SuperSpeed configuration descriptor of 2018 is 121 bytes with the UAS alternate setting; 2020's is 44 bytes.

## The parameter pages matter

The flash holds more than the code. The last 256 KiB (`0x40000..0x7FFFF`) carry the enclosure's own parameter pages: `IVP0` at `0x41000`, `IPP0` at `0x44000` (it contains the USB IDs `152d:1561`), `IUP0` at `0x45000` and `WDq1` at `0x46000`. Byte `0x46008` is a "UAS disabled" flag; ours is `00`.

These pages are per enclosure (they also hold its USB serial number), and the 2018 firmware needs them to offer UASP. The same was reported for the sibling JMS567, where an erased NVS region makes the UASP alternate setting disappear (projectgus/jms567ctl). On our enclosure, an image with a valid copy of the code but erased parameter pages didn't boot at all ([lessons.md](lessons.md)). So:

- keep your own pages: [`tools/jms561u_build.py`](../tools/jms561u_build.py) copies them from your backup byte for byte and refuses a backup that doesn't have them
- don't flash a full 512 KiB image taken from someone else's enclosure.

## How to get UASP

- **UASP only**: build Ugreen's 2018 code with your own parameter pages and flash it with an SPI programmer:

  ```sh
  tools/fetch-ugreen-2018
  tools/jms561u_build.py --backup backups/clip-*-original/image.bin --out uas.bin --uas-only
  ```

  The code part of the result is Ugreen's file unchanged (sha256 `57099a24…3e64e7`).
- **UASP + TRIM**: the same command without `--uas-only`. TRIM needs UASP anyway ([trim.md](trim.md)).

Full procedure: [flashing.md](flashing.md).

## Porting UAS into the 2020 firmware: tried and dropped

Before we knew the 2018 firmware ran on this enclosure, we tried to graft the 2018 UAS path into the 2020 code. Candidate B moved 14,122 bytes of 2018 code into the free space `0xBC00..0xF329` of 2020 and added 19 entry hooks. It booted, but in BOT mode only: the gate `0x4C77.4` still picked the disabled path, and it showed the strings of the other copy, which later turned out to mean its patched copy never ran (its code CRC was stale). A second version, B2, was built but never flashed. Once 167.1.0.4 gave UASP with no changes at all, the port had nothing left to offer, so we stopped.

## Is UASP on JMS561 stable?

Reports from other JMS561 boards are mixed: Odroid CloudShell2 users saw `uas_eh_abort_handler` storms on Hardkernel's UAS firmware v158.1.0.4, and a Radxa engineer tested four JMS561 firmwares and called none of them stable. Those are different boards and firmwares. On our CM198 with 167.1.0.4 and later the TRIM image, two SATA SSDs have run under `uas` with sustained 390 MiB/s writes, concurrent `fstrim` on both disks and a clean kernel log ([testing.md](testing.md)). If you see resets, the usual fallback is the `usb-storage.quirks=152d:1561:u` kernel parameter, which forces BOT, and you'll lose TRIM with it.
