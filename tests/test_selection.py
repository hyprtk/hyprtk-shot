import unittest

from hyprtk_shot import selection


class SquareTest(unittest.TestCase):
    def test_drags_east_south(self):
        self.assertEqual(selection.square(10, 10, 60, 30), (60, 60))

    def test_drags_west_north(self):
        self.assertEqual(selection.square(60, 60, 10, 40), (10, 10))

    def test_mixed_direction_uses_the_longer_delta(self):
        # x grows, y shrinks: the box still has to be square and follow the pointer.
        self.assertEqual(selection.square(60, 60, 90, 20), (100, 20))

    def test_zero_delta_is_a_point(self):
        self.assertEqual(selection.square(5, 5, 5, 5), (5, 5))


class ClampTest(unittest.TestCase):
    def test_negative_width_is_normalised(self):
        self.assertEqual(selection.clamp(100, 100, -40, -20, 400, 300), (100, 100, 40, 20))

    def test_stays_inside_the_image(self):
        self.assertEqual(selection.clamp(380, 290, 40, 40, 400, 300), (360, 260, 40, 40))

    def test_smallest_size_is_enforced(self):
        x, y, w, h = selection.clamp(10, 10, 0.2, 0.2, 400, 300)
        self.assertEqual((w, h), (selection.MIN_SIZE, selection.MIN_SIZE))


class NudgeTest(unittest.TestCase):
    def test_moves_by_one_pixel(self):
        self.assertEqual(selection.nudge(100, 50, 200, 100, 1, 0, 400, 300), (101, 50, 200, 100))

    def test_moves_by_ten(self):
        self.assertEqual(selection.nudge(100, 50, 200, 100, 0, -10, 400, 300), (100, 40, 200, 100))

    def test_clamps_at_the_left_edge(self):
        self.assertEqual(selection.nudge(3, 0, 200, 100, -10, 0, 400, 300), (0, 0, 200, 100))

    def test_clamps_at_the_bottom_right(self):
        self.assertEqual(selection.nudge(195, 195, 200, 100, 10, 10, 400, 300), (200, 200, 200, 100))

    def test_never_resizes(self):
        x, y, w, h = selection.nudge(0, 0, 400, 300, 10, 10, 400, 300)
        self.assertEqual((x, y, w, h), (0, 0, 400, 300))


class FullFrameTest(unittest.TestCase):
    def test_the_default_selection_is_full_frame(self):
        self.assertTrue(selection.is_full_frame(0, 0, 640, 400, 640, 400))

    def test_a_drawn_box_is_not(self):
        self.assertFalse(selection.is_full_frame(10, 10, 200, 100, 640, 400))
        self.assertFalse(selection.is_full_frame(0, 0, 639, 400, 640, 400))

    def test_mode_switch_rounding_is_tolerated(self):
        self.assertTrue(selection.is_full_frame(0.0, 0.0, 639.7, 400.2, 640, 400))


class ResizeTest(unittest.TestCase):
    def test_east_edge_moves_only_the_width(self):
        self.assertEqual(selection.resize("e", 100, 50, 200, 100, 250, 999, 640, 480),
                         (100, 50, 150, 100))

    def test_north_edge_moves_only_the_top(self):
        self.assertEqual(selection.resize("n", 100, 50, 200, 100, 999, 80, 640, 480),
                         (100, 80, 200, 70))

    def test_south_east_corner_moves_both(self):
        self.assertEqual(selection.resize("se", 100, 50, 200, 100, 400, 300, 640, 480),
                         (100, 50, 300, 250))

    def test_north_west_corner_keeps_the_far_corner(self):
        self.assertEqual(selection.resize("nw", 100, 50, 200, 100, 40, 20, 640, 480),
                         (40, 20, 260, 130))

    def test_west_edge_cannot_cross_the_east_edge(self):
        x, y, w, h = selection.resize("w", 100, 50, 200, 100, 500, 0, 640, 480)
        self.assertEqual((x, w), (296, selection.MIN_SIZE))

    def test_east_edge_stops_at_the_image(self):
        x, y, w, h = selection.resize("e", 100, 50, 200, 100, 5000, 0, 640, 480)
        self.assertEqual(x + w, 640)

    def test_unknown_handle_is_ignored(self):
        self.assertEqual(selection.resize("middle", 1, 2, 3, 4, 9, 9, 100, 100),
                         (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
