import unittest
from unittest import mock

from hyprtk_shot import capture as cap


class OutputGeometryTest(unittest.TestCase):
    def test_logical_size_divides_by_scale(self):
        out = cap.Output(name="DP-1", x=0, y=0, width=3840, height=2160, scale=2.0,
                         focused=True)
        self.assertEqual((out.logical_width, out.logical_height), (1920, 1080))
        self.assertEqual(out.geometry, "0,0 1920x1080")

    def test_geometry_uses_logical_offsets(self):
        out = cap.Output(name="HDMI-A-1", x=1920, y=0, width=1920, height=1080,
                         scale=1.0, focused=False)
        self.assertEqual(out.geometry, "1920,0 1920x1080")

    def test_scale_zero_does_not_divide_by_zero(self):
        out = cap.Output(name="BAD", x=0, y=0, width=100, height=100, scale=0.0,
                         focused=False)
        self.assertEqual(out.logical_width, 100)


class MonitorParsingTest(unittest.TestCase):
    def test_outputs_reads_hyprctl_monitors(self):
        data = [
            {"name": "DP-1", "x": 0, "y": 0, "width": 3840, "height": 1080,
             "scale": 1.0, "focused": False, "refreshRate": 60.0},
            {"name": "DP-2", "x": 3840, "y": 0, "width": 2560, "height": 1440,
             "scale": 1.25, "focused": True, "refreshRate": 144.0},
        ]
        with mock.patch.object(cap, "_hyprctl_json", return_value=data):
            rows = cap.outputs()
        self.assertEqual([row.name for row in rows], ["DP-1", "DP-2"])
        self.assertEqual(rows[1].logical_width, 2048)
        self.assertTrue(rows[1].focused)
        self.assertEqual(cap.focused_output(rows).name, "DP-2")

    def test_output_without_a_name_is_dropped(self):
        with mock.patch.object(cap, "_hyprctl_json", return_value=[{"name": ""}]):
            self.assertEqual(cap.outputs(), [])

    def test_no_hyprctl_is_an_empty_list_not_a_crash(self):
        with mock.patch.object(cap, "_hyprctl_json", return_value=None):
            self.assertEqual(cap.outputs(), [])
            self.assertEqual(cap.windows(), [])
            self.assertIsNone(cap.active_window())
            self.assertIsNone(cap.window_at(1, 1))


class WindowTest(unittest.TestCase):
    def rows(self):
        return [
            cap.Window("0x1", "Terminal", "hyprtk-term", 10, 40, 800, 500, 0, False, 3),
            cap.Window("0x2", "Editor", "hyprtk-editor", 100, 100, 400, 300, 0, True, 0),
        ]

    def test_contains(self):
        window = self.rows()[0]
        self.assertTrue(window.contains(10, 40))
        self.assertTrue(window.contains(809, 539))
        self.assertFalse(window.contains(9, 40))
        self.assertFalse(window.contains(10, 540))

    def test_window_at_prefers_the_most_recently_focused(self):
        pick = cap.window_at(120, 120, self.rows())
        self.assertIsNotNone(pick)
        self.assertEqual(pick.address, "0x2")

    def test_window_at_returns_none_outside_everything(self):
        self.assertIsNone(cap.window_at(5000, 5000, self.rows()))

    def test_windows_skips_hidden_and_empty(self):
        data = [
            {"address": "0x1", "at": [0, 0], "size": [100, 100], "hidden": True},
            {"address": "0x2", "at": [0, 0], "size": [0, 0]},
            {"address": "0x3", "at": [5, 5], "size": [10, 20], "class": "foot"},
        ]
        with mock.patch.object(cap, "_hyprctl_json", return_value=data):
            rows = cap.windows()
        self.assertEqual([row.address for row in rows], ["0x3"])
        self.assertEqual(rows[0].geometry, "5,5 10x20")


