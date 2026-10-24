"""Render the Composer mark into a Windows icon."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    QApplication([])
    renderer = QSvgRenderer(str(ROOT / "logo" / "composer-mark.svg"))
    if not renderer.isValid():
        raise SystemExit("Could not read the Composer mark.")
    size = 256
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    margin = size * 0.08
    renderer.render(painter, QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    painter.end()
    png_path = ROOT / "packaging" / "composer-icon.png"
    image.save(str(png_path))
    icon = Image.open(png_path)
    icon.save(
        ROOT / "packaging" / "composer.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
