import os
import tempfile
import unittest
from pathlib import Path

from hyprtk_shot.settings import DEFAULTS, Settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hyprtk-shot-settings-"))
        self.path = self.dir / "config.json"

    def tearDown(self):
        for child in self.dir.iterdir():
            child.unlink()
        self.dir.rmdir()

    def test_defaults_are_used_without_a_file(self):
        settings = Settings(self.path)
        self.assertEqual(settings.get("mode"), "region")
        self.assertTrue(settings.get("copy"))

    def test_set_persists_and_reloads(self):
        settings = Settings(self.path)
        self.assertTrue(settings.set("mode", "window"))
        settings.save()
        again = Settings(self.path)
        self.assertEqual(again.get("mode"), "window")

    def test_set_reports_a_no_op(self):
        settings = Settings(self.path)
        self.assertFalse(settings.set("mode", "region"))
        self.assertFalse(settings.set("unknown-key", 1))

    def test_values_are_clamped(self):
        settings = Settings(self.path)
        settings.set("delay", 99)
        self.assertEqual(settings.get("delay"), 30)
        settings.set("delay", -4)
        self.assertEqual(settings.get("delay"), 0)
        settings.set("quality", 5)
        self.assertEqual(settings.get("quality"), 40)
        settings.set("dim", 4.0)
        self.assertEqual(settings.get("dim"), 0.9)
        settings.set("stroke", 99)
        self.assertEqual(settings.get("stroke"), 24.0)

    def test_bad_enums_fall_back(self):
        settings = Settings(self.path)
        settings.set("mode", "hologram")
        self.assertEqual(settings.get("mode"), "region")
        settings.set("format", "tiff")
        self.assertEqual(settings.get("format"), "png")
        settings.set("color", "blue")
        self.assertEqual(settings.get("color"), DEFAULTS["color"])

    def test_dir_expands_the_home_tilde(self):
        settings = Settings(self.path)
        settings.set("dir", "~/Pictures/Shots")
        self.assertEqual(settings.get("dir"), os.path.expanduser("~/Pictures/Shots"))

    def test_empty_dir_means_the_default(self):
        settings = Settings(self.path)
        settings.set("dir", "")
        self.assertTrue(settings.as_dict()["dir"].endswith("Screenshots"))

    def test_a_broken_file_is_ignored(self):
        self.path.write_text("{nope", encoding="utf-8")
        settings = Settings(self.path)
        self.assertEqual(settings.get("mode"), "region")

    def test_unknown_keys_are_dropped(self):
        self.path.write_text('{"mode": "full", "explode": true}', encoding="utf-8")
        settings = Settings(self.path)
        self.assertEqual(settings.get("mode"), "full")
        self.assertNotIn("explode", settings.as_dict())


if __name__ == "__main__":
    unittest.main()
