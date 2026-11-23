"""`--save PATH` must apply to the overlay path too.

It used to apply only to the no-editor capture: the overlay always wrote into
the configured screenshot directory and silently ignored the flag. Found by
driving the overlay with injected input.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hyprtk_shot.bridge import Bridge  # noqa: E402
from hyprtk_shot.settings import Settings  # noqa: E402


def bridge_with(path: str) -> Bridge:
    b = Bridge(settings=Settings())
    b.save_path_override = path
    return b


class SavePathOverrideTest(unittest.TestCase):
    def test_a_file_path_is_used_as_given(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "capture.png")
            self.assertEqual(str(bridge_with(target)._target_path()), target)

    def test_a_directory_gets_a_generated_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = bridge_with(directory + "/")._target_path()
            self.assertEqual(path.parent, Path(directory))
            self.assertEqual(path.suffix, ".png")
            self.assertTrue(path.name)

    def test_a_path_without_a_suffix_gets_the_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = bridge_with(os.path.join(directory, "shot"))._target_path()
            self.assertEqual(path.suffix, ".png")

    def test_an_existing_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "capture.png"
            target.write_bytes(b"old")
            path = bridge_with(str(target))._target_path()
            self.assertNotEqual(path, target)
            self.assertTrue(path.name.startswith("capture"))

    def test_without_an_override_the_settings_dir_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings()
            settings.set("dir", directory)
            b = Bridge(settings=settings)
            self.assertEqual(b._target_path().parent, Path(directory))


if __name__ == "__main__":
    unittest.main()
