# Sources

Everything we read and used. Claims from these pages are attributed where we use them. Where we checked a claim on our own hardware or bytes, the other docs say so.

## Firmware, tools and code

- xedt, Ugreen_HDD_Case_Turnoff_Sleep_Mode_Tool: mirror of Ugreen's package with firmware 167.1.0.4 and JMMassProd 1.16.15.7. https://github.com/xedt/Ugreen_HDD_Case_Turnoff_Sleep_Mode_Tool
- Ugreen's original download page `lulian.cn/download/48-cn.html` (now 403), and the Wayback Machine copy of 2021-08-31 of `硬盘盒关闭自动休眠升级工具.rar` (20332542 bytes, sha256 `ba8cf3c9e46d70363d6dca5c942de582a0c3a5123ea7be2814e846245f7fe7a9`), which contains the same JMS561U files.
- projectgus, jms567ctl: the `DF`/`E0`/`FF` vendor protocol, mask ROM after erase, NVS and the UAS alternate setting. https://github.com/projectgus/jms567ctl (and issue #4 on /CS recovery)
- xRetia, JMS56x: JMS565 analysis, firmware archive, dual-bank release files, FwUpdater561U. https://github.com/xRetia/JMS56x
- BertoldVdb, jms578flash: JMS578 image format and load address. https://github.com/BertoldVdb/jms578flash
- hferreira23, JMS578: Hardkernel JMS578 firmware with TRIM. https://github.com/hferreira23/JMS578
- derexiaon, adata-hd710pro-trim-uas: TRIM and UAS on a JMS578 enclosure. https://github.com/derexiaon/adata-hd710pro-trim-uas
- flashrom (CH347 programmer, P25D40SH entry). https://github.com/flashrom/flashrom
- uCsim. https://github.com/danieldrotos/ucsim
- Linux `drivers/scsi/sd.c`, `drivers/usb/storage/`. hdparm 9.65 `sgio.c`.

## Datasheets

- JMicron JMS561U product brief. https://www.jmicron.com/file/download/1070/JMS561U.pdf
- PUYA P25Q40H datasheet (P25D40SH family).

## Write-ups and forum threads

- integer13, "Fix: Alxum USB adapter provides no SMART info. How to break the firmware, recover it and make it better than before" (JMS561U, /CS to GND recovery, empty-flash behaviour). https://integer13.wordpress.com/2026/01/27/fix-alxum-usb-adapter-provides-no-smart-info-how-to-break-the-firmware-recover-it-and-make-it-better-than-before
- Odroid wiki, CloudShell2 firmware upgrade (JMS561 firmware table, JMS561FwUpdate). https://web.archive.org/web/20230130184845/https://wiki.odroid.com/accessory/add-on_boards/xu4_cloudshell2/firmware_upgrade
- Odroid forum, UAS resets on JMS561. https://forum.odroid.com/viewtopic.php?t=29472 . Sabrent EC-UASP on JMS561U without TRIM. https://forum.odroid.com/viewtopic.php?p=304941
- Radxa forum, "How to upgrade F/W with jms561 under Windows". https://forum.radxa.com/t/how-to-upgrade-f-w-with-jms561-under-windows/4437 and "JMS561 Firmware Upgrade?". https://forum.radxa.com/t/jms561-firmware-upgrade/9926
- Raspberry Pi forum, VINIK dock on JMS561U. https://forums.raspberrypi.com/viewtopic.php?t=266542
- Sabrent community, EC-UASP / DS-4SSD on JMS561U. https://sabrent.com/community/xenforum/topic/85232/ec-uasp-more-information
- 4PDA, enclosures thread 510629, posts 601 (CM198 = JMS561U = Acasis EC-7352), 614-615 (brick and SPI recovery). https://4pda.to/forum/index.php?showtopic=510629&st=600
- ELEOK thread 123920, flashing 167.2.0.21 with JMMassProd 1.16.15.12. https://www.eleok.com/forum.php?mod=viewthread&action=printable&tid=123920
- right.com.cn thread 8481240, CM198 standby timer via MP Tool.
- usbdev.ru, JMS561 firmware files and topic 9895. https://www.usbdev.ru/files/jmicron/jms561firmware and https://www.usbdev.ru/f/index.php?topic=9895.0
- Station-Drivers, JMicron JMS-561B firmware 107.01.00.04.
- liangchanba thread 269, list of JMS561U firmware versions. https://club.liangchanba.com/thread-269-1-1.html
- r/DataHoarder, "Which are proper external enclosure chipsets?" (JMS567 UAS firmwares, VM semi-brick). https://www.reddit.com/r/DataHoarder/comments/jcloqv/which_are_proper_external_enclosure_chipsets/
- r/linux, pass-through on a two-bay JMicron `152d:2352` going to port 0.
- raspberrypi/linux #3070, TRIM on JMS578 and other bridges. https://github.com/raspberrypi/linux/issues/3070
- smartmontools #656 (JMS561 RAID `152d:a561`) and #216 (Acasis EC-7352). https://github.com/smartmontools/smartmontools/issues/656
- andlabs/reallymine and themaddoctor/linux-mybook-tools (WD My Book Duo on JMS561).
