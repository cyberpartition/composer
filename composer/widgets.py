"""Small layout pieces shared by the Composer window."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from composer.theme import CREAM


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def clear(self) -> None:
        while self.count():
            item = self.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        limit = effective.x() + effective.width()
        for item in self._items:
            item_width = item.sizeHint().width()
            if line_height > 0 and x + item_width > limit:
                x = effective.x()
                y = y + line_height + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = x + item_width + self._spacing
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + bottom


class FieldHost(QWidget):
    """Wraps column chips and grows tall enough for every row of them."""

    def __init__(self) -> None:
        super().__init__()
        self.flow = FlowLayout(self)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = max(1, self.width())
        height = max(0, self.flow.heightForWidth(width))
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)

    def refresh(self) -> None:
        width = self.width() if self.width() > 20 else 280
        self.setMinimumHeight(max(0, self.flow.heightForWidth(width)))
        self.updateGeometry()


class PaperCard(QFrame):
    """Cream sheet with the orange folded corner from the logo."""

    def __init__(self) -> None:
        super().__init__()
        self.setAutoFillBackground(False)
        self.setMinimumHeight(250)

    def paintEvent(self, event) -> None:
        painter_owner = QPainter(self)
        painter_owner.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        shape = QPainterPath()
        shape.addRoundedRect(rect, 10, 10)
        painter_owner.fillPath(shape, QColor(CREAM))
        painter_owner.setPen(QPen(QColor("#E4DCCB"), 1))
        painter_owner.drawPath(shape)
        painter_owner.setClipPath(shape)
        size = 18.0
        ear = QPainterPath()
        ear.moveTo(rect.right() - size, rect.top())
        ear.lineTo(rect.right(), rect.top())
        ear.lineTo(rect.right(), rect.top() + size)
        ear.closeSubpath()
        painter_owner.fillPath(ear, QColor("#E08A30"))
        painter_owner.setPen(QPen(QColor("#E7D7C0"), 1))
        painter_owner.drawLine(
            QPointF(rect.right() - size, rect.top() + 0.5),
            QPointF(rect.right() - 0.5, rect.top() + size),
        )
        painter_owner.end()


class ClickLabel(QLabel):
    clicked = Signal()

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setWordWrap(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setTextFormat(Qt.PlainText)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def make_button(text: str, name: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.setCursor(Qt.PointingHandCursor)
    return button


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Section")
    label.setTextFormat(Qt.PlainText)
    return label


def hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    label.setTextFormat(Qt.PlainText)
    return label


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    label.setTextFormat(Qt.PlainText)
    return label


def labeled(text: str, widget: QWidget) -> QWidget:
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(field_label(text))
    layout.addWidget(widget)
    return wrap


def ink_label(text: str, *, size: int, weight: int = 400, family: str = "Segoe UI") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.PlainText)
    label.setStyleSheet(
        "color: #14283A; background: transparent; "
        f"font-family: '{family}'; font-size: {size}px; font-weight: {weight};"
    )
    return label


def button_row(*widgets: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    return layout
