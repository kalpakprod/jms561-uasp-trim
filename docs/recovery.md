# Unbricking a JMS561U enclosure

A JMS561U that doesn't show up on USB after a firmware change is usually still fine. Work through this in order.

## 1. Rule out the boring causes

These made us declare working images dead:

- **No cold boot.** The bridge loads firmware only when the 12 V supply comes on. Replugging USB with the supply on keeps the old code running, or keeps nothing running.
- **No disk.** The bridge doesn't enumerate on USB without a SATA disk in a bay. This applies to stock firmware too.
- **A USB 2 hub.** Our first TRIM test image "hung" on a USB 2 hub shared with the programmer and booted fine on a direct USB 3 port.

So: unplug USB and 12 V, put a disk in, power on, plug USB directly into a USB 3 port, then look at `dmesg -w` and `lsusb`.

## 2. If the bridge really doesn't start: SPI programmer

An image that fails at run time can't be fixed over USB, because nothing is running to receive an update. The programmer doesn't care what's in the flash.

1. Power off (12 V and USB), take the disks out, clip on U2 ([flashing.md](flashing.md)).
2. Read what's there: `tools/jms561-clip read broken`. Keep it, it tells you what happened.
3. Write a backup you know booted: `tools/jms561-clip write <backup.bin> <sha256>`.
4. Clip off, disk in, cold boot.

That's how we recovered from the worst state we produced: copy 0 erased, copy 1 holding a fully valid image, parameter pages erased. The enclosure was completely dead on USB until the clip wrote a full image back.

If you have no backup of your own enclosure, build one: `tools/jms561u_build.py --uas-only` needs parameter pages, and those exist only in a read of your chip. If they're erased too, you can try the pages of another unit, at the cost of its USB serial number (they're per enclosure). We haven't had to do that.

## 3. No programmer: /CS trick and empty flash

Two methods from other people, both untested on our enclosure:

- **Short /CS to GND at power-on.** integer13 recovered a JMS561U this way: power off, short flash pin 1 (/CS) to pin 4 (GND), plug in USB and power with the short in place, remove it after about 2 seconds. The bridge fails to read its flash, boots its internal mask ROM and enumerates in a minimal mode, and the vendor tool can reflash it. projectgus reports the same for the JMS567, with /CS to GND or to VCC, "working in multiple cases". 4PDA users describe shorting pins 1 and 2 of the SPI chip. Don't overdo it.
- **Empty flash.** A JMS561U with a fully erased flash boots the mask ROM (version 0.0.0.1 on the JMS567) and accepts an update over USB. Our case shows the flip side: once *any* image is in flash, the bridge tries to run it, and only a programmer or the /CS trick gets you past a bad one.

## 4. Things that will brick it

- An erase over USB (`DF 03 FB` in the vendor protocol). It wiped all 512 KiB of ours, including the parameter pages.
- A firmware for a different chip. JMicron's tools refuse most of them ("The firmware file seems not match this chip!"), but people on the Radxa and 4PDA forums still bricked JMS561 boards with images from other products. Orico firmwares are reported to brick other boards often.
- A patched image whose code CRC wasn't recomputed. It doesn't brick, it's worse: the bridge quietly runs the other copy and you believe your patch doesn't work ([lessons.md](lessons.md)).
