#!/usr/bin/env python3
"""Dev-only: load the QML headlessly, drive a session, and fail on warnings.

The unit tests cover geometry and rendering. This covers the parts only a real
QML load finds: a renamed slot, an unregistered type, a property the palette no
longer exposes, a toolbar binding that throws, a save that never lands.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

_SANDBOX = tempfile.mkdtemp(prefix="hyprtk-shot-boot-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SANDBOX, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "cache")
os.environ["HYPRTK_WAL_HOME"] = _SANDBOX
os.environ["HYPRTK_SHOT_CONFIG_DIR"] = os.path.join(_SANDBOX, "config", "hyprtk-shot")
os.environ["HYPRTK_SHOT_DIR"] = os.path.join(_SANDBOX, "pictures")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from hyprtk_shot.annotate import Shape  # noqa: E402
from hyprtk_shot.app import create  # noqa: E402

problems: list[str] = []

IGNORED = (
    "QStandardPaths",
    "This plugin does not support",
    "Failed to create",
    "propagateSizeHints",
    "QObject::startTimer",
    "qt.qpa.wayland",
)


def handler(mode, context, message: str) -> None:
    if any(fragment in message for fragment in IGNORED):
        return
    problems.append(message)


def fail(message: str) -> None:
    problems.append(message)


def make_source(path: Path) -> None:
    image = QImage(640, 400, QImage.Format_RGB32)
    image.fill(QColor("#1e1e2e"))
    painter = QPainter(image)
    painter.fillRect(0, 0, 320, 200, QColor("#22d3ee"))
    painter.fillRect(320, 200, 320, 200, QColor("#c084fc"))
    painter.end()
    if not image.save(str(path)):
        raise SystemExit("could not write the test image")


def main() -> int:
    qInstallMessageHandler(handler)
    source = Path(_SANDBOX) / "source.png"
    make_source(source)

    app, engine, bridge = create([sys.argv[0]], open_path=str(source))
    root = engine.rootObjects()[0]

    if not bridge.overlayVisible:
        fail("the overlay did not open for an existing image")
    if bridge.imageInfo.get("width") != 640:
        fail(f"imageInfo is wrong: {bridge.imageInfo}")
    if bridge.selectionInfo.get("width") != 640:
        fail(f"the default selection is not the whole image: {bridge.selectionInfo}")

    # Annotations: add, undo, redo, and save a cropped selection.
    bridge.setSelection(20, 20, 200, 120)
    bridge.setTool("arrow")
    bridge.setColor("#f9e2af")
    bridge.addShapeObject(Shape(kind="arrow", points=[(30.0, 30.0), (200.0, 130.0)],
                                color="#f9e2af", width=6.0))
    if not bridge.canUndo:
        fail("an added shape did not enable undo")
    bridge.undo()
    if bridge.canUndo:
        fail("undo did not remove the shape")
    bridge.redo()
    if not bridge.canUndo:
        fail("redo did not restore the shape")

    path = bridge.save()
    if not path or not Path(path).is_file():
        fail(f"save wrote nothing: {path!r}")
    else:
        saved = QImage(path)
        if saved.width() != 200 or saved.height() != 120:
            fail(f"save did not crop to the selection: {saved.width()}x{saved.height()}")

    if not bridge.history.recent_paths(1):
        fail("the capture was not recorded in the history")

    # Palette roles the QML binds to must exist.
    palette = bridge.palette
    for key in ("background", "foreground", "accent", "accent2", "panel",
                "panelAlt", "panelHover", "textOnAccent", "muted", "border",
                "danger", "selection", "veil"):
        if key not in palette:
            fail(f"palette is missing {key!r}")

    bridge.close()
    if bridge.overlayVisible:
        fail("close() left the overlay visible")

    def finish() -> None:
        app.quit()

    QTimer.singleShot(200, finish)
    app.exec()

    if problems:
        for message in problems:
            print("PROBLEM:", message, file=sys.stderr)
        return 1
    print("bootcheck OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
