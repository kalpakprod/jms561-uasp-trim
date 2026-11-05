# JMS561 / JMS561U firmware catalog

Every JMS561-family firmware and tool we found, where it comes from and what we know about it. "Checked" means we looked at the bytes ourselves. Nothing here is redistributed by this repository. Follow the links.

## JMS561U (`152d:1561`)

| Firmware | Source | UASP | TRIM | Notes |
|---|---|---|---|---|
| **167.1.0.4** `CM198-v167.001.000.004-20180730-meta.bin`, 262144 bytes, sha256 `57099a24904f87afc5fe8ccd195c554a002eda058ed3e0c111594325243e64e7` | Ugreen's "turn off sleep mode" package `JMS561U Tools for Turning off Sleep Mode.rar` (1648242 bytes, sha256 `b41502a442c57ce375e7a243ec6221dd68b8d058c55b90e0f821ee4071b4b0f2`), mirrored at [xedt/Ugreen_HDD_Case_Turnoff_Sleep_Mode_Tool](https://github.com/xedt/Ugreen_HDD_Case_Turnoff_Sleep_Mode_Tool) | yes, checked on our CM198 | code present, flag cleared (checked), **enabled by this project's patch** | the base of this project. Same package ships `JMMassProd_v1_16_15_7.exe`, password `jmicron` |
| **167.2.0.21** (`v167.002.000.021`, 2020-01-03) | shipped on our CM198; ELEOK thread 123920 as `JMS561U A3-FEIXUAN-_v167.002.000.021_20200103` with JMMassProd 1.16.15.12 | no (BOT only, checked) | code present (builder at `0xA7B4`), flag cleared (checked) | strings "Ugreen Storage Device" |
| 20.3.2.2 and 20.3.2.4 | JMicron's `FwUpdater561U_v1_0_2_0.exe` (embeds two 256 KiB images) per xRetia/JMS56x; also "JMicron JMS56x FW Update Tool v1.0.2.0 [FW20.03.02.04]" on usbdev.ru | UAS alternate setting present (checked) | code present, flag cleared (checked) | JMicron reference builds, a close relative of Ugreen's 2018 code |
| 09.1.2.2 `JMS561U_v09.01.02.02.bin`, .bin sha256 `9c95364c…811f` | liangchanba thread 269 (login needed, and the site prepends a 127-byte tracking header) | UAS alternate setting present (checked) | code present, flag cleared (checked) | header says `0565 JMicron JMS565`; never flashed |
| 105.1.0.9 (`JMS561U_v105.01.00.09_20191105`), 115.1.1.7 | listed on liangchanba thread 269 | ? | ? | not downloaded |
| 1.3.2.4 | Sabrent DS-4SSD, per a Sabrent forum user | ? | user reports no TRIM | that unit may have been a JMS567 |

Every image here, JMS561U and JMS561 alike, has the UNMAP to ATA TRIM translation and clears its TRIM flag (XRAM `0x3FA9 + port`) with `CLR A; MOVX @DPTR,A`. The instructions around that store differ a little between versions. [`tools/jms561_inspect.py`](../tools/jms561_inspect.py) finds both in any image, and [your-enclosure.md](your-enclosure.md#what-the-inspector-finds-in-the-firmware-we-hold) lists the addresses for each firmware here. The patch in this repository is written against 167.1.0.4. For another version the idea carries over, but every address has to be found again.

## JMS561 (`152d:0561`) and JMS561B

| Firmware | Source | UASP | Notes |
|---|---|---|---|
| Hardkernel v158.1.0.1 to v158.1.0.4 | Odroid wiki (CloudShell2 firmware page, Wayback 2023-01), usbdev.ru | 158.1.0.1 to 158.1.0.3: BOT only, 158.1.0.4: "Support USB UAS Mode" | JMicron called the UAS problems "host driver issue", SMART drop-outs "cannot fix"; same serial on both disks "H/W limitations (JMS561 is RAID manager chip)". TRIM code present and flag cleared in 158.1.0.1, which has no UAS alternate setting (checked) |
| JMS561b v8.0.3.7 (2016) | Odroid wiki | no | SMART drop-outs |
| `jms561b_v8.1.3.6.BIN` | usbdev.ru | UAS alternate setting present (checked) | TRIM code present, flag cleared (checked) |
| CE702 v107.1.0.3 (2018), JMS561B v107.1.0.4 (2024-08-30) | usbdev.ru, Station-Drivers "Jmicron JMS-561B Firmware Version 107.01.00.04" | UAS alternate setting present in both (checked) | TRIM code present, flag cleared, with a slightly different instruction sequence (checked) |

## Tools

| Tool | Where | Notes |
|---|---|---|
| JMMassProd 1.16.15.7 | Ugreen package above | writes copy 1 over USB. "RD Version" password `jmicron` (some posts say `jmicro`) |
| JMMassProd2 1.16.14.34 | Odroid (`dn.odroid.com/cs2/`) | Windows. Load only the F/W file, no INI, or it errors out (Radxa forum) |
| JMS561FwUpdate | Odroid | ARM Linux only. `-b` saves a backup first |
| FwUpdater561U 1.0.2.0 | xRetia/JMS56x | JMicron's JMS561U updater |
| JMicron tools in a VM | | reported to semi-brick a JMS567 (r/DataHoarder). On our side, JMMassProd in a QEMU WinPE VM with USB passthrough read the version fine; we didn't write with it |

## Neighbours with working TRIM

- JMS578: passes UNMAP to TRIM (raspberrypi/linux #3070). Hardkernel v173.1.0.1/2 has it, and [BertoldVdb/jms578flash](https://github.com/BertoldVdb/jms578flash) loads its code at CPU `0x4000`. The Hardkernel image builds the same DSM fields (`06`, `01`, `01`) we found in the JMS561U.
- JMS567: the DS500U3 v3 image sets its TRIM flag from an NVS bit and IDENTIFY word 169, which is the design our patch copies.
- Ugreen's own newer enclosures on ASMedia bridges (ASM225CM, ASM1153E) have UASP from the factory.
