"""The hardware TRIM test stays out of the partition and judges readbacks correctly."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("trim_test", ROOT / "tools/jms561_trim_test.py")
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class TestRegion(unittest.TestCase):
    def test_aligned_layout_accepted(self):
        t.check_region(2048, 1875385008)  # 960 GB SSD, GPT, first partition at 2048

    def test_partition_inside_region_refused(self):
        with self.assertRaises(SystemExit):
            t.check_region(1024, 1875385008)

    def test_high_lba_aliases_into_pattern_outside_discard(self):
        alias = t.HIGH_LBA & ((1 << 48) - 1)
        self.assertEqual(alias, t.ALIAS_LBA)
        self.assertTrue(t.REGION[0] <= alias and alias + 8 <= t.REGION[1])
        self.assertTrue(alias + 8 <= t.DISCARD[0] or alias >= t.DISCARD[1])


class TestBehindBridge(unittest.TestCase):
    def tree(self, vid, pid):
        import tempfile
        root = pathlib.Path(tempfile.mkdtemp())
        usb = root / "usb6/6-1/6-1.2"
        dev = usb / "6-1.2:1.0/host1/target1:0:0/1:0:0:1"
        dev.mkdir(parents=True)
        (usb / "idVendor").write_text(vid + "\n")
        (usb / "idProduct").write_text(pid + "\n")
        (root / "usb6/6-1/idVendor").write_text("05e3\n")  # the hub above must not decide
        (root / "usb6/6-1/idProduct").write_text("0626\n")
        blk = root / "sdc"
        blk.mkdir()
        (blk / "device").symlink_to(dev)
        return blk

    def test_disk_behind_bridge(self):
        self.assertTrue(t.behind_bridge(self.tree("152d", "1561")))

    def test_other_usb_disk(self):
        self.assertFalse(t.behind_bridge(self.tree("05e3", "0751")))


class TestClassify(unittest.TestCase):
    def blocks(self, changed=(), fill=bytes(512)):
        return {lba: (fill if lba in changed else t.pattern(lba)) for lba in range(*t.REGION)}

    def test_patterns_unique(self):
        self.assertEqual(len({t.pattern(lba) for lba in range(*t.REGION)}), t.REGION[1] - t.REGION[0])
        self.assertEqual(len(t.pattern(5)), 512)

    def test_exact_discard_passes(self):
        self.assertEqual(t.classify(self.blocks(range(*t.DISCARD)), t.DISCARD), ([], "zeros"))

    def test_neighbour_hit_fails(self):
        p, _ = t.classify(self.blocks(range(t.DISCARD[0] - 1, t.DISCARD[1])), t.DISCARD)
        self.assertEqual(p, [f"LBA {t.DISCARD[0] - 1} lost its pattern"])

    def test_short_discard_fails(self):
        p, _ = t.classify(self.blocks(range(t.DISCARD[0], t.DISCARD[1] - 1)), t.DISCARD)
        self.assertEqual(p, ["only part of the discard target changed"])

    def test_old_data_after_trim_is_not_a_failure(self):
        self.assertEqual(t.classify(self.blocks(), t.DISCARD), ([], "pattern"))

    def test_alias_damage_detected_when_nothing_may_change(self):
        p, _ = t.classify(self.blocks(range(t.ALIAS_LBA, t.ALIAS_LBA + 8)), None)
        self.assertEqual(len(p), 8)

    def test_nonzero_discard_state(self):
        self.assertEqual(t.classify(self.blocks(range(*t.DISCARD), b"\xff" * 512), t.DISCARD)[1], "other")


if __name__ == "__main__":
    unittest.main()
