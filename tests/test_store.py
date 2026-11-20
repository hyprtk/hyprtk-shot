import os
import tempfile
import unittest
from pathlib import Path

from hyprtk_shot.store import (
    History,
    human_size,
    make_name,
    save_image,
    unique_path,
    write_bytes,
)


class NameTest(unittest.TestCase):
    def test_name_carries_the_mode(self):
        name = make_name("region")
        self.assertTrue(name.startswith("hyprtk-"))
        self.assertIn("-region.png", name)
        self.assertRegex(name, r"^hyprtk-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}")

    def test_extension_follows_the_format(self):
        self.assertTrue(make_name("full", ext="jpg").endswith(".jpg"))
        self.assertTrue(make_name("edit", ext="webp").endswith(".webp"))

    def test_mode_is_sanitised(self):
        self.assertEqual(make_name("a/b c").split("-")[-1], "abc.png")


class UniqueTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hyprtk-shot-store-"))

    def tearDown(self):
        for child in self.dir.iterdir():
            child.unlink()
        self.dir.rmdir()

    def test_an_existing_name_gets_a_counter(self):
        first = self.dir / "shot.png"
        first.write_bytes(b"x")
        second = unique_path(first)
        self.assertEqual(second.name, "shot-2.png")
        second.write_bytes(b"x")
        self.assertEqual(unique_path(first).name, "shot-3.png")

    def test_a_free_name_is_kept(self):
        path = self.dir / "free.png"
        self.assertEqual(unique_path(path), path)


class WriteTest(unittest.TestCase):
    def test_write_bytes_makes_the_directory(self):
        root = Path(tempfile.mkdtemp(prefix="hyprtk-shot-write-"))
        target = root / "nested" / "a.png"
        write_bytes(target, b"data")
        self.assertEqual(target.read_bytes(), b"data")

    def test_save_image_adds_the_extension(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QColor, QGuiApplication, QImage

        QGuiApplication.instance() or QGuiApplication([])
        image = QImage(10, 10, QImage.Format_RGB32)
        image.fill(QColor("#000000"))
        root = Path(tempfile.mkdtemp(prefix="hyprtk-shot-save-"))
        path = save_image(image, root / "capture", fmt="png")
        self.assertEqual(path.suffix, ".png")
        self.assertTrue(path.is_file())


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hyprtk-shot-hist-"))
        self.history = History(self.dir / "history.jsonl", limit=3)
        self.files = []
        for index in range(4):
            path = self.dir / f"shot{index}.png"
            path.write_bytes(b"x")
            self.files.append(path)
            self.history.add({"path": str(path), "mode": "region"})

    def tearDown(self):
        for child in self.dir.iterdir():
            child.unlink()
        self.dir.rmdir()

    def test_entries_are_newest_first(self):
        rows = self.history.entries()
        self.assertEqual(rows[0]["path"], str(self.files[-1]))
        self.assertEqual(rows[-1]["path"], str(self.files[1]))

    def test_trim_keeps_the_limit(self):
        self.assertEqual(len(self.history.entries(10)), 3)

    def test_recent_paths_skips_deleted_files(self):
        self.files[-1].unlink()
        rows = self.history.recent_paths(10)
        self.assertNotIn(str(self.files[-1]), [row["path"] for row in rows])

    def test_clear_removes_the_log(self):
        self.history.clear()
        self.assertEqual(self.history.entries(), [])

    def test_corrupt_lines_are_skipped(self):
        with (self.dir / "history.jsonl").open("a") as handle:
            handle.write("not json\n")
        self.assertTrue(self.history.entries())


class HumanSizeTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(900), "900 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")


if __name__ == "__main__":
    unittest.main()
