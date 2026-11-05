# Other enclosures with the JMS561 or JMS561U

This project was built and tested on one Ugreen CM198. These products are reported to use the same family of bridges. None of them has been tested with this firmware, and for most of them nobody has published which firmware they ship. If you own one, a report helps everyone: [report form](../../../issues/new?template=enclosure-report.yml).

| Product | Bridge | What's reported |
|---|---|---|
| Ugreen CM198 (two-bay dock, offline clone) | JMS561U `152d:1561` | this project: UASP + TRIM work |
| Acasis EC-7352 | JMS561U | "same controller as the Ugreen CM198" (4PDA, enclosures thread, post 601) |
| Acasis EC-7252 | JMS561 | in RAID1 it shows `152d:a561` and hides the member disks (smartmontools #656) |
| VINIK two-bay dock | JMS561U `152d:1561` | "barely works under Linux, drops out under load", and the owner found no firmware for 1561 (Raspberry Pi forum t=266542) |
| PiBOX | JMS561U `152d:1561` | owner asked on the Radxa forum whether the JMS561 guide applies |
| Sabrent EC-UASP, DS-4SSD | JMS561U reported, possibly JMS567 | "The JMS561U chipset DOES NOT support TRIM" (Odroid forum), but Sabrent support said none shipped with the JMS561U |
| Radxa Quad/Penta SATA HAT | JMS561 (several) | MP Tool guide. A Radxa engineer tested four firmwares and found none stable |
| Odroid CloudShell2 | JMS561 | Hardkernel firmware v158, UAS from 158.1.0.4 |
| WD My Book Duo | JMS561 | users revived broken units with Radxa/Odroid firmware |
| Alxum USB adapter | JMS561U with a BY25D16 flash | integer13's break-and-recover write-up |

## Before you try anything on another enclosure

Read your flash and run `tools/jms561_inspect.py` on it. [your-enclosure.md](your-enclosure.md) walks through it: reading over USB without opening the case, what each verdict means, and how to port the patch to another firmware.

One thing the inspector can't see is the flash chip itself. Ours is a 512 KiB PUYA P25D40SH. A different chip needs `CHIP=` for `jms561-clip`, and a different size probably means a different layout.
