# What went wrong, and the rule each mistake left behind

The working image took two weeks and more than a dozen test images. Most of that time went into mistakes that are easy to repeat on any JMicron bridge, so here they are, in the order they happened.

## The dead ends

### The UAS port into the 2020 firmware (15 October)

We grafted 14 KB of the 2018 UAS code into the stock 2020 firmware. It booted in BOT mode only. Later it turned out the patched copy probably never ran (stale code CRC, below). Then Ugreen's own 2018 firmware simply booted with UASP and made the port pointless. Rule: before porting a feature, check whether an older official release already has it.

### Four USB uploads that changed nothing (15 October)

Candidates C, E, E2 and M2 went in over USB and were "verified" by reading them back. After each power cycle the bridge behaved exactly as before. Two things fooled us. The bridge writes USB uploads into copy 1 and keeps running copy 0. And READ BUFFER, which we used to "see the running code", returns flash, not RAM. Rule: before the first write of a new kind, reverse the vendor tool's whole update sequence, and have a marker that proves which code runs. Written and verified is not the same as running.

### The USB chip erase (16 October)

`DF 03 FB` erased all 512 KiB: both copies and the parameter pages. Then a valid image went into copy 1 over USB, and the enclosure never came back on USB. The backup taken before the erase had been overwritten by a later read with the same file name. The clip saved it. Rules: never erase or write copy 0 or the parameter pages over USB, and give every backup a unique timestamped name and make it read-only at once.

### Three TRIM images that never ran (15 and 16 October)

C, E and F1 recomputed the footer and header CRCs but not the code CRC at `+0x1FFF8`: our first CRC tool didn't touch that field. The most likely result: the boot loader skipped the patched copy and ran the untouched one, so three rounds of hardware tests measured stock code. We even concluded, wrongly, that the code answering SCSI commands must be hidden in the encrypted part of the image. F3, built with every CRC recomputed, worked on the first try. Rule: check every CRC field of every bank before writing (`jms561_crc_rows.py check` must print `RESULT OK`).

### Two weeks hunting a missing "engine command" (17 to 30 October)

We read a block of registers at XRAM `0x70B0` as a SATA command mailbox, saw command `01` go into it during UNMAP, and decided the firmware was missing the real TRIM command. Nine reviewers looked at our rewrite of that path and rejected it. Actually `0x70B0` is an arithmetic unit (`01` means subtract), and the ATA DSM command goes out through the ordinary taskfile in the very next state of the UNMAP state machine. We found it by listing every opcode the firmware writes into the IDENTIFY command byte. Rule: follow a command path to the byte that holds the ATA opcode before you conclude that something is missing. `tools/jms561_ata_slots.py` does this listing.

### Trusting the vendor's parser (30 October)

The first F3 round turned TRIM on and checked the byte order of the LBA, but not what the parser refuses. An outside review found that it drops LBA bits 63..48, so an UNMAP for a huge LBA would trim a low one, and that it accepts any count. Round 2 added the guard. Rule: for a destructive command, test the inputs it must refuse, not only the ones it must accept.

## Bench mistakes

- **Boot tests without a cold power cycle.** Images were declared dead after a USB replug with 12 V still on and no disk in. The bridge reloads firmware only at power-up and enumerates only with a disk. Order: 12 V off, clip off, disk in, 12 V on, USB into a USB 3 port directly.
- **A USB 2 hub.** The F1 "hang" was the hub it was plugged into, shared with the programmer. Same direct USB 3 port every time, programmer on a different port.
- **A USB reset pulled the other disk.** Toggling the device's `authorized` flag knocked out a mounted filesystem in the other bay four times. Unmount every disk of the enclosure before any reset, power cycle or write.
- **A broken listing handed to reviewers.** Our disassembly script ignored its base address argument, and nine reviewers read data as code. Spot-check every listing on one known byte before you hand it out.
- **A test fake that was too kind.** Our clip script passed a 16 KiB file to `flashrom -w`, which only accepts a whole-chip image. The test used a fake flashrom without that rule, so it passed. The script would have stopped before erasing anything, but it would never have worked. The fake in `tests/fixtures/fake_flashrom.py` now enforces the rule. A fake has to model the real tool's argument checks.
- **A test that couldn't decide anything.** One planned boot test had valid CRCs in both copies. With both valid, the bridge runs copy 0 in every theory, so the outcome couldn't tell the theories apart. Before you run a test, write down what each outcome means under each hypothesis.
- **A copy of a vendor tool reported as the vendor tool.** Find the vendor's own page (live or on the Wayback Machine) and compare the sha256 with the mirror.
