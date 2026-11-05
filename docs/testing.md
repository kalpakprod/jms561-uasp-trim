# Testing TRIM on the enclosure, and what we measured

`fstrim` printing "trimmed" proves very little. It shows that Linux sent discards and the bridge said GOOD. It doesn't show that the drive trimmed the right blocks, or only those. A bridge that drops the high bits of an LBA, or sends the range to the other bay, would also print "trimmed" and quietly destroy data. So the test writes known data around a target, discards the target and reads everything back.

## Quick check: does Linux see TRIM?

```sh
sudo tools/jms561-status
```

It prints the USB link, the driver, the product string and, for each disk behind the bridge, what Linux uses to decide on discard. With the TRIM image and an SSD you should see `JMS56T Series`, `driver uas`, `provisioning_mode unmap`, `discard_max_bytes 33521664`, `lbpme=1`, `Maximum unmap LBA count: 0xffc0`, `LBPU=1` and `Non-rotating medium`. The same by hand:

```sh
lsusb -t
cat /sys/block/sdX/device/scsi_disk/*/provisioning_mode
lsblk -D /dev/sdX
sudo sg_readcap -l /dev/sdX
sudo sg_vpd -p bl /dev/sdX; sudo sg_vpd -p lbpv /dev/sdX; sudo sg_vpd -p bdc /dev/sdX
```

## The full test

Use a disk you can afford to lose. [`tools/jms561_trim_test.py`](../tools/jms561_trim_test.py) writes only LBAs 960..1151, which lie in the gap between the GPT and a first partition at LBA 2048, so a mounted filesystem isn't touched. It refuses any disk whose filesystem label you didn't name, any disk that isn't behind a `152d:1561` bridge, and any layout where the first partition starts inside that range.

```sh
sudo tools/jms561_trim_test.py /dev/sdX --labels mytestdisk
sudo tools/jms561_trim_test.py /dev/sdX /dev/sdY --labels disk1,disk2    # both bays
```

What it does:

1. Records what the bridge reports (RC16, VPD B0/B2/B1, IDENTIFY, sysfs).
2. Writes a unique 512-byte pattern into every LBA of 960..1151 and reads it back with `O_DIRECT`.
3. Sends two UNMAPs that must be refused, and checks that every pattern survived:
   - LBA = disk capacity (past the end): the drive must abort.
   - LBA = 2^48 + 1100: the vendor parser would drop the top bits and trim LBA 1100, which holds pattern data. The patch must refuse it.
4. `blkdiscard` of LBAs 1024..1087 on one disk while every other disk writes and verifies a 2 GiB file with fio. Exactly those 64 blocks may change, every neighbour must keep its pattern, and the same LBAs on the other disk must not change.
5. `fstrim` on every mounted filesystem at once, with write+verify running on each.
6. Kernel log since the start. A log lands in `logs/trim-test-<time>.txt`.

A drive that returns old data after TRIM (LBPRZ = 0 allows that) shows the target as unchanged. The test reports this and doesn't count it as a failure, but then it can't prove exactness on that drive.

## Our results (30 October 2026, laptop, UASP + TRIM image)

One SSD in the box (CUSU C200 960 GB, XFS):

- Product "JMS56T Series", SuperSpeed, `uas`. Linux on its own: `provisioning_mode unmap`, `discard_max_bytes 33521664`, `rotational 0`.
- `blkdiscard` of LBAs 1024..1087: exactly those 64 blocks read zeros afterwards. 960..1023 and 1088..1151 kept their patterns.
- UNMAP at LBA = capacity: ABORTED COMMAND (the drive refused, the firmware passed it on). UNMAP at 2^48 + 1100: ILLEGAL REQUEST, invalid field in parameter list (the patch's guard). LBA 1100 kept its pattern.
- `fstrim` trimmed 894.3 GiB, kernel log clean.

Both bays (a 1 TB SSD with btrfs as LUN 0, the CUSU as LUN 1): PASS. Bad UNMAPs refused on both disks. A discard on one disk zeroed exactly its 64 target blocks and left the same LBAs on the other disk intact while that disk ran a 2 GiB write+verify. `fstrim` of both at once (196.4 GiB and 894.3 GiB) with write+verify running on both: every verify OK, kernel log clean. btrfs switched on asynchronous discard by itself.

## Speed before and after the first TRIM

The CUSU SSD had spent its life behind bridges that never passed TRIM. fio, 4 GiB sequential, direct I/O, on its XFS (2% full: 18 GiB of 894):

| | Write | Read |
|---|---|---|
| Before the first `fstrim` | 42.7 MiB/s | 369 MiB/s |
| After the first `fstrim` | 389 MiB/s | 382 MiB/s |

Then a sustained 40 GiB write: 390 MiB/s flat for 105 seconds, the slowest second at 327 MiB/s, no cache cliff. At that point the limit is the 5 Gb/s USB link, not the drive. The filesystem was nearly empty before the test, so a full filesystem wasn't the cause of the slow writes. Our explanation, which we can't prove from here: the drive's flash was still full of blocks that had been deleted without ever being trimmed.

## In daily use

The enclosure now stays plugged into a second Linux machine with both SSDs in. Checked there on 5 November 2026: `uas` at 5000 Mb/s, both disks with `DISC-GRAN 512B`, `DISC-MAX 32M`, `ROTA 0`, and the weekly `fstrim.timer` enabled (its last run was on 2 November).

## Not tested yet

- A hard disk in a bay. The patch should leave it on stock behaviour (no TRIM flag, reported as rotating), but nobody has checked.
- Mixed SSD + HDD.
- Long-term behaviour under heavy concurrent load beyond the test above.

If you run the test on your enclosure, please post the result: [report form](../../../issues/new?template=enclosure-report.yml).
