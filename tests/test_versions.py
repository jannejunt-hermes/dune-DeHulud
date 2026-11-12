"""A retired image is unsupported, with no reads beyond its PE identity."""
import unittest

from support import FakeGame, FakeSource
import dehulud
import dehulud_combat


class PreviousVersion(unittest.TestCase):
    def check_previous(self, module):
        # Previous version 26548928: its actual TimeDateStamp and SizeOfImage.
        game = FakeGame("--timestamp", "1794246991", "--image-size", "217268224")
        self.addCleanup(game.close)
        options = {"damage": module.DamageReader()} if module is dehulud_combat else {}
        meter = module.Meter(source=FakeSource(game), scan_interval=0, **options)
        reading = meter.poll(module.ALL) if options else meter.poll()
        self.assertEqual((reading.status, reading.percent, reading.fraction),
                         ("Unsupported game version", None, None))
        self.assertEqual(meter.reads, 1)
        self.assertIsNone(meter.game)
        self.assertIn(" - ", module.format_line(reading))
        if options:
            self.assertIsNone(reading.taken)
            self.assertIsNone(reading.dealt)

    def test_previous_version_plain(self):
        self.check_previous(dehulud)

    def test_previous_version_combat(self):
        self.check_previous(dehulud_combat)
