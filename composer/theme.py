"""Dark navy, cream, and orange — the same colors as the Composer logo."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from composer.paths import ROOT

NAVY = "#101C2B"
SIDEBAR = "#0C1622"
CARD = "#17283A"
INK = "#14283A"
CREAM = "#F4F0E6"
ORANGE = "#E08A30"
BLUE = "#2164A0"
BLUE_DEEP = "#173F6B"
LINE = "#1B527F"
MUTED = "#8FA3B8"
BORDER = "#2C4660"

STYLESHEET = """
QWidget#Root {
    background: #101C2B;
}
QFrame#Header {
    background: #101C2B;
}
QFrame#BrandBar {
    background: #E08A30;
    border: none;
}
QFrame#Sidebar {
    background: #0C1622;
    border: none;
}
QSplitter#BodySplit::handle {
    background: #24384C;
    width: 6px;
}
QScrollArea#SideScroll {
    background: #0C1622;
    border: none;
}
QWidget#SidebarInner {
    background: #0C1622;
}
QWidget#Main {
    background: #101C2B;
}
QFrame#Footer {
    background: #0C1622;
    border: none;
    border-top: 1px solid #24384C;
}
QFrame#EditorCard {
    background: #17283A;
    border: 1px solid #2C4660;
    border-radius: 12px;
}
QFrame#Segment {
    background: #0C1622;
    border: 1px solid #2C4660;
    border-radius: 10px;
}
QLabel {
    background: transparent;
    color: #F4F0E6;
}
QLabel#Subtitle, QLabel#Hint, QLabel#StatusMuted {
    color: #C5D2DE;
    font-size: 12px;
}
QLabel#Section {
    color: #F4F0E6;
    font-size: 13px;
    font-weight: 600;
}
QLabel#FieldLabel {
    color: #C5D0DB;
    font-size: 12px;
}
QLabel#DialogTitle {
    color: #F4F0E6;
    font-size: 18px;
    font-weight: 650;
}
QLabel#StatusOk { color: #8FD0B0; font-size: 12px; }
QLabel#StatusWarn { color: #E0B15A; font-size: 12px; }
QLabel#StatusError { color: #E07A70; font-size: 12px; }
QLabel#Wordmark {
    color: #F4F0E6;
    font-family: Georgia;
    font-size: 28px;
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #0C1622;
    color: #F4F0E6;
    border: 1px solid #2C4660;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: #2164A0;
    selection-color: #F4F0E6;
    min-height: 20px;
}
QPlainTextEdit#TemplateEdit {
    background: #17283A;
    border: none;
    font-size: 14px;
    padding: 2px;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #E08A30;
}
QPlainTextEdit#TemplateEdit:focus {
    border: none;
}
QComboBox {
    combobox-popup: 0;
    padding-right: 28px;
}
QComboBox QAbstractItemView {
    background: #17283A;
    color: #F4F0E6;
    selection-background-color: #2164A0;
    selection-color: #F4F0E6;
    border: 1px solid #2C4660;
    outline: 0;
    padding: 4px;
}
QCheckBox {
    color: #F4F0E6;
    background: transparent;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #C5D2DE;
    border-radius: 4px;
    background: #0C1622;
}
QCheckBox::indicator:hover {
    border-color: #E08A30;
}
QCheckBox::indicator:checked {
    background: #E08A30;
    border: 1px solid #E08A30;
    image: url(CHECK_ICON);
}
QPushButton {
    background: #17283A;
    color: #F4F0E6;
    border: 1px solid #3D5872;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 32px;
}
QPushButton:hover {
    border-color: #E08A30;
}
QPushButton:pressed {
    background: #122033;
}
QPushButton:disabled {
    color: #6E8296;
    border-color: #2A3E52;
    background: #122033;
}
QPushButton#PrimaryButton {
    background: #E08A30;
    color: #14283A;
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    min-height: 34px;
    font-weight: 650;
}
QPushButton#PrimaryButton:hover { background: #E99A45; }
QPushButton#PrimaryButton:pressed { background: #C97622; }
QPushButton#PrimaryButton:disabled,
QPushButton#SecondaryButton:disabled,
QPushButton#GhostButton:disabled,
QPushButton#PaperPrimary:disabled,
QPushButton#PaperSecondary:disabled,
QPushButton#FieldChip:disabled,
QPushButton#SegmentButton:disabled {
    color: #6E8296;
    border-color: #2A3E52;
    background: transparent;
}
QPushButton#PrimaryButton:disabled {
    background: #3A4C60;
    color: #8FA3B8;
}
QPushButton#SecondaryButton, QPushButton#GhostButton {
    background: transparent;
    color: #F4F0E6;
    border: 1px solid #3D5872;
    border-radius: 8px;
}
QPushButton#GhostButton {
    background: #17283A;
}
QPushButton#SecondaryButton:hover, QPushButton#GhostButton:hover {
    border-color: #E08A30;
}
QPushButton#FieldChip {
    background: #17283A;
    color: #F4F0E6;
    border: 1px solid #2C4660;
    border-radius: 12px;
    padding: 3px 10px;
    min-height: 24px;
    font-size: 12px;
}
QPushButton#FieldChip:hover {
    border-color: #E08A30;
}
QPushButton#SegmentButton {
    background: transparent;
    color: #8FA3B8;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 32px;
    font-weight: 600;
}
QPushButton#SegmentButton:hover {
    color: #F4F0E6;
}
QPushButton#SegmentButton[selected="true"] {
    background: #2164A0;
    color: #F4F0E6;
}
QPushButton#SegmentButton[selected="true"]:hover {
    background: #1B527F;
}
QPushButton#PaperPrimary {
    background: #E08A30;
    color: #14283A;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 650;
}
QPushButton#PaperPrimary:hover { background: #E99A45; }
QPushButton#PaperSecondary {
    background: transparent;
    color: #14283A;
    border: 1px solid #14283A;
    border-radius: 8px;
    padding: 8px 14px;
}
QPushButton#PaperSecondary:hover {
    background: #E7E1D4;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: #2C4660;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #3D5872; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0px; }
