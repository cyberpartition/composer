"""Draw the Composer logo sharply at the screen's pixel density."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QApplication

from composer.paths import logo_dark_png, logo_dark_svg, mark_svg


def screen_ratio() -> float:
    app = QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    return float(screen.devicePixelRatio() or 1.0)


def load_pixmap(path: Path, height: int) -> QPixmap:
    if not path.is_file():
        return QPixmap()
    ratio = screen_ratio()
    if path.suffix.lower() == ".svg":
        return _render_svg(path, height, ratio)
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaledToHeight(max(1, int(round(height * ratio))), Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(ratio)
    return scaled


def load_lockup(height: int = 44) -> tuple[QPixmap, bool]:
    """Return the logo and whether the pixmap already includes the word Composer."""
    for path in (logo_dark_svg(), logo_dark_png()):
        pixmap = load_pixmap(path, height)
        if not pixmap.isNull():
            return pixmap, True
    return paint_mark(height), False


def load_square_mark(size: int) -> QPixmap:
    ratio = screen_ratio()
    path = mark_svg()
    pixel = max(1, int(round(size * ratio)))
    if path.is_file():
        try:
            from PySide6.QtSvg import QSvgRenderer
        except ImportError:
            return paint_mark(size, ratio)
        renderer = QSvgRenderer(str(path))
        if renderer.isValid():
            image = QImage(pixel, pixel, QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing, True)
            margin = pixel * 0.06
            renderer.render(painter, QRectF(margin, margin, pixel - 2 * margin, pixel - 2 * margin))
            painter.end()
            image.setDevicePixelRatio(ratio)
            return QPixmap.fromImage(image)
    return paint_mark(size, ratio)


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 256):
        icon.addPixmap(load_square_mark(size))
    return icon


def logical_width(pixmap: QPixmap) -> int:
    ratio = pixmap.devicePixelRatio() or 1
    return max(1, int(round(pixmap.width() / ratio)))


def logical_height(pixmap: QPixmap) -> int:
    ratio = pixmap.devicePixelRatio() or 1
    return max(1, int(round(pixmap.height() / ratio)))


def paint_mark(height: int, ratio: float | None = None) -> QPixmap:
    ratio = screen_ratio() if ratio is None else ratio
    aspect = 48 / 60
    pixel_h = max(1, int(round(height * ratio)))
    pixel_w = max(1, int(round(pixel_h * aspect)))
    image = QImage(pixel_w, pixel_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.scale(pixel_h / 60, pixel_h / 60)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#173F6B"))
    painter.drawRoundedRect(QRectF(16, 1, 28, 38), 3.2, 3.2)
    painter.setBrush(QColor("#2164A0"))
    painter.drawRoundedRect(QRectF(9, 7, 28, 40), 3.2, 3.2)
    painter.setPen(QPen(QColor("#14283A"), 1.2))
    painter.setBrush(QColor("#F4F0E6"))
    painter.drawRoundedRect(QRectF(2, 13, 30, 42), 3.2, 3.2)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#1B527F"))
    for top, width in ((30, 14), (36, 18), (42, 10)):
        painter.drawRoundedRect(QRectF(6, top, width, 2.2), 1, 1)
    ear = QPainterPath()
    ear.moveTo(20, 13)
    ear.lineTo(32, 13)
    ear.lineTo(32, 25)
    ear.closeSubpath()
    painter.fillPath(ear, QColor("#E08A30"))
    painter.end()
    image.setDevicePixelRatio(ratio)
    return QPixmap.fromImage(image)


def _render_svg(path: Path, height: int, ratio: float) -> QPixmap:
    try:
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        return QPixmap()
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()
    box = renderer.viewBoxF()
    aspect = (box.width() / box.height()) if box.height() else 4.0
    pixel_h = max(1, int(round(height * ratio)))
    pixel_w = max(1, int(round(pixel_h * aspect)))
    image = QImage(pixel_w, pixel_h, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()
    image.setDevicePixelRatio(ratio)
    return QPixmap.fromImage(image)
