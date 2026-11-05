# jms561-uasp-trim: UASP and TRIM for the JMicron JMS561U (Ugreen CM198)

[![test](https://github.com/kalpakprod/jms561-uasp-trim/actions/workflows/test.yml/badge.svg)](https://github.com/kalpakprod/jms561-uasp-trim/actions/workflows/test.yml) &nbsp; [中文说明](#中文说明)

Firmware for USB 3.0 two-bay SATA enclosures built on the **JMicron JMS561U** bridge (USB ID `152d:1561`), tested on the **Ugreen CM198** dual-bay docking station. It makes the enclosure use the `uas` driver (UASP) instead of `usb-storage`, and it makes **TRIM / discard work over USB**: `fstrim`, `blkdiscard`, the `discard` mount option and btrfs async discard, per drive, in both bays.

There's no host-side workaround involved, no udev rule, no `provisioning_mode` override and no kernel parameter. The enclosure itself now tells Linux that it supports UNMAP, and it translates UNMAP into ATA TRIM correctly.

## What changed on our enclosure

| | Ugreen 2020 (as shipped) | Ugreen 2018 | This firmware |
|---|---|---|---|
| Linux driver | `usb-storage` (Bulk-Only) | `uas` | `uas`, SuperSpeed 5 Gb/s |
| `provisioning_mode` | `full` | `full` | `unmap` |
| `lsblk -D` DISC-MAX | `0B` | `0B` | `32M` |
| `fstrim` | not supported | not supported | trims, 894.3 GiB on a 960 GB SSD |

The SSD in the enclosure wrote 42.7 MiB/s before its first TRIM and 389 MiB/s right after it (fio, 4 GiB sequential, direct I/O), then held 390 MiB/s over a 40 GiB write. Reads stayed at about 370 to 380 MiB/s.

```
$ lsblk -D -o NAME,MODEL,DISC-GRAN,DISC-MAX,TRAN,ROTA
NAME   MODEL             DISC-GRAN DISC-MAX TRAN ROTA
sda    SSD                    512B      32M usb     0
sdb    CUSU C200 960GB        512B      32M usb     0

$ sudo sg_readcap -l /dev/sdb | grep lbpme
   Logical block provisioning: lbpme=1, lbprz=0
```

An exact-block test passed on both bays at once: a discard of 64 blocks zeroed exactly those 64 and nothing next to them or on the other disk, while the other disk was writing and verifying data ([testing.md](docs/testing.md)).

## How it works

JMicron had already written TRIM for this chip. Ugreen's 2018 firmware **167.1.0.4** contains a complete SCSI UNMAP to ATA DATA SET MANAGEMENT translation, and two things keep it off: a flag that the firmware sets to zero right after it identifies the drive, and a READ CAPACITY(16) reply that never sets LBPME. Every JMS561 and JMS561U firmware we could open, nine in all, has the same translation and clears the same flag.

The patch is 103 bytes in [`patches/trim.rows`](patches/trim.rows):

- the TRIM flag comes from the drive's own IDENTIFY data (word 169 bit 0), so only drives that support TRIM get it and a hard disk stays as before
- READ CAPACITY(16) reports LBPME when the flag is set
- the flag is read by port instead of by LUN, which fixes a single disk in bay 2
- the rotation rate comes from the drive, not from the TRIM flag
- UNMAP descriptors that the vendor parser would mangle (LBA above 2^48, more than 65472 blocks) get CHECK CONDITION instead of trimming the wrong blocks
- the USB product string becomes "JMS56T Series", so `lsusb` shows the patched code is running.

UASP comes with the 2018 firmware itself. Ugreen's 2020 firmware removed it. Every address and byte is explained in [trim.md](docs/trim.md) and [uasp.md](docs/uasp.md).

## Start here: does it fit your enclosure?

Plenty of enclosures use this bridge with different firmware: Ugreen, Acasis, Sabrent, VINIK, unbranded docks. Before you buy a programmer or open anything, find out what your enclosure runs. On Linux, with the stock firmware, you can read the flash over USB without opening the case, and the inspector tells you which path fits:

```sh
git clone https://github.com/kalpakprod/jms561-uasp-trim && cd jms561-uasp-trim
lsusb | grep 152d                          # 152d:1561 is a JMS561U
(cd tools/jms561u-usb && cargo build --release)
sudo tools/jms561u-usb/target/release/jms561u-usb read /dev/sdX 0 0x80000 my-flash.bin
tools/jms561_inspect.py my-flash.bin       # firmware, UASP, TRIM, parameter pages, verdict
```

| Verdict | What it means | What you do |
|---|---|---|
| `ready` | Ugreen CM198 firmware and layout, the tested case | build and flash, below |
| `same-layout` | same flash layout, other firmware: probably another brand's board | build with `--other-board`, an untested experiment with a rollback ready |
| `no-pages` | the per-enclosure settings are not where the CM198 keeps them | stop, keep the read, open an issue |
| `other-family` | a JMS561 / JMS561B (`152d:0561`), a different firmware line | the image doesn't fit. The same TRIM code is in there, switched off: a port is possible |

The inspector never writes, and it hides the serial number, so its output is safe to post. Each verdict, the firmware we've seen so far and how to port the patch to another version: [your-enclosure.md](docs/your-enclosure.md).

## Build and flash (verdict `ready`)

You need a CH347T (or another flashrom-supported) SPI programmer with a SOIC-8 clip, and a Linux machine. The image has to go into a part of the flash that the USB updater can't write, so this can't be done over USB yet ([why](docs/flashing.md#why-not-over-usb)).

```sh
make test                                  # downloads Ugreen's 2018 firmware, runs the checks

# enclosure open, 12 V unplugged, clip on the SPI flash U2
tools/jms561-clip read original            # two identical reads -> backups/clip-*-original/image.bin
tools/jms561u_build.py --backup backups/clip-*-original/image.bin --out trim.bin
tools/jms561-clip write trim.bin <sha256 printed by the builder>

# clip off, SSD in a bay, 12 V on, USB 3 port
sudo tools/jms561-status                   # JMS56T Series, uas, provisioning_mode unmap
```

The builder takes Ugreen's firmware, downloaded from its public mirror and checked by sha256, and adds your enclosure's own parameter pages from your backup. That's why no ready-made image is published: those pages hold each enclosure's USB serial number and settings, and Ugreen's code isn't ours to redistribute. The code part of every build must match the published hash `6855b9b5…04d440c`, and the builder checks that, so a build that prints OK is byte for byte the image we run. Want UASP without TRIM? Add `--uas-only`.

The full procedure, with the boot order that matters and the rollback: [flashing.md](docs/flashing.md).

> **Risk.** A bad image means opening the case and writing your backup back with the programmer. Keep the backup safe, and never erase the chip over USB: that's how we bricked ours ([recovery.md](docs/recovery.md)).

## Status

| | |
|---|---|
| Ugreen CM198, JMS561U `152d:1561`, SSD in each bay | works: UASP, TRIM, exact-block test, in use since 30 October 2026 |
| Hard disk in a bay | should stay on stock behaviour, not tested |
| Other JMS561U enclosures (Acasis EC-7352, VINIK, PiBOX, ...) | not tested: run the inspector, see [your-enclosure.md](docs/your-enclosure.md) and [other-enclosures.md](docs/other-enclosures.md) |
| JMS561 `152d:0561`, JMS561B | different firmware family. The same TRIM code is there, switched off; no port yet |
| Flashing over USB without opening the case | not possible yet |
| Windows, macOS | the firmware is host-independent, but only Linux was tested |
| Clone button, sleep timer | not changed, not tested |

## Documentation

- [Your enclosure: the inspector, each verdict, porting the patch](docs/your-enclosure.md)
- [TRIM: where it was hidden and the patch row by row](docs/trim.md)
- [UASP: why stock firmware runs usb-storage](docs/uasp.md)
- [Flashing with a CH347T and flashrom](docs/flashing.md) and [unbricking](docs/recovery.md)
- [Testing TRIM exactly, and our measurements](docs/testing.md)
- [Hardware](docs/hardware.md), [flash layout and CRCs](docs/firmware-layout.md), [vendor USB commands](docs/vendor-usb-protocol.md)
- [JMS561 / JMS561U firmware catalog](docs/firmware-catalog.md) and [other enclosures](docs/other-enclosures.md)
- [How we reverse engineered it](docs/methods.md) and [what went wrong on the way](docs/lessons.md)
- [FAQ](docs/faq.md), [sources](docs/sources.md)

## What's in the repository

```
patches/trim.rows          the patch: offset, bytes before, bytes after, comment
tools/jms561_inspect.py    reads a flash dump: firmware, UASP, TRIM, pages, which path fits
tools/jms561u_build.py     builds your image from Ugreen's firmware + your backup
tools/fetch-ugreen-2018    downloads and checks Ugreen's 2018 package
tools/jms561-clip          flashrom wrapper: two reads, chunked write, verified read-back
tools/jms561-status        what Linux sees: driver, product string, LBPME, VPD pages
tools/jms561_trim_test.py  exact-block TRIM test on a disk you can lose
tools/jms561_crc_rows.py   checks and recomputes every CRC of a firmware bank
tools/jms561_ata_slots.py  lists the ATA commands a firmware issues
tools/jms561u-usb/         vendor USB commands: chip info, flash read, copy-1 write (Rust)
tools/setup-flashrom       builds flashrom with CH347 and P25D40SH support
tools/setup-ucsim          builds the 8051 simulator the tests use
tests/                     the patch runs in an 8051 simulator; builder, CRC, flashing wrapper
```

Coding agents (Claude Code, Codex and others) can work with this repository directly: [AGENTS.md](AGENTS.md) has the safety rules and the map, and `.agents/skills/` has step-by-step skills for building an image, flashing with the clip and checking the enclosure over USB.

## Reports welcome

If you have a JMS561 or JMS561U enclosure, a report helps more than anything else, whether it worked or not. Even the inspector output alone tells everyone which firmware that enclosure ships with: [open a report](../../issues/new?template=enclosure-report.yml).

## 中文说明

本项目为 JMicron（智微）JMS561U 主控的 USB 3.0 双盘位 SATA 硬盘盒提供开启 UASP 和 TRIM 的固件补丁（USB ID `152d:1561`，测试机型：绿联 Ugreen CM198 双盘位硬盘底座，支持脱机对拷）。刷入后 Linux 使用 `uas` 驱动，`fstrim`、`blkdiscard` 和 `discard` 挂载选项都能正常工作，两个盘位都支持。

JMicron 其实早已在 JMS561U 固件里写好了 SCSI UNMAP 到 ATA TRIM（DATA SET MANAGEMENT）的转换代码，只是固件在识别硬盘之后把 TRIM 开关清零了。绿联 2018 年的固件 167.1.0.4 支持 UASP，2020 年的出厂固件 167.2.0.21 去掉了 UASP，只剩 BOT（`usb-storage`）。补丁基于绿联 2018 固件，共 103 字节：是否开启 TRIM 由硬盘自己的 IDENTIFY 数据（第 169 字第 0 位）决定，所以机械硬盘保持原来的行为。实测一块 SSD 在第一次 TRIM 之前顺序写入 42.7 MiB/s，之后 389 MiB/s。

怎么用：先在 Linux 下通过 USB 读出你的固件（原厂固件下不用拆壳），运行 `tools/jms561_inspect.py`，它会告诉你固件版本、是否支持 UASP、TRIM 在哪里被关闭，以及哪条路线适合你的硬盘盒。写入需要 SPI 编程器（我们用 CH347T、SOIC-8 夹子和 flashrom）。本仓库不分发任何固件：构建脚本从公开镜像下载绿联官方固件并校验 sha256，再加上你自己备份里的参数页（其中有每个硬盘盒自己的 USB 序列号）。刷坏了可以用编程器写回备份来救砖，见 [recovery.md](docs/recovery.md)。JMS561（`152d:0561`）和 JMS561B 是另一条固件线，这里的固件不适用，但它们的固件里也有同样的 TRIM 代码。

关于休眠：绿联 2018 固件来自绿联的"关闭硬盘盒自动休眠"工具包（JMS561U Tools for Turning off Sleep Mode），休眠行为我们没有测试。文档是英文的。

关键词：JMS561 固件、JMS561U 固件、JMS561 最新固件、JMS561 固件下载、JMS561 固件升级、JMS561 主控、JMS561 休眠、JMS561 救砖、JMS561 量产工具 JMMassProd、智微 JMS561U、绿联 CM198 固件、绿联硬盘盒固件、绿联硬盘底座、双盘位硬盘盒 TRIM、USB 硬盘盒 UASP、移动硬盘盒 TRIM、Linux USB SSD TRIM、固态硬盘 TRIM。

## Search terms

JMS561U firmware, JMS561 firmware update, JMS561 UASP, JMS561 TRIM, JMS561 Linux, JMS561 SMART, JMicron firmware update tool Linux, JMMassProd, Ugreen CM198 firmware, Ugreen dual-bay docking station, USB 3.0 dual-bay SATA enclosure TRIM, USB SSD TRIM on Linux, `fstrim: the discard operation is not supported`, `uas` instead of `usb-storage`, unbrick a JMS561, SPI flash CH347T flashrom, Acasis EC-7352, Sabrent EC-UASP, VINIK dock, Radxa SATA HAT, Odroid CloudShell2, WD My Book Duo.

## License and disclaimer

Code under the MIT License, documentation under CC BY 4.0 ([LICENSE](LICENSE)). This project is not affiliated with JMicron or Ugreen. It doesn't include or redistribute their firmware or tools: the builder downloads Ugreen's package from its public mirror. You flash at your own risk.
