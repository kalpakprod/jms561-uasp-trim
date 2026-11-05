#!/usr/bin/env python3
"""Hardware TRIM test for disks behind a JMS561U enclosure (USB 152d:1561).

    sudo tools/jms561_trim_test.py /dev/sdX [/dev/sdY] --labels MYTEST[,OTHER] [--no-fstrim]

Use a disk whose data you can afford to lose. The test writes only LBAs 960..1151, the gap
between the GPT (ends at LBA 33) and a first partition aligned at LBA 2048; it refuses a
disk whose first partition starts inside that range, a disk without one of the filesystem
labels given in --labels, and a disk that is not behind the bridge. Steps:
  1. what the bridge reports: READ CAPACITY(16), VPD B0/B2/B1, IDENTIFY, sysfs
  2. a per-LBA pattern over 960..1151, read back with O_DIRECT
  3b. UNMAPs the firmware or the drive must refuse: LBA = capacity, and a high LBA whose
      low 48 bits point at 1100 (inside the pattern); the pattern must survive
  3. blkdiscard of 1024..1087 on each disk in turn while the other disks write and verify
     a 2 GiB file; those 64 blocks must change, every other block must keep its pattern
  4. fstrim -v of every mounted filesystem at once, with write+verify running on each
A log goes to logs/trim-test-<time>.txt (or --log-dir).
"""
import argparse
import datetime
import mmap
import os
import pathlib
import subprocess
import sys

BS = 512
REGION = (960, 1152)          # patterned LBAs, end exclusive
DISCARD = (1024, 1088)        # blkdiscard target inside REGION
ALIAS_LBA = 1100              # high-LBA UNMAP aliases here if bits 63..48 are dropped
HIGH_LBA = (1 << 48) + ALIAS_LBA
ROOT = pathlib.Path(__file__).resolve().parent.parent


