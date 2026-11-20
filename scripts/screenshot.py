#!/usr/bin/env python3
"""Dev-only: render the launcher and the overlay offscreen to PNGs.

    python3 scripts/screenshot.py docs/shot-overlay.png [docs/shot-launcher.png]

Not a screenshot of a real desktop (there is no compositor offscreen): it draws
a synthetic "desktop" image, opens the real QML against it, and grabs the
window. Useful for design review and the README.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

_SANDBOX = tempfile.mkdtemp(prefix="hyprtk-shot-shot-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_SANDBOX, "config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_SANDBOX, "cache")
os.environ["HYPRTK_WAL_HOME"] = _SANDBOX
os.environ["HYPRTK_SHOT_CONFIG_DIR"] = os.path.join(_SANDBOX, "config", "hyprtk-shot")
os.environ["HYPRTK_SHOT_DIR"] = os.path.join(_SANDBOX, "pictures")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402

from hyprtk_shot.annotate import Shape  # noqa: E402


def desktop_image(width: int = 1600, height: int = 900) -> QImage:
    """A fake desktop that reads like one at a glance."""
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("#171722"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    painter.fillRect(0, 0, width, 38, QColor("#101018"))
    painter.fillRect(0, height - 120, width, 120, QColor("#101018"))
    painter.fillRect(30, 60, width // 2 - 50, height - 210, QColor("#1e1e2e"))
    painter.fillRect(width // 2 + 20, 60, width // 2 - 50, 380, QColor("#232336"))
    painter.fillRect(width // 2 + 20, 470, width // 2 - 50, height - 620, QColor("#232336"))

    painter.setPen(QColor("#c084fc"))
    painter.setFont(_font(22, bold=True))
    painter.drawText(60, 110, "hyprtk-term")
    painter.setPen(QColor("#a6adc8"))
    painter.setFont(_font(15))
    for i, line in enumerate([
        "$ hyprtk-shot region",
        "freeze · select · annotate · save",
        "",
        "$ grim -o DP-1 -",
        "3840x1080  png  182 KB",
        "",
        "$ wf-recorder -g \"0,0 1920x1080\" -f demo.mp4",
    ]):
        painter.drawText(60, 150 + i * 26, line)

    painter.setPen(QColor("#22d3ee"))
    painter.setFont(_font(18, bold=True))
    painter.drawText(width // 2 + 50, 110, "Screenshot")
    painter.setFont(_font(13))
    painter.setPen(QColor("#a6adc8"))
    painter.drawText(width // 2 + 50, 140, "Region · Window · Monitor · All outputs")

    painter.setPen(QColor("#f9e2af"))
    painter.setFont(_font(18, bold=True))
    painter.drawText(width // 2 + 50, 520, "Recorder")
    painter.end()
    return image


def _font(size: int, bold: bool = False):
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamily("DejaVu Sans")
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def qquick(window):
    """engine.rootObjects() hands back a bare QWindow under PySide6; re-wrap it."""
    from PySide6.QtQuick import QQuickWindow
    from shiboken6 import getCppPointer, wrapInstance

    if hasattr(window, "grabWindow"):
        return window
    return wrapInstance(getCppPointer(window)[0], QQuickWindow)


def grab(window, path: Path, width: int, height: int) -> None:
    window = qquick(window)
    window.setGeometry(0, 0, width, height)
    path.parent.mkdir(parents=True, exist_ok=True)
    shot = window.grabWindow()
    if not shot.save(str(path)):
        raise SystemExit(f"could not write {path}")
    print(f"wrote {path} ({shot.width()}x{shot.height()})")


def main() -> int:
    overlay_out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "shot-overlay.png"
    launcher_out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "shot-launcher.png"

    source = Path(_SANDBOX) / "desktop.png"

    from PySide6.QtGui import QWindow

    from hyprtk_shot.app import create

    # One process can only own one QGuiApplication, so the launcher is grabbed
    # first and the overlay is opened afterwards. The synthetic desktop is drawn
    # after the application exists: QPainter.drawText needs the font database.
    app, engine, bridge = create([sys.argv[0]])
    root = engine.rootObjects()[0]
    desktop_image().save(str(source))

    def grab_launcher() -> None:
        print("stage: launcher", flush=True)
        grab(root, launcher_out, 560, 640)
        print("stage: openFile", flush=True)
        bridge.openFile(str(source))
        print("stage: queued overlay", flush=True)
        QTimer.singleShot(350, grab_overlay)

    def grab_overlay() -> None:
        print("stage: overlay", flush=True)
        windows = [w for w in QGuiApplication.topLevelWindows() if w.title() == "hyprtk-shot"]
        overlay = windows[0] if windows else None
        if overlay is None:
            print("no overlay window", file=sys.stderr)
            app.quit()
            return

        bridge.setSelection(180, 120, 820, 470)
        bridge.addShapeObject(Shape(kind="arrow", points=[(300.0, 250.0), (760.0, 340.0)],
                                    color="#fd4fb6", width=6.0))
        bridge.addShapeObject(Shape(kind="rect", points=[(700.0, 400.0), (960.0, 500.0)],
                                    color="#02dede", width=4.0))
        bridge.addShapeObject(Shape(kind="marker", points=[(260.0, 190.0)],
                                    color="#f9e2af", width=4.0))
        bridge.setTool("cursor")

        # Offscreen "fullscreen" is the platform's default size; go windowed so
        # the grab is a usable composition size.
        overlay.setVisibility(QWindow.Windowed)
        overlay.resize(1280, 720)
        print("stage: windowed", flush=True)
        QTimer.singleShot(300, lambda: finish(overlay))

    def finish(overlay) -> None:
        grab(overlay, overlay_out, 1280, 720)
        app.quit()

    QTimer.singleShot(300, grab_launcher)
    app.exec()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
