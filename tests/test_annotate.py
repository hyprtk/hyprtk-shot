import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402

from hyprtk_shot.annotate import (  # noqa: E402
    Shape,
    new_shape,
    render,
    render_to_png,
)

_app = QGuiApplication.instance() or QGuiApplication([])


def white(width=200, height=100):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("#ffffff"))
    return image


def pixel(image, x, y):
    return QColor(image.pixel(int(x), int(y)))


class ShapeModelTest(unittest.TestCase):
    def test_new_shape_rejects_the_cursor(self):
        with self.assertRaises(ValueError):
            new_shape("cursor", 1, 2, color="#ffffff", width=2)
        with self.assertRaises(ValueError):
            new_shape("nope", 1, 2, color="#ffffff", width=2)

    def test_bounds_are_normalised(self):
        shape = Shape(kind="rect", points=[(90, 70), (10, 20)])
        self.assertEqual(shape.bounds(), (10, 20, 80, 50))

    def test_roundtrip(self):
        shape = Shape(kind="arrow", points=[(1.5, 2.5), (3.0, 4.0)],
                      color="#fd4fb6", width=5.0, text="hi", filled=True)
        again = Shape.from_dict(shape.to_dict())
        self.assertEqual(again.kind, "arrow")
        self.assertEqual(again.points, [(1.5, 2.5), (3.0, 4.0)])
        self.assertEqual(again.color, "#fd4fb6")
        self.assertEqual(again.text, "hi")
        self.assertTrue(again.filled)


class RenderTest(unittest.TestCase):
    def test_render_does_not_mutate_the_source(self):
        base = white()
        shape = Shape(kind="rect", points=[(10, 10), (100, 80)], color="#ff0000", width=3)
        render(base, [shape])
        self.assertEqual(pixel(base, 10, 10), QColor("#ffffff"))

    def test_rectangle_draws_its_border_and_leaves_the_inside(self):
        base = white()
        shape = Shape(kind="rect", points=[(20, 20), (180, 80)], color="#ff0000", width=3)
        out = render(base, [shape])
        self.assertEqual(pixel(out, 20, 20).name(), "#ff0000")
        self.assertEqual(pixel(out, 100, 50).name(), "#ffffff")
        self.assertEqual(pixel(out, 5, 5).name(), "#ffffff")

    def test_ellipse_does_not_paint_the_bounding_box_corner(self):
        base = white()
        shape = Shape(kind="ellipse", points=[(20, 20), (180, 80)], color="#00ff00", width=3)
        out = render(base, [shape])
        self.assertEqual(pixel(out, 21, 21).name(), "#ffffff")
        self.assertEqual(pixel(out, 100, 20).name(), "#00ff00")

    def test_arrow_has_a_head(self):
        base = white()
        shape = Shape(kind="arrow", points=[(10, 50), (150, 50)], color="#0000ff", width=4)
        out = render(base, [shape])
        # A bare line would leave the pixel just above the tip white.
        self.assertEqual(pixel(out, 140, 47).name(), "#0000ff")

    def test_pen_draws_every_segment(self):
        base = white()
        shape = Shape(kind="pen", points=[(10, 10), (50, 50), (90, 10)],
                      color="#123456", width=3)
        out = render(base, [shape])
        self.assertEqual(pixel(out, 30, 30).name(), "#123456")
        self.assertEqual(pixel(out, 70, 30).name(), "#123456")

    def test_highlight_is_translucent(self):
        base = white()
        shape = Shape(kind="highlight", points=[(10, 50), (150, 50)],
                      color="#ff0000", width=4)
        out = render(base, [shape])
        got = pixel(out, 80, 50)
        self.assertNotEqual(got.name(), "#ff0000")
        self.assertLess(got.green(), 255)
        self.assertGreater(got.red(), 200)

    def test_marker_numbers_are_drawn_in_order(self):
        base = white()
        shapes = [
            Shape(kind="marker", points=[(30, 30)], color="#000000", width=4),
            Shape(kind="marker", points=[(150, 30)], color="#000000", width=4),
        ]
        one = render(base, shapes[:1])
        two = render(base, shapes)
        self.assertNotEqual(bytes(one.constBits()), bytes(two.constBits()))

    def test_blur_changes_the_patch_and_not_the_outside(self):
        base = QImage(200, 100, QImage.Format_RGB32)
        for x in range(200):
            for y in range(100):
                base.setPixelColor(x, y, QColor(255, 255, 255) if (x // 4 + y // 4) % 2 else QColor(0, 0, 0))
        shape = Shape(kind="blur", points=[(50, 20), (150, 80)], color="#000000", width=4)
        out = render(base, [shape])
        self.assertNotEqual(pixel(out, 60, 30), pixel(base, 60, 30))
        self.assertEqual(pixel(out, 5, 5), pixel(base, 5, 5))

    def test_pixelate_uses_large_blocks(self):
        base = QImage(200, 100, QImage.Format_RGB32)
        base.fill(QColor("#808080"))
        for x in range(100):
            for y in range(50):
                base.setPixelColor(x, y, QColor("#ffffff"))
        shape = Shape(kind="pixelate", points=[(40, 10), (160, 90)], color="#000000", width=4)
        out = render(base, [shape])
        colors = {pixel(out, x, y).name() for x in range(45, 150, 3) for y in range(15, 85, 3)}
        self.assertLessEqual(len(colors), 4)

    def test_text_is_painted(self):
        base = white()
        shape = Shape(kind="text", points=[(20, 60)], color="#000000", width=4, text="hello")
        out = render(base, [shape])
        darkened = sum(
            1 for x in range(15, 120) for y in range(30, 70)
            if pixel(out, x, y).value() < 200
        )
        self.assertGreater(darkened, 20)

    def test_scale_multiplies_the_stroke(self):
        base = white(400, 200)
        shape = Shape(kind="line", points=[(10, 100), (390, 100)], color="#000000", width=2)
        thin = render(base, [shape], scale=1.0)
        thick = render(base, [shape], scale=3.0)
        thin_rows = sum(1 for y in range(80, 120) if pixel(thin, 200, y).value() < 128)
        thick_rows = sum(1 for y in range(80, 120) if pixel(thick, 200, y).value() < 128)
        self.assertGreater(thick_rows, thin_rows)

    def test_png_bytes_are_a_png(self):
        data = render_to_png(white(), [])
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(data), 50)

    def test_unknown_kind_is_ignored(self):
        base = white()
        out = render(base, [Shape(kind="mystery", points=[(1, 1), (20, 20)])])
        self.assertEqual(pixel(out, 10, 10).name(), "#ffffff")


if __name__ == "__main__":
    unittest.main()
