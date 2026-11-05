# JMS561U flash layout, checksums and boot

Everything here was checked on the 512 KiB flash of our Ugreen CM198 and on Ugreen's 2018 and 2020 releases. Statements we couldn't test directly are marked as such.

## Flash map

```
0x00000-0x1FFFF  copy 0, a 128 KiB bank
0x20000-0x3FFFF  copy 1, a second bank (same window2 code in Ugreen's images; window1 and config
                 differ, Ugreen's package calls it the COPIER clone-mode image)
0x40000-0x7FFFF  parameter pages, specific to each enclosure:
                 IVP0 0x41000, IPP0 0x44000 (USB IDs 152d:1561), IUP0 0x45000,
                 WDq1 0x46000 (byte 0x46008 = "UAS disabled", 00 on ours)
```

Ugreen's release file `CM198-v167.001.000.004-20180730-meta.bin` is 256 KiB: both copies, no parameter pages. It matches the first 256 KiB of the 2018 image that booted on our enclosure byte for byte. The xRetia/JMS56x notes describe JMS561/561B 256 KiB release files the same way, as dual-bank mirrors at `0x0` and `0x20000`.

## Inside a bank

With B = `0x00000` or `0x20000`:

```
B+0x000..0x3FF    header; public metadata at 0x200..0x3FF (signature 5ac369e1 at 0x200)
                  firmware version at B+0x19..0x1C (a7 01 00 04 = 167.1.0.4)
                  "0565" / "JMicron JMS565" project strings at the start, on a JMS561U
B+0x400..0x7FF    config; copy 0 of stock 2020 holds the "Ugreen" strings, copy 1 "JMicron Disk"
B+0x800..0xFFF    zeros in every release image; FF after a USB upload
B+0x1000..0xFFFF  window1; 0x2000..0xBFFF has entropy 7.98 (encrypted or compressed, not decoded)
B+0x10000..0x1FFEF window2: the 8051 code, CPU address = offset - B - 0x10000
B+0x1FFF0         "EXROMEND"
```

Window2 is the code the bridge runs in normal operation. The 2018 code ends at CPU `0xE30C` and the 2020 code at `0xBB37`. The rest up to `EXROMEND` is zero padding, and the code CRC covers it. Our TRIM stubs live in that padding at `0xE310..0xE363`, and they run (the enclosure has been using them since 30 October 2026). The xRetia analysis says the code also calls an internal mask ROM at `0xDC00..0xFFFF`; on this chip the 2018 code itself extends into `0xDC00..0xE30C` in flash.

Don't read too much into the project ID in the header: our JMS561U images say `0565 / JMicron JMS565`, and integer13 saw the same on a chip with PID `A561`.

## Checksums

CRC-32 with polynomial `0x04C11DB7`, the bits of each byte fed LSB first, the four bytes of each DWORD fed in reverse order, initial value `0xFFFFFFFF`, no final XOR ([`tools/jms561_crc.py`](../tools/jms561_crc.py)). It's the standard CRC-32 over DWORD-reversed data with the register bit order reflected, so the tool lets `zlib` do the work, and the test checks it against a bit-by-bit version of the algorithm. Fields per bank, in the order they must be recomputed:

1. `B+0x1FFF8` code CRC: `crc(B+0x10000 .. B+0x1FFF7)`.
2. `B+0x1FFFC` footer: `crc(B+0x400 .. B+0x1FFFB, init 0) XOR K`. K is a constant per release: `0x79849691` for 2018 167.1.0.4, `0x1BCC43A3` for 2020 167.2.0.21.
3. `B+0x208` copy of the footer. The host tool stamps it, and release files carry zeros.
4. `B+0x3FC` header CRC: `crc(B+0x000 .. B+0x3FB)`.
5. Also `B+0x7FC` (config) and `B+0xFFFC` (window1), which our patch doesn't touch.

The code CRC lies inside the range the footer covers, so it goes first. [`tools/jms561_crc_rows.py`](../tools/jms561_crc_rows.py) `check` verifies all of them and `pack` recomputes them.

Over USB, the bridge checks the footer before it accepts an upload and refuses the last chunk with sense `5/0x26` otherwise. It doesn't check the code CRC: images with a stale one were accepted.

## Boot

What we observed:

- With a fully valid copy 0 the bridge runs copy 0, even with a valid, committed image in copy 1.
- Copy 0 with a stale code CRC: every image in that state (C, E, M2, F1) behaved exactly like the untouched copy. F1 was written by clip into copy 0, and none of its five changes showed up. F3, with the same kind of changes and every CRC valid, ran on the first try.
- Copy 0 erased, copy 1 valid in every field, parameter pages erased: no USB enumeration at all. Which of the two empty regions stopped it, we don't know.
- The bridge needs a SATA disk to enumerate and loads firmware only at a 12 V power-up.

Our reading, strongly supported but not tested in isolation: the boot loader skips a copy whose code CRC is wrong and runs the other one. We built a probe image to test exactly that (copy 0 with only the code CRC stale and a marker `A`, copy 1 valid with a marker `B`) but never needed to flash it once F3 worked.

## Which copy is running?

The USB product string is read from the code window that executes (CPU `0x0223` runs a `MOVC` loop over `0xC250`). So CPU `0xC255` (file `0x1C255` in copy 0, `0x3C255` in copy 1) is a reliable marker. Ugreen's 2018 code has `x` there ("JMS56x Series"). Our TRIM image changes it in copy 0 only, to `T`. If `lsusb -v` shows "JMS56T Series", copy 0 is running.

The version the vendor command `E0` reports doesn't tell you this: it comes from the header of the bank the bridge uses for data (XRAM `0x4FF8` = 0 means copy 0), not from the running code. Neither does READ BUFFER (`3C` mode 1): it returns flash contents, not RAM.