class GrimArgvTest(unittest.TestCase):
    def test_region_needs_geometry(self):
        argv = cap.grim_argv("region", geometry="10,20 300x200")
        self.assertEqual(argv, ["grim", "-g", "10,20 300x200", "-"])

    def test_region_can_grab_a_whole_output_for_the_overlay(self):
        argv = cap.grim_argv("region", output="DP-1")
        self.assertEqual(argv, ["grim", "-o", "DP-1", "-"])

    def test_window_uses_geometry(self):
        argv = cap.grim_argv("window", geometry="0,38 1200x800")
        self.assertEqual(argv[:3], ["grim", "-g", "0,38 1200x800"])

    def test_output_prefers_the_name(self):
        argv = cap.grim_argv("output", output="DP-1", geometry="0,0 1x1")
        self.assertEqual(argv, ["grim", "-o", "DP-1", "-"])

    def test_output_falls_back_to_geometry(self):
        argv = cap.grim_argv("output", geometry="0,0 800x600")
        self.assertEqual(argv, ["grim", "-g", "0,0 800x600", "-"])

    def test_full_takes_no_target(self):
        self.assertEqual(cap.grim_argv("full"), ["grim", "-"])

    def test_cursor_and_jpeg_options(self):
        argv = cap.grim_argv("full", cursor=True, image_format="jpeg", quality=72)
        self.assertEqual(argv, ["grim", "-c", "-t", "jpeg", "-q", "72", "-"])

    def test_quality_is_clamped(self):
        argv = cap.grim_argv("full", image_format="jpeg", quality=900)
        self.assertIn("100", argv)

    def test_region_without_geometry_raises(self):
        with self.assertRaises(cap.CaptureError):
            cap.grim_argv("region")

    def test_unknown_mode_raises(self):
        with self.assertRaises(cap.CaptureError):
            cap.grim_argv("everything")


class ResolveTargetTest(unittest.TestCase):
    def test_region_grabs_the_focused_output_for_the_overlay(self):
        monitor = cap.Output("DP-1", 0, 0, 3840, 1080, 1.0, True)
        with mock.patch.object(cap, "focused_output", return_value=monitor):
            target = cap.resolve_target("region")
        # Region selection happens on the frozen frame, not in slurp.
        self.assertEqual(target["mode"], "region")
        self.assertEqual(target["output"], "DP-1")
        self.assertIsNone(target["geometry"])
        self.assertEqual(target["logical_width"], 3840)

    def test_region_accepts_an_explicit_geometry(self):
        target = cap.resolve_target("region", region="10,20 100x50")
        self.assertEqual(target["geometry"], "10,20 100x50")
        self.assertIsNone(target["output"])

    def test_region_without_a_monitor(self):
        with mock.patch.object(cap, "focused_output", return_value=None):
            with self.assertRaises(cap.CaptureError):
                cap.resolve_target("region")

    def test_window_uses_the_active_window(self):
        window = cap.Window("0x9", "Doc", "app", 4, 5, 600, 400, 0, False, 0)
        with mock.patch.object(cap, "active_window", return_value=window):
            target = cap.resolve_target("window")
        self.assertEqual(target["geometry"], "4,5 600x400")
        self.assertEqual(target["label"], "Doc")

    def test_window_picker_address_wins_over_focus(self):
        picked = cap.Window("0x2", "Picked", "app", 10, 20, 500, 400, 0, False, 3)
        focused = cap.Window("0x1", "Focused", "app", 0, 0, 400, 300, 0, False, 0)
        with mock.patch.object(cap, "windows", return_value=[focused, picked]), \
                mock.patch.object(cap, "active_window", return_value=focused):
            target = cap.resolve_target("window", window="0x2")
        self.assertEqual(target["geometry"], "10,20 500x400")
        self.assertEqual(target["label"], "Picked")

    def test_a_closed_explicit_window_is_an_error_not_a_substitution(self):
        """Picking a window that vanished must not silently capture another."""
        focused = cap.Window("0x1", "Focused", "app", 0, 0, 400, 300, 0, False, 0)
        with mock.patch.object(cap, "windows", return_value=[focused]), \
                mock.patch.object(cap, "active_window", return_value=focused):
            with self.assertRaises(cap.CaptureError):
                cap.resolve_target("window", window="0xdead")

    def test_no_pick_uses_the_focused_window(self):
        focused = cap.Window("0x1", "Focused", "app", 0, 0, 400, 300, 0, False, 0)
        with mock.patch.object(cap, "windows", return_value=[focused]), \
                mock.patch.object(cap, "active_window", return_value=focused):
            target = cap.resolve_target("window")
        self.assertEqual(target["geometry"], "0,0 400x300")

    def test_windows_carry_their_workspace(self):
        data = [{"address": "0x1", "at": [0, 43], "size": [800, 600], "class": "a",
                 "title": "A", "focusHistoryID": 0, "workspace": {"id": 2, "name": "2"}},
                {"address": "0x2", "at": [0, 43], "size": [800, 600], "class": "b",
                 "title": "B", "focusHistoryID": 1, "workspace": {"id": 5, "name": "5"}}]
        with mock.patch.object(cap, "_hyprctl_json", return_value=data):
            rows = cap.windows()
        self.assertEqual([row.workspace for row in rows], [2, 5])
        self.assertEqual(rows[0].as_row()["workspace"], 2)

    def test_active_workspace(self):
        with mock.patch.object(cap, "_hyprctl_json", return_value={"id": 3, "name": "3"}):
            self.assertEqual(cap.active_workspace(), 3)
        with mock.patch.object(cap, "_hyprctl_json", return_value=None):
            self.assertEqual(cap.active_workspace(), 0)

    def test_window_without_a_window(self):
        with mock.patch.object(cap, "active_window", return_value=None):
            with self.assertRaises(cap.CaptureError):
                cap.resolve_target("window")

    def test_output_uses_the_focused_monitor(self):
        monitor = cap.Output("DP-3", 0, 0, 1920, 1080, 1.0, True)
        with mock.patch.object(cap, "focused_output", return_value=monitor):
            target = cap.resolve_target("output")
        self.assertEqual(target["output"], "DP-3")


