import unittest
from backend.window_placement import centered_bounds


class PlacementTests(unittest.TestCase):
    def test_centered_and_inside_work_area(self):
        for area, scale in [
            ((0, 0, 1920, 1040), 1),
            ((0, 0, 1366, 728), 1),
            ((0, 0, 1920, 1040), 1.5),
            ((-2560, 0, 0, 1400), 1.5),
            ((1920, -1080, 3840, -40), 2),
            ((48, 0, 1024, 768), 1.25),
        ]:
            with self.subTest(area=area, scale=scale):
                x, y, width, height = centered_bounds(area, scale)
                left, top, right, bottom = area
                self.assertGreaterEqual(x, left)
                self.assertGreaterEqual(y, top)
                self.assertLessEqual(x+width, right)
                self.assertLessEqual(y+height, bottom)
                self.assertLessEqual(abs((x-left)-(right-x-width)), 1)
                self.assertLessEqual(abs((y-top)-(bottom-y-height)), 1)

    def test_preserves_preferred_size_when_it_fits(self):
        self.assertEqual(centered_bounds((0, 0, 1920, 1040)), (240, 50, 1440, 940))


if __name__ == '__main__':
    unittest.main()
