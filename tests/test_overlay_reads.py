"""Unavailable overlays must suppress damage memory reads while preserving the switches."""
import io
import os
import tempfile
import unittest
from unittest import mock

from damage_model import LoggedReader
from support import FakeGame, FakeSource
from test_combat_window import FakeTk, Ev
import dehulud_combat as m


class OverlayReadLog(unittest.TestCase):
    def test_no_shape_window_reads_only_worm_and_saves_switches(self):
        game = FakeGame("--build", "26592269", "--damage")
        self.addCleanup(game.close)
        reader = LoggedReader(m.Reader(game.pid))

        class AttachmentReader:
            def __init__(self, pid):
                self.count = 0

            def read(self, address, size):
                self.count += 1
                return reader.read(address, size)

        meter = m.Meter(source=FakeSource(game), reader_factory=AttachmentReader,
                        scan_interval=0, damage=m.DamageReader())
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "config.json")
            stderr = io.StringIO()
            with mock.patch.object(m, "monitors", return_value=[(0, 0, 1280, 800, True)]), \
                    mock.patch("sys.stderr", stderr):
                w = m.Window(FakeTk(), meter, cfg, display=":9", shape=False)
                self.addCleanup(w.quit)
                metadata = game.damage_frame({"at_ms": 0}, reader)
                w.tick()
                reader.assert_no_reads({"damage_taken", "damage_dealt"}, metadata["feature_ranges"])
                self.assertGreater(len(reader.log), 0, "worm still reads the fake game")
                self.assertEqual(w.enabled, m.ALL)
                self.assertIsNone(w.overlay_state())
                w.tick()
                self.assertEqual(stderr.getvalue().count(m.NO_SHAPE), 1)
                # Switches stay useful even when damage display is unavailable.
                for _ in range(2):
                    ev = Ev(80, 9, w.pos)
                    w._press(ev)
                    w._release(ev)
                self.assertTrue(m.load_config(cfg)["damage_taken"])
                ev = Ev(10, 9, w.pos)
                w._press(ev)
                w._release(ev)
                reader.log.clear()
                w.tick()
                self.assertEqual(reader.log, [], "damage-only switches with no overlay read nothing")
                self.assertEqual(w.enabled, frozenset({"damage_taken", "damage_dealt"}))
                w.quit()
                self.assertTrue(m.load_config(cfg)["damage_taken"])
                self.assertTrue(m.load_config(cfg)["damage_dealt"])

    def test_available_overlay_keeps_both_damage_routes(self):
        game = FakeGame("--build", "26592269", "--damage")
        self.addCleanup(game.close)
        reader = LoggedReader(m.Reader(game.pid))

        class AttachmentReader:
            def __init__(self, pid):
                self.count = 0

            def read(self, address, size):
                self.count += 1
                return reader.read(address, size)

        meter = m.Meter(source=FakeSource(game), reader_factory=AttachmentReader,
                        scan_interval=0, damage=m.DamageReader())
        metadata = game.damage_frame({"at_ms": 0}, reader)
        meter.poll(m.read_features(m.ALL, True))
        for feature in ("damage_taken", "damage_dealt"):
            self.assertTrue(any(entry["address"] < hi and lo < entry["address"] + entry["size"] for entry in reader.log
                                for lo, hi in metadata["feature_ranges"][feature]), feature)


if __name__ == "__main__":
    unittest.main()
