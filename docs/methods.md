# How we took the firmware apart

Notes for anyone doing the same on another JMicron bridge. Nothing here needs the hardware except the last step.

## Get the code window out

The bridge's 8051 code is window2 of each bank: file offset `B + 0x10000`, 64 KiB, CPU address = offset − B − `0x10000`. Window1 (`B+0x1000..0xFFFF`) is mostly high-entropy data we never decoded and never needed.

```sh
dd if=image.bin of=w2.bin bs=65536 skip=1 count=1     # copy 0
```

## Disassemble and decompile

- **rizin** gives correct relative jumps for MCS-51: [`tools/jms561-listing`](../tools/jms561-listing) `image.bin 0 0x2527:0x252c` prints any CPU range of a bank.
- **Ghidra** has an 8051 decompiler (IDA has the disassembler but no 8051 decompiler). Import the raw window with processor `8051:BE:16:default`. A raw image without an entry point gives zero functions, so [`tools/ghidra/Vectors8051.java`](../tools/ghidra/Vectors8051.java) starts analysis from the reset and interrupt vectors. [`tools/jms561-ghidra-decompile`](../tools/jms561-ghidra-decompile) wraps the headless run and decompiles the functions at the addresses you give. It needs JDK 21, and a Ghidra project path without a component starting with a dot.
- The firmware is Keil C51 output. `switch8` and `switch16` helpers keep their case tables right after the `LCALL` (entries `target_hi, target_lo, case`, ending `00 00, default_hi, default_lo`), and an `inline4` helper reads four bytes after its call site. A naive disassembler decodes those tables as code. Our state machines store continuation addresses as `MOV 0x6C,#hi; MOV 0x6D,#lo` pairs, which a call graph misses, so seed the analysis with them.

## Find the ATA commands

Every ATA command the bridge sends goes through one taskfile in XRAM (`0x342C..0x3437` on the JMS561U): count, command, features, LBA, device. The firmware fills it with `MOV DPTR,#slot; MOV A,#opcode; MOVX @DPTR,A`. Look for slots that receive IDENTIFY (`0xEC`) and list every other opcode written into the same slot. [`tools/jms561_ata_slots.py`](../tools/jms561_ata_slots.py) does exactly that, and on the 2018 firmware it finds DSM `0x06` at `0xCCD9`. Had we run it first, we'd have saved two weeks.

## Follow a SCSI command

Start at the SCSI opcode dispatch (`0x4FD9` in the 2018 code: a switch on the CDB's first byte), pick the opcode (UNMAP `0x42`), and follow its state machine through every continuation until you reach a taskfile write and a status check. Write down each gate on the way, the flags it reads, and who writes those flags.

## Read what Linux wants

Don't guess which bits matter. `drivers/scsi/sd.c` decides on discard in `sd_try_rc16_first`, `read_capacity_16` (LBPME), `sd_read_block_limits` (VPD B0), `sd_read_block_provisioning` (VPD B2) and `sd_discard_mode`. The usb-storage driver sets `try_rc_10_first`, which is why TRIM on this bridge needs UAS.

## Run the patch in a simulator

uCsim (`s51`, built by [`tools/setup-ucsim`](../tools/setup-ucsim)) runs an 8052 with 24 MB of XRAM. The bridge's USB and SATA hardware isn't modelled, so a free run of the firmware just waits for hardware forever. What works is calling one routine from a harness: put `LCALL <routine>; SJMP $` into zero padding (we use `0xF000`), preload the XRAM and SFRs the routine reads, set `pc`, break on the `SJMP` and dump the results. [`tests/test_trim_patch.py`](../tests/test_trim_patch.py) does this for both TRIM stubs, and runs UNMAP stage 2 from `0x2C6A` on real parameter lists to show which descriptors reach the parser and which get CHECK CONDITION. As a negative control, the same test feeds the aliasing LBA to Ugreen's unpatched code and sees it accepted.

## Compare with sibling chips

JMicron reuses code across the JMS56x and JMS57x lines. The JMS567 DS500U3 v3 image and Hardkernel's JMS578 firmware (which has working TRIM) build the same DSM taskfile fields. Seeing the same design in a chip where it's switched on told us the JMS561U path was meant to work, not an abandoned stub. For the JMS578, Hardkernel's release payload at file `0x400` loads at CPU `0x4000` (BertoldVdb/jms578flash), so CPU = file offset + `0x3C00`.

## Check the CRC model on known images

We derived the CRC fields from JMMassProd and checked the model by recomputing all of them on every bank of the 2018 and 2020 releases. The per-release footer constant K was the last piece. A model that reproduces every stored value on untouched images is the only one worth trusting before a write.

## Prove which code runs

Give each copy a different visible marker. The USB product string is read from the running code window, so one changed letter at CPU `0xC255` shows up in `lsusb -v`. Without such a marker you can't tell "my patch doesn't work" from "my patch never ran".

## Then the hardware

Write with the clip, boot cold, run [`tools/jms561_trim_test.py`](../tools/jms561_trim_test.py) on a disk you can lose. The simulator tells you a routine does what you wrote. Only the drive tells you the right blocks got trimmed.
