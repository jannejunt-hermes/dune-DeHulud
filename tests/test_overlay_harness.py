"""The X server may canonicalize overlapping outline runs without changing their union."""
import unittest

from overlay_x11 import coverage


class ShapeCoverage(unittest.TestCase):
    def test_overlapping_runs_equal_their_union(self):
        self.assertEqual(coverage([(0, 0, 3, 2), (2, 1, 3, 2)]),
                         {0: [(0, 3)], 1: [(0, 5)], 2: [(2, 5)]})
        self.assertNotEqual(coverage([(0, 0, 3, 2)]), coverage([(0, 0, 3, 1)]))


if __name__ == "__main__":
    unittest.main()