QScrollArea#SideScroll QScrollBar:horizontal {
    height: 12px;
    background: transparent;
    margin: 2px 4px;
}
QScrollArea#SideScroll QScrollBar::handle:horizontal {
    background: #2C4660;
    border-radius: 4px;
    min-width: 28px;
}
QScrollArea#SideScroll QScrollBar::add-line:horizontal,
QScrollArea#SideScroll QScrollBar::sub-line:horizontal { width: 0px; }
QTableView {
    background: #0C1622;
    alternate-background-color: #132433;
    color: #F4F0E6;
    gridline-color: #24384C;
    selection-background-color: #2164A0;
    selection-color: #F4F0E6;
    border: 1px solid #2C4660;
    border-radius: 8px;
}
QHeaderView::section {
    background: #17283A;
    color: #F4F0E6;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #24384C;
    border-bottom: 1px solid #24384C;
    font-weight: 600;
}
QTableCornerButton::section {
    background: #17283A;
    border: none;
}
QDialog { background: #101C2B; }
QMessageBox { background: #17283A; }
QMessageBox QLabel { color: #F4F0E6; background: transparent; }
QToolTip {
    background: #17283A;
    color: #F4F0E6;
    border: 1px solid #2C4660;
    padding: 6px 8px;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(NAVY))
    palette.setColor(QPalette.WindowText, QColor(CREAM))
    palette.setColor(QPalette.Base, QColor(SIDEBAR))
    palette.setColor(QPalette.AlternateBase, QColor(CARD))
    palette.setColor(QPalette.Text, QColor(CREAM))
    palette.setColor(QPalette.Button, QColor(CARD))
    palette.setColor(QPalette.ButtonText, QColor(CREAM))
    palette.setColor(QPalette.Highlight, QColor(BLUE))
    palette.setColor(QPalette.HighlightedText, QColor(CREAM))
    palette.setColor(QPalette.ToolTipBase, QColor(CARD))
    palette.setColor(QPalette.ToolTipText, QColor(CREAM))
    palette.setColor(QPalette.PlaceholderText, QColor(MUTED))
    muted = QColor("#6E8296")
    palette.setColor(QPalette.Disabled, QPalette.Text, muted)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, muted)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, muted)
    app.setPalette(palette)
    check_icon = (ROOT / "logo" / "check.png").as_posix()
    app.setStyleSheet(STYLESHEET.replace("CHECK_ICON", check_icon))