class SlurpTest(unittest.TestCase):
    def test_select_region_returns_the_geometry(self):
        result = mock.Mock(returncode=0, stdout=b"10,20 300x200\n", stderr=b"")
        with mock.patch.object(cap, "have", return_value=True), \
                mock.patch.object(cap, "_run", return_value=result):
            self.assertEqual(cap.select_region(), "10,20 300x200")

    def test_select_region_cancelled(self):
        result = mock.Mock(returncode=1, stdout=b"", stderr=b"")
        with mock.patch.object(cap, "have", return_value=True), \
                mock.patch.object(cap, "_run", return_value=result):
            self.assertIsNone(cap.select_region())

    def test_select_region_without_slurp(self):
        with mock.patch.object(cap, "have", return_value=False):
            with self.assertRaises(cap.CaptureError):
                cap.select_region()


class CaptureTest(unittest.TestCase):
    def test_capture_returns_bytes(self):
        result = mock.Mock(returncode=0, stdout=b"png-bytes", stderr=b"")
        with mock.patch.object(cap, "have", return_value=True), \
                mock.patch.object(cap, "_run", return_value=result):
            self.assertEqual(cap.capture("full"), b"png-bytes")

    def test_capture_surfaces_grims_error(self):
        result = mock.Mock(returncode=1, stdout=b"", stderr=b"compositor does not support the protocol")
        with mock.patch.object(cap, "have", return_value=True), \
                mock.patch.object(cap, "_run", return_value=result):
            with self.assertRaises(cap.CaptureError) as ctx:
                cap.capture("full")
        self.assertIn("compositor", str(ctx.exception))

    def test_capture_without_grim_raises(self):
        with mock.patch.object(cap, "have", return_value=False):
            with self.assertRaises(cap.CaptureError):
                cap.capture("full")

    def test_empty_image_is_an_error(self):
        result = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch.object(cap, "have", return_value=True), \
                mock.patch.object(cap, "_run", return_value=result):
            with self.assertRaises(cap.CaptureError):
                cap.capture("full")


if __name__ == "__main__":
    unittest.main()
