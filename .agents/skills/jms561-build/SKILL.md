---
name: jms561-build
description: Inspect, build, change or check a JMS561U firmware image. Use on any flash read or firmware file, to build the UASP or UASP+TRIM image from an owner's backup, to add or change patch rows, or to port the patch to another firmware version.
---

# Build or change a JMS561U image

Read `docs/firmware-layout.md` before the first edit: addresses, CRC fields and the boot rule are there.

## Inspect first

`tools/jms561_inspect.py <read>` (`--json` for you) on every flash read or firmware file before anything else. Its verdict decides the path, and `docs/your-enclosure.md` explains each one. Only `ready` is the tested path. `same-layout` builds with `--other-board` only after the owner agrees to an experiment on an untested board. `no-pages`, `other-family` and `unreadable` stop here: report the output to the owner.

## Build for an owner

1. `tools/fetch-ugreen-2018` prints `OK 57099a24…`.
2. `tools/jms561u_build.py --backup <owner's original clip read> --out <name>.bin` (add `--uas-only` for UASP without TRIM).
3. Done when it prints `OK <sha256>` and the code line says it matches the published hash. Give the owner that sha256: the write skill needs it.

The builder refuses a backup without the four parameter pages. That backup is the wrong file, or the board differs from the CM198: stop and tell the owner.

## Change the patch

1. Find the code with rizin (`tools/jms561-listing <img> 0 <start>:<end>`) and Ghidra (`tools/jms561-ghidra-decompile`). CPU address = file offset − `0x10000` in copy 0. Keil switch tables after an `LCALL` and the four bytes after the `0x5DD4` helper are data.
2. Prove the change before building: a trace from the SCSI command entry (UAS and BOT) to the instruction that writes each byte you change, and a uCsim run of any new routine from a harness (see `tests/test_trim_patch.py`). For UNMAP, test the inputs the code must refuse as well as those it must accept: a wrong LBA destroys data outside the range.
3. Edit `patches/trim.rows` (`<offset> <before> <after>  # why`). New code goes into the zero padding after `0xE363`.
4. Update `CODE_SHA["trim"]` in `tools/jms561u_build.py` and the published hash in `README.md` and `docs/flashing.md`.
5. A patched copy needs a visible marker in the product string at `0x1C255`, so the owner can see it runs.

Done when `make test` is green, `tools/jms561_crc_rows.py check <image>` prints `RESULT OK`, and `docs/trim.md` explains every new row.

## Port to another firmware version

`tools/jms561_inspect.py` gives the TRIM flag clear, every read of the flag (by LUN or by port), the DSM taskfile builder and the free space in the new code. From there find the READ CAPACITY(16) reply, the VPD B0/B1/B2 gates and the UNMAP stage-2 exit, then follow "Change the patch" with a new `patches/trim-<firmware>.rows`. `docs/your-enclosure.md`, "Porting the patch", lists the six parts. A port is done when its stubs pass uCsim tests like `tests/test_trim_patch.py`; it works only after a hardware report.
