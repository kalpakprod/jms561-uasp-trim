# TRIM on the JMS561U: where it was hidden and how the patch turns it on

JMicron had already written TRIM support for this bridge. Ugreen's 2018 firmware 167.1.0.4 contains a complete translation from SCSI UNMAP to ATA DATA SET MANAGEMENT (the ATA TRIM command), and the code is switched off in two places. The patch in [`patches/trim.rows`](../patches/trim.rows) switches it back on, makes it depend on whether the drive in each bay actually supports TRIM, and adds the input checks the vendor code lacked. It's 103 changed bytes plus recomputed checksums.

Addresses below are 8051 CPU addresses in copy 0 of the 2018 firmware. The file offset is CPU address + `0x10000` (see [firmware-layout.md](firmware-layout.md)).

## What Linux needs before it sends TRIM over USB

A USB disk gets discard (`fstrim`, `discard` mount option, `blkdiscard`) only if the bridge tells the SCSI layer that it supports logical block provisioning. The checks are in `drivers/scsi/sd.c`:

| Step | Linux condition | Stock answer (2018 and 2020) |
|---|---|---|
| READ CAPACITY(16) is sent at all | `sd_try_rc16_first()`: SCSI level above SPC-2. usb-storage (BOT) sets `try_rc_10_first`, so over BOT a disk under 2 TB never gets RC16 | UAS: sent. BOT: not sent |
| LBPME bit | `read_capacity_16()`: byte 14 bit 7 of the reply | 0 |
| VPD pages read | `scsi_device_supports_vpd()`, the bridge lists B0, B1, B2 | listed |
| LBPU (VPD B2) | byte 5 bit 7 | 0 |
| Max unmap (VPD B0) | page length at least 64, nonzero max unmap LBA count and descriptor count | 0 and 0 |
| Result | `sd_discard_mode()` picks UNMAP | `provisioning_mode = full`, `DISC-MAX 0B` |

Two practical consequences:

- **TRIM needs UASP on this bridge.** Over the Bulk-Only Transport (usb-storage) Linux never asks READ CAPACITY(16) for a disk under 2 TB, so it never sees LBPME. Stock Ugreen 2020 firmware is BOT only, so the first step for any TRIM work is the 2018 firmware, which has UASP ([uasp.md](uasp.md)).
- **A udev rule that writes `unmap` into `provisioning_mode` is not a fix.** With the stock firmware the bridge answers SCSI UNMAP (`0x42`) with "invalid command operation code", so the kernel's discards fail. ATA pass-through of DSM doesn't help either: `hdparm --trim-sector-ranges` uses ATA protocol 6 (DMA), and the bridge's pass-through handler refuses protocol 6 ("Invalid exchange").

## The vendor's UNMAP path in the 2018 firmware

```
SCSI opcode table 0x4FD9:  0x42 (UNMAP) -> gate 0x505B
gate 0x505B:   XRAM[0x3FA9 + port] != 0, else "invalid opcode"
0x2BF2         UNMAP state machine, stage counter XRAM 0x3508
  stage 2  0x2C6A  check the parameter list header
  stage 3  0x2CB4  parse the first block descriptor at 0x3A08
                   (big-endian LBA -> 0x355E.. little-endian 48-bit, count -> 0x3558..)
  stage 4  0x2D9C  LCALL 0x5246: build 8-byte ATA DSM range entries at XRAM 0x3600
                   XRAM 0x3513 = port, continuation 0xCCD6
  0xCCD6           LCALL 0xE18B          ; clear the taskfile
                   0x342E = 0x06         ; command DATA SET MANAGEMENT
                   0x342F = 0x01         ; features bit 0 = TRIM
                   0x342C = 0x01         ; count = one 512-byte block of ranges
                   0x3433 = 0x40         ; device: LBA mode
                   continuation 0xB3AE   ; 512-byte data-out phase from 0x3600
  stage 5  0x2DBB  ATA status: (0x343A & 0xE1) == 0x40 -> GOOD,
                   else sense data from the error register 0x3439
```

