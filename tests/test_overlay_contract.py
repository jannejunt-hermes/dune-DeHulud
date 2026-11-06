"""An unavailable value leaves a column empty; it never paints a missing-value dash."""
import unittest
from unittest import mock

import support  # noqa: F401
import dehulud_combat as m


class MissingValue(unittest.TestCase):
    def test_meter_layout_has_only_header_worm_and_status(self):
        for bits in range(8):
            enabled = frozenset(key for i, key in enumerate(m.FEATURES) if bits & (1 << i))
            sections, height = m.layout(enabled)
            self.assertTrue({name for name, _ in sections} <= {"header", "worm", "status"})
            self.assertEqual(height, 62 if "worm" in enabled else 38 if enabled else 18)

    def test_no_standalone_dash_is_ever_sent_to_the_bitmap_font(self):
        view = m.Overlay()
        with mock.patch.object(m, "big_runs", wraps=m.big_runs) as runs:
            view.step(m.Reading("on foot", taken=(37,), dealt=((120,), (40,))), m.ALL)
            m.overlay_rects(view, 2, 1)
            self.assertIn("-37", [call.args[0] for call in runs.call_args_list])
            view.step(m.Reading("unavailable", taken=None, dealt=None), m.ALL)
            self.assertEqual(m.overlay_rects(view, 2, 1), ([], []))
            view.step(m.Reading("on foot", taken=(1,), dealt=((2,), (3,))), m.ALL)
            view.reset("damage_taken")
            view.reset("damage_dealt")
            self.assertEqual(m.overlay_rects(view, 2, 1), ([], []))
            self.assertNotIn("-", [call.args[0] for call in runs.call_args_list])


if __name__ == "__main__":
    unittest.main()