def pattern(lba):
    """512 bytes unique to this LBA."""
    unit = b"JMS561-TRIM-TEST" + lba.to_bytes(8, "big") + b"\xa5" * 8
    return unit * (BS // len(unit))


def check_region(first_part_start, capacity):
    """Refuse a layout where REGION is not in the free gap before the first partition."""
    if first_part_start < REGION[1]:
        raise SystemExit(f"first partition starts at {first_part_start}, inside {REGION}")
    if REGION[0] <= 33 or REGION[1] > capacity:
        raise SystemExit("region overlaps the GPT or exceeds the disk")
    if not (REGION[0] <= DISCARD[0] < DISCARD[1] <= REGION[1]):
        raise SystemExit("discard target not inside the region")
    if not (REGION[0] <= ALIAS_LBA and ALIAS_LBA + 8 <= REGION[1]):
        raise SystemExit("alias target not inside the region")
    if DISCARD[0] <= ALIAS_LBA < DISCARD[1]:
        raise SystemExit("alias target must lie outside the discard target")


def classify(blocks, discarded):
    """blocks: {lba: bytes}. Return (problems, discard_state) for the expected outcome.

    discarded: the LBA range that must have changed, or None if nothing may change."""
    problems, states = [], set()
    for lba, data in sorted(blocks.items()):
        inside = discarded is not None and discarded[0] <= lba < discarded[1]
        if not inside:
            if data != pattern(lba):
                problems.append(f"LBA {lba} lost its pattern")
        elif data == pattern(lba):
            states.add("pattern")  # the drive may return old data (LBPRZ=0)
        else:
            states.add("zeros" if data == bytes(BS) else "other")
    if "pattern" in states and len(states) > 1:
        problems.append("only part of the discard target changed")
    return problems, ",".join(sorted(states)) or "-"


class Disk:
    def __init__(self, dev):
        self.dev = dev
        self.fd = os.open(dev, os.O_RDWR | os.O_DIRECT | os.O_SYNC)

    def write(self, lba, n):
        m = mmap.mmap(-1, n * BS)
        for i in range(n):
            m[i * BS:(i + 1) * BS] = pattern(lba + i)
        assert os.pwritev(self.fd, [m], lba * BS) == n * BS

    def read(self, lba, n):
        m = mmap.mmap(-1, n * BS)
        assert os.preadv(self.fd, [m], lba * BS) == n * BS
        return {lba + i: bytes(m[i * BS:(i + 1) * BS]) for i in range(n)}


def sh(log, cmd, ok=None):
    r = subprocess.run(cmd, capture_output=True, text=True)
    log(f"$ {' '.join(cmd)}  -> exit {r.returncode}")
    for line in (r.stdout + r.stderr).splitlines():
        log("    " + line)
    return r.returncode


def behind_bridge(sysb):
    for d in pathlib.Path(sysb / "device").resolve().parents:
        v, pid = d / "idVendor", d / "idProduct"
        if v.exists() and pid.exists():
            return (v.read_text().strip(), pid.read_text().strip()) == ("152d", "1561")
    return False


def mounts_of(dev):
    return subprocess.run(["lsblk", "-nlo", "MOUNTPOINTS", dev],
                          capture_output=True, text=True).stdout.split()


def fio_verify(mount, tag):
    """Background write+verify on a mounted filesystem, to catch TRIM hitting live data."""
    return subprocess.Popen(
        ["fio", f"--name={tag}", f"--filename={mount}/jms561-trimtest-{tag}.tmp", "--rw=write",
         "--bs=1M", "--size=2G", "--direct=1", "--ioengine=libaio", "--iodepth=8",
         "--verify=crc32c", "--do_verify=1", "--verify_fatal=1", "--unlink=1"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("devs", nargs="+", help="whole-disk devices behind the bridge")
    ap.add_argument("--labels", required=True,
                    help="comma list of filesystem labels on the disks you agree to test")
    ap.add_argument("--log-dir", default=str(ROOT / "logs"))
    ap.add_argument("--no-fstrim", action="store_true")
    a = ap.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("run as root (sudo)")
    if "152d:1561" not in subprocess.run(["lsusb"], capture_output=True, text=True).stdout:
        raise SystemExit("no JMS561U bridge (152d:1561) on USB")
    allowed = set(a.labels.split(","))
    info = {}
    for dev in a.devs:
        name = os.path.basename(dev)
        sysb = pathlib.Path("/sys/block") / name
        labels = set(subprocess.run(["lsblk", "-nlo", "LABEL", dev],
                                    capture_output=True, text=True).stdout.split())
        if not labels & allowed:
            raise SystemExit(f"{dev} carries labels {labels or '{}'}, none of {allowed}")
        if not behind_bridge(sysb):
            raise SystemExit(f"{dev} is not behind the 152d:1561 bridge")
        capacity = int((sysb / "size").read_text())
        parts = sorted(int((p / "start").read_text()) for p in sysb.glob(name + "*"))
        check_region(parts[0] if parts else capacity, capacity)
        info[dev] = (sysb, capacity, ",".join(sorted(labels)))

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = pathlib.Path(a.log_dir) / f"trim-test-{stamp}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    f = out.open("w")

    def log(s):
        print(s)
        f.write(s + "\n")
        f.flush()

    fails = []
    n = REGION[1] - REGION[0]
    disks = {dev: Disk(dev) for dev in a.devs}
    discarded = set()

    def check_all(when):
        for dev, disk in disks.items():
            p, state = classify(disk.read(REGION[0], n), DISCARD if dev in discarded else None)
            log(f"{when}: {dev} target {state if dev in discarded else '-'}; "
                + ("rest intact" if not p else "; ".join(p[:5])))
            fails.extend(f"{dev}: {x}" for x in p)
            if dev in discarded and state == "pattern":
                log(f"{dev}: target unchanged, the drive returns old data after TRIM; exactness not shown")

    log(f"== {stamp} devices: " + "; ".join(
        f"{d} ({info[d][2]}, {(info[d][0] / 'device/scsi_device').exists() and os.path.basename(os.path.realpath(info[d][0] / 'device'))}) capacity {info[d][1]}"
        for d in a.devs))
    log("== 1. what the bridge reports")
    for dev, (sysb, _, _) in info.items():
        log(f"-- {dev}")
        for q in sysb.glob("device/scsi_disk/*/provisioning_mode"):
            log(f"provisioning_mode {q.read_text().strip()}")
        for q in ("discard_max_bytes", "discard_granularity", "rotational"):
            log(f"{q} {(sysb / 'queue' / q).read_text().strip()}")
        sh(log, ["sg_readcap", "-l", dev])
        for page in ("bl", "lbpv", "bdc"):
            sh(log, ["sg_vpd", "-p", page, dev])
        sh(log, ["hdparm", "-I", dev])

    log(f"== 2. pattern over LBA {REGION[0]}..{REGION[1] - 1} on every disk")
    for disk in disks.values():
        disk.write(REGION[0], n)
    check_all("pattern read back")
    if fails:
        raise SystemExit("pattern did not read back: stop")

    log("== 3b. UNMAPs that must be refused")
    for dev in a.devs:
        for lba in (info[dev][1], HIGH_LBA):
            rc = sh(log, ["sg_unmap", f"--lba={lba:#x}", "--num=8", "-v", dev])
            log(f"{dev} UNMAP lba {lba:#x}: " + ("refused (good)" if rc else "ACCEPTED"))
            if rc == 0:
                fails.append(f"{dev} UNMAP lba {lba:#x} accepted")
    check_all("after 3b")

    log(f"== 3. blkdiscard LBA {DISCARD[0]}..{DISCARD[1] - 1}, one disk at a time, "
        "while the other disks write and verify a file")
    for dev in a.devs:
        bg = [(m, fio_verify(m, f"bg{i}")) for i, o in enumerate(a.devs) if o != dev
              for m in mounts_of(o)]
        # --force: blkdiscard opens O_EXCL, which fails while the partition is mounted
        rc = sh(log, ["blkdiscard", "--force", "-o", str(DISCARD[0] * BS), "-l",
                      str((DISCARD[1] - DISCARD[0]) * BS), dev])
        if rc:
            fails.append(f"{dev} blkdiscard failed")
        discarded.add(dev)
        check_all(f"after discard on {dev}")
        for m, pr in bg:
            o, _ = pr.communicate()
            ok = pr.returncode == 0
            log(f"background fio verify on {m}: " + ("OK" if ok else "FAIL"))
            if not ok:
                log(o)
                fails.append(f"fio verify on {m} failed")

    if not a.no_fstrim:
        log("== 4. fstrim of every mounted disk at once, with write+verify running on each")
        ms = [m for dev in a.devs for m in mounts_of(dev)]
        bg = [(m, fio_verify(m, f"ft{i}")) for i, m in enumerate(ms)]
        tr = [(m, subprocess.Popen(["fstrim", "-v", m], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)) for m in ms]
        for m, pr in tr + bg:
            o, _ = pr.communicate()
            name = "fstrim" if (m, pr) in tr else "fio verify"
            log(f"{name} {m}: exit {pr.returncode} " + (o.strip().splitlines()[-1] if name == "fstrim" and o.strip() else ""))
            if pr.returncode:
                log(o)
                fails.append(f"{name} {m} failed")
        check_all("after fstrim")

    log("== kernel log since the start")
    sh(log, ["journalctl", "-k", "--no-pager", "--since",
             datetime.datetime.strptime(stamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")])
    log("RESULT " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
    f.close()
    uid = int(os.environ.get("SUDO_UID") or os.environ.get("PKEXEC_UID") or 0)
    os.chown(out, uid, -1)
    os.chmod(out, 0o444)
    print(f"log: {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