The ATA taskfile at XRAM `0x342C..0x3437` is the same one the firmware uses for IDENTIFY (`0xEC`), SMART (`0xB0`), SET FEATURES, standby, flush and for ATA pass-through. [`tools/jms561_ata_slots.py`](../tools/jms561_ata_slots.py) lists every ATA opcode the firmware writes into it and finds DSM `0x06` at `0xCCD9`. Stock 2020 has the same builder at `0xA7B4`, so the code survived there too.

The sibling JMS567 firmware (DS500U3 v3) shows how JMicron meant the gate to work: at `0x420C` it sets its TRIM flag only when an NVS setting bit and IDENTIFY word 169 bit 0 are both set, and its UNMAP handler builds the same taskfile (`+0=1`, `+2=0x06`, `+3=1`, `+7=0x40`).

## What switches it off

1. Right after IDENTIFY, the function at `0x2519` stores zero into the gate flag: `0x2527: CLR A; MOVX @DPTR,A` with DPTR = `0x3FA9 + port`. Nothing else ever sets it.
2. The READ CAPACITY(16) handler (`0x4D59`) never sets LBPME (reply byte 14, XRAM `0x3A0E`).

VPD B0 (max unmap), B2 (LBPU) and B1 (rotation) are already gated by the same flag, so they come alive once the flag is set.

## The patch, row by row

Every row in [`patches/trim.rows`](../patches/trim.rows) gives the file offset, the bytes that must be there before and the bytes after. The builder refuses to apply a row whose "before" bytes don't match. The new code lives in zero padding after the last vendor code byte (`0xE30C`).

### 1. Set the flag from the drive's own IDENTIFY data

(`0x2527`, stub at `0xE310`). The `CLR A; MOVX @DPTR,A; MOV DPTR,#0x37B3` sequence becomes `LCALL 0xE310; NOP; NOP`. The stub saves DPTR (the flag address), reads IDENTIFY word 169 low byte (XRAM `0x3752`; the IDENTIFY buffer starts at `0x3600`), keeps bit 0 ("DATA SET MANAGEMENT TRIM supported"), stores it into the flag, re-creates `MOV DPTR,#0x37B3` and returns. So a drive without TRIM support keeps the stock behaviour, and an HDD is never offered UNMAP.

```
E310  C0 82        PUSH DPL
E312  C0 83        PUSH DPH
E314  90 37 52     MOV DPTR,#0x3752     ; IDENTIFY word 169, low byte
E317  E0           MOVX A,@DPTR
E318  54 01        ANL A,#0x01          ; DSM TRIM supported
E31A  D0 83        POP DPH
E31C  D0 82        POP DPL
E31E  F0           MOVX @DPTR,A         ; flag for this port
E31F  90 37 B3     MOV DPTR,#0x37B3     ; what the overwritten code did
E322  22           RET
```

### 2. Report LBPME in READ CAPACITY(16)

(`0x4E53`, stub at `0xE323`). The original `CLR A; MOV DPTR,#0x3A0B; MOVX @DPTR,A` becomes a call. The stub does the original store, then sets reply byte 14 to `0x80` only if the flag of this command's port is set, and returns with A = 0 as the original code did.

### 3. Read the flag by port, not by LUN

(`0x177B`, `0x182C`, `0x505E`: `40` → `43`). The vendor writes the flag indexed by port (XRAM `0x3513`, mirrored in RAM `0x43`) but reads it indexed by LUN (RAM `0x40`) in VPD B0, VPD B2 and the UNMAP gate. With both bays filled LUN equals port. With a single disk in bay 2 the vendor indexing reads the wrong slot. RC16 and the UNMAP issue stage already use RAM `0x43`, and both the BOT and UAS command paths set it from `IRAM[0x4A + LUN]`.

### 4. Rotation rate from the drive, not from the TRIM flag

(`0x17B5`). The vendor reports "non-rotating medium" in VPD B1 whenever the TRIM flag is set. The patch makes VPD B1 read the vendor's own word-217 table `XRAM[0x4B53 + port]` (1 when IDENTIFY word 217 = 1, "non-rotating"), so a TRIM-capable SMR hard disk is still reported as rotating.

