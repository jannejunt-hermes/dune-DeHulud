import re
import unittest
from pathlib import Path

import dehulud_combat as c


class OverlayModel(unittest.TestCase):
    def reading(self, taken=(), dealt=((), ())):
        return c.Reading("", None, None, "", "", taken, dealt)

    def test_geometry_and_monitor(self):
        for mon, want in [
            ((0, 0, 1920, 1080), (859, 270, 202, 102, 2, 1)),
            ((0, 0, 2560, 1440), (1129, 360, 302, 152, 3, 1)),
            ((0, 0, 3840, 2160), (1718, 540, 404, 204, 4, 2)),
            ((-100, 37, 1919, 1079), (758, 306, 202, 102, 2, 1)),
            ((-30, -21, 99, 101), (-32, 4, 102, 52, 1, 1)),
        ]:
            self.assertEqual(c.overlay_geometry(mon), want)
        mons = [(10, 20, 800, 600, False), (-900, -50, 900, 1080, True)]
        self.assertEqual(c.overlay_monitor(mons, (0, 0, 1, 1)), mons[1][:4])
        self.assertEqual(c.overlay_monitor(mons[:1], (0, 0, 1, 1)), mons[0][:4])
        self.assertEqual(c.overlay_monitor([], (1, 2, 3, 4)), (1, 2, 3, 4))

    def test_glyphs_match_bitmap_font(self):
        source = (Path(__file__).resolve().parents[1] / "rust/src/font.rs").read_text()
        table = source.split("pub static BIG:")[1].split("#[cfg(test)]")[0]
        glyphs = dict(re.findall(r"\('([0-9-])', \"([.# ]+)\"\)", table))
        self.assertEqual({key: rows.split() for key, rows in glyphs.items()}, c.BIG_GLYPHS)

    def test_exact_rectangles_and_order(self):
        v = c.Overlay()
        v.taken = [(1, 2)]
        v.dealt = [(1, 4, "shield")]
        runs = [(32, 5, 5), (32, 6, 5), (41, 0, 2), (40, 1, 3), (39, 2, 4),
                (41, 3, 2), (41, 4, 2), (41, 5, 2), (41, 6, 2), (41, 7, 2),
                (41, 8, 2), (41, 9, 2), (39, 10, 6),
                (58, 0, 2), (57, 1, 3), (56, 2, 4), (58, 3, 2), (58, 4, 2),
                (58, 5, 2), (58, 6, 2), (58, 7, 2), (58, 8, 2), (58, 9, 2), (56, 10, 6)]
        colours = ["#b63a2f"] * 13 + ["#28343d"] * 11
        expected = ([(x * 2, y * 2, w * 2 + 2, 4) for x, y, w in runs],
                    [(1 + x * 2, 1 + y * 2, w * 2, 2, colour)
                     for (x, y, w), colour in zip(runs, colours)])
        self.assertEqual(c.overlay_rects(v, 2, 1), expected)
        self.assertEqual(expected[0][0], (64, 10, 12, 4))

    def test_merge_cap_life_and_colours(self):
        v = c.Overlay()
        v.step(self.reading((1e9,), ((2.5,), (4.5,))), c.ALL)
        self.assertEqual(v.taken, [(99999, 0)])
        self.assertEqual(v.dealt, [(3, 0, "health"), (5, 0, "shield")])
        for age in range(5):
            fills = c.overlay_rects(v, 1, 1)[1]
            self.assertEqual(list(dict.fromkeys(r[4] for r in fills)),
                             [c.OVERLAY_TAKEN[age], c.OVERLAY_HEALTH[age], c.OVERLAY_SHIELD[age]])
            v.step(self.reading(), c.ALL)
        self.assertTrue(v.empty())
        self.assertEqual(c.overlay_rects(v, 1, 1), ([], []))
        for n in range(1, 6):
            v.step(self.reading((n,), ((n,), (n + 10,))), c.ALL)
        self.assertEqual(v.taken, [(5, 0), (4, 1), (3, 2), (2, 3)])
        self.assertEqual(v.dealt, [(5, 0, "health"), (15, 0, "shield"),
                                   (4, 1, "health"), (14, 1, "shield")])

    def test_clear_reset_and_read_features(self):
        v = c.Overlay()
        self.assertTrue(v.empty())
        for r, enabled in [(self.reading(None, None), c.ALL),
                           (self.reading(), set()),
                           (self.reading(None, (None, ())), c.ALL),
                           (self.reading(None, ((), None)), c.ALL)]:
            v.step(self.reading((1,), ((2,), (3,))), c.ALL)
            v.step(r, enabled)
            self.assertTrue(v.empty())
            self.assertEqual(c.overlay_rects(v, 2, 1), ([], []))
        v.step(self.reading((0.1,), ((0.0,), (0.49,))), c.ALL)
        self.assertTrue(v.empty())
        v.step(self.reading((1,), ((2,), ())), c.ALL)
        v.reset("worm")
        self.assertFalse(v.empty())
        v.reset("damage_taken")
        self.assertEqual(v.taken, [])
        v.reset("damage_dealt")
        self.assertTrue(v.empty())
        self.assertEqual(c.read_features(c.ALL, True), c.ALL)
        self.assertEqual(c.read_features(c.ALL, False), {"worm"})
        self.assertEqual(c.read_features({"damage_taken"}, False), set())
