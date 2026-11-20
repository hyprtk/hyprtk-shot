import base64
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from hyprtk_shot import cli

# 1x1 transparent PNG: enough for the no-editor path, which never decodes it
# when the format is PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ParseTest(unittest.TestCase):
    def test_defaults(self):
        opts = cli.parse([])
        self.assertEqual(opts.mode, "")
        self.assertIsNone(opts.copy)

    def test_modes_and_flags(self):
        opts = cli.parse(["window", "--copy", "--delay", "3", "--cursor", "--json"])
        self.assertEqual(opts.mode, "window")
        self.assertTrue(opts.copy)
        self.assertEqual(opts.delay, 3)
        self.assertTrue(opts.cursor)
        self.assertTrue(opts.json)

    def test_equals_forms(self):
        opts = cli.parse(["--delay=5", "--save=/tmp/a.png"])
        self.assertEqual(opts.delay, 5)
        self.assertEqual(opts.save, "/tmp/a.png")

    def test_unknown_option(self):
        with self.assertRaises(ValueError):
            cli.parse(["--turbo"])

    def test_unknown_mode(self):
        with self.assertRaises(ValueError):
            cli.parse(["hologram"])

    def test_two_modes_is_an_error(self):
        with self.assertRaises(ValueError):
            cli.parse(["region", "window"])

    def test_missing_value(self):
        with self.assertRaises(ValueError):
            cli.parse(["--delay"])


class MainTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hyprtk-shot-cli-"))
        self.saved = {key: os.environ.get(key) for key in
                      ("HYPRTK_SHOT_CONFIG_DIR", "HYPRTK_SHOT_DIR", "HYPRTK_SHOT_CONFIG")}
        os.environ["HYPRTK_SHOT_CONFIG_DIR"] = str(self.dir / "config")
        os.environ["HYPRTK_SHOT_DIR"] = str(self.dir / "pictures")
        # wl-copy talks to the compositor: never let a unit test wait on it.
        patcher = mock.patch.object(cli, "copy_to_clipboard", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for root, dirs, files in os.walk(self.dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.dir)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = cli.main(list(args))
        return status, out.getvalue(), err.getvalue()

    def test_version(self):
        status, out, _ = self.run_cli("--version")
        self.assertEqual(status, 0)
        self.assertRegex(out, r"^hyprtk-shot \d+\.\d+\.\d+")

    def test_help(self):
        status, out, _ = self.run_cli("--help")
        self.assertEqual(status, 0)
        self.assertIn("usage: hyprtk-shot", out)

    def test_unknown_option_exits_two(self):
        status, _, err = self.run_cli("--nope")
        self.assertEqual(status, 2)
        self.assertIn("unknown option", err)

    def test_quick_capture_saves_and_reports_json(self):
        target = self.dir / "one.png"
        with mock.patch.object(cli, "resolve_target", return_value={"mode": "full", "geometry": None, "output": None, "label": "All"}), \
                mock.patch.object(cli, "capture", return_value=PNG):
            status, out, _ = self.run_cli("full", "--no-edit", "--save", str(target), "--json")
        self.assertEqual(status, 0)
        self.assertTrue(target.is_file())
        payload = json.loads(out)
        self.assertEqual(payload["path"], str(target))
        self.assertEqual(payload["mode"], "full")

    def test_quick_capture_writes_png_to_stdout(self):
        class BinaryOut:
            def __init__(self):
                self.buffer = io.BytesIO()

            def write(self, _text):
                return 0

            def flush(self):
                pass

        sink = BinaryOut()
        with mock.patch.object(cli, "resolve_target", return_value={"mode": "output", "geometry": None, "output": "DP-1", "label": "DP-1"}), \
                mock.patch.object(cli, "capture", return_value=PNG), \
                redirect_stdout(sink):
            status = cli.main(["output", "--stdout"])
        self.assertEqual(status, 0)
        self.assertTrue(sink.buffer.getvalue().startswith(b"\x89PNG"))

    def test_cancelled_region_exits_three(self):
        with mock.patch.object(cli, "resolve_target", side_effect=cli.CaptureError("cancelled")):
            status, _, _ = self.run_cli("region", "--no-edit")
        self.assertEqual(status, 3)

    def test_capture_error_exits_one(self):
        with mock.patch.object(cli, "resolve_target", side_effect=cli.CaptureError("grim is not installed")):
            status, _, err = self.run_cli("region", "--no-edit")
        self.assertEqual(status, 1)
        self.assertIn("grim is not installed", err)

    def test_list_outputs(self):
        rows = [cli.outputs.__globals__["Output"]("DP-1", 0, 0, 3840, 1080, 1.0, True)]
        with mock.patch.object(cli, "outputs", return_value=rows):
            status, out, _ = self.run_cli("--list-outputs")
        self.assertEqual(status, 0)
        self.assertIn("DP-1", out)
        self.assertIn("focused", out)

    def test_last_without_history_exits_one(self):
        status, _, err = self.run_cli("last")
        self.assertEqual(status, 1)
        self.assertIn("no captures", err)


if __name__ == "__main__":
    unittest.main()