### 5. A marker that shows the patched copy runs

(`0x1C255`: `x` → `T`). The USB product string becomes "JMS56T Series" instead of "JMS56x Series". The bridge reads this string from the code window it executes, so `lsusb` tells you which copy runs ([firmware-layout.md](firmware-layout.md), "Boot").

### 6. Refuse UNMAP descriptors the vendor parser would mangle

(`0x2CB1`, stub at `0xE33E`). Stage 2 checks only the parameter list header and then jumps to `0x2DAD`. The vendor parser keeps only LBA bytes 7..2, so bits 63..48 are dropped and a high LBA aliases onto a low one. Counts of 65536 and more go into a splitting loop in `0x5246` that nothing else exercises. The patch routes the accept exit through a check: LBA bytes 0..1 must be zero and the block count must be at most `0xFFC0` (65472, the limit the bridge advertises in VPD B0). Anything else takes the vendor's own error exit `0x2CAC` (`MOV R7,#6; LJMP 0xCFDC`), which returns CHECK CONDITION, ILLEGAL REQUEST, invalid field in parameter list.

```
E33E  90 3A 08     MOV DPTR,#0x3A08     ; descriptor LBA, big-endian
E341  E0 70 1D     MOVX A,@DPTR / JNZ bad
E344  A3 E0 70 19  INC DPTR / MOVX / JNZ bad     ; LBA bits 63..48 must be 0
E348  90 3A 10     MOV DPTR,#0x3A10     ; block count, big-endian
E34B  E0 70 13     MOVX / JNZ bad
E34E  A3 E0 70 0F  INC DPTR / MOVX / JNZ bad     ; count < 65536
E352  A3 E0        INC DPTR / MOVX
E354  B4 FF 07     CJNE A,#0xFF,ok               ; high byte below 0xFF: fine
E357  A3 E0        INC DPTR / MOVX
E359  D3           SETB C
E35A  94 C0        SUBB A,#0xC0                   ; low byte must be <= 0xC0
E35C  50 03        JNC bad
E35E  02 2D AD     ok:  LJMP 0x2DAD
E361  02 2C AC     bad: LJMP 0x2CAC
```

An LBA inside 48 bits but past the end of the drive is left to the drive: ACS-4 says the drive aborts a DSM range outside its capacity, and stage 5 turns the abort into CHECK CONDITION. Our test drive did exactly that ([testing.md](testing.md)).

After the rows, the builder recomputes every CRC of copy 0, including the code CRC at `+0x1FFF8`. That last one matters more than it looks: three of our early attempts left it stale and the bridge silently ran the unpatched copy ([lessons.md](lessons.md)).

## What Linux sees with the patched firmware

From `sg_readcap -l`, `sg_vpd` and sysfs on our enclosure, with a SATA SSD in each bay:

```
Logical block provisioning: lbpme=1, lbprz=0
Maximum unmap LBA count: 0xffc0
Maximum unmap block descriptor count: 0x1
LBPU=1
Non-rotating medium (e.g. solid state)
provisioning_mode unmap   discard_max_bytes 33521664   discard_granularity 512   rotational 0
```

`33521664` bytes is 65472 blocks of 512 bytes, the advertised maximum. Linux turns on discard by itself: `lsblk -D` shows `DISC-MAX 32M`, `fstrim` works, and btrfs even enabled asynchronous discard on its own. No udev rule, no kernel parameter.

## What the patch doesn't change

- The UNMAP state machine handles one descriptor per command (the bridge advertises a descriptor count of 1, and Linux sends one).
- `LBPRZ` stays 0: the bridge doesn't promise zeros after TRIM. Our SSD returned zeros anyway.
- ATA pass-through is untouched. On a two-bay JMicron bridge (`152d:2352`) someone found pass-through going to port 0 whatever LUN it was sent to. Our path sets the port from the LUN only for protocol 3, the others weren't traced, so treat `hdparm`/`smartctl` writes to the second bay with care.
- An HDD in a bay should keep the stock behaviour (word 169 bit 0 is 0, so no flag). We haven't tested it with a real HDD yet.
