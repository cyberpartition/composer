"""Composer window: load a spreadsheet, preview the merge, and write drafts."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFontMetrics, QKeySequence, QPalette, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from composer import __version__
from composer.branding import app_icon, load_lockup, logical_height, logical_width
from composer.cities import NEAREST_CITY, computed_fields, nearest_city, normalize_zip
from composer.data import (
    EMAIL,
    EXAMPLE_BODY,
    EXAMPLE_SUBJECT,
    WORD,
    Table,
    closest_header,
    default_filename_pattern,
    find_header,
    guess_email_column,
    guess_zip_column,
    looks_like_email,
    record_title,
    render,
    safe_stem,
    single_line,
)
from composer.data import load_table
from composer.dialogs import DataDialog, SendDialog, ask, show_error, show_info
from composer.export import BatchReport, ExportJob, export_batch
from composer.paths import default_output_dir, sample_csv
from composer.settings import load_settings, save_settings
from composer.theme import CREAM
from composer.widgets import (
    FieldHost,
    PaperCard,
    hint_label,
    ink_label,
    labeled,
    make_button,
    repolish,
    section_label,
)


class GenerateWorker(QThread):
    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, job: ExportJob) -> None:
        super().__init__()
        self.job = job

    def run(self) -> None:
        try:
            report = export_batch(
                self.job,
                progress=lambda done, total: self.progress.emit(done, total),
                cancel=self.isInterruptionRequested,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(report)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Root")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(f"Composer {__version__}")
        self.setMinimumSize(1040, 720)
        self.setAcceptDrops(True)
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.table: Table | None = None
        self.record_index = 0
        self.last_report: BatchReport | None = None
        self._kind = EMAIL
        self._busy = False
        self._batch_sent = False
        self._programmatic = 0
        self._body_edited = False
        self._subject_edited = False
        self._filename_edited = False
        self._preferred_recipient = ""
        self._preferred_zip = ""
        self._smtp_password = ""
        self._smtp: dict[str, object] = {
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "",
        }
        self._worker: GenerateWorker | None = None
        self._insert_target: QWidget | None = None
        self._shortcuts: list[QShortcut] = []
        self._did_show = False
        self._fitting_chips = False
        self._sidebar_width = 420
        self._restored_geometry = False
        self._settings = load_settings()

        self._build()
        self._apply_settings(self._settings)
        self._show_idle_status()
        QTimer.singleShot(0, self._restore_last_source)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        bar = QFrame()
        bar.setObjectName("BrandBar")
        bar.setFixedHeight(4)
        bar.setAttribute(Qt.WA_StyledBackground, True)
        root.addWidget(bar)
        root.addWidget(self._build_header())
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("BodySplit")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._build_sidebar())
        self.splitter.addWidget(self._build_main())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        root.addWidget(self.splitter, 1)
        root.addWidget(self._build_footer())
        self._install_shortcuts()
        for widget in (self.subject_edit, self.body_edit, self.filename_edit):
            widget.installEventFilter(self)
        self._insert_target = self.body_edit

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        header.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(14)
        pixmap, includes_word = load_lockup(44)
        self.logo = QLabel()
        if not pixmap.isNull():
            self.logo.setPixmap(pixmap)
            self.logo.setFixedSize(logical_width(pixmap), logical_height(pixmap))
        layout.addWidget(self.logo, 0, Qt.AlignVCenter)
        if not includes_word:
            word = QLabel("Composer")
            word.setObjectName("Wordmark")
            layout.addWidget(word, 0, Qt.AlignVCenter)
        subtitle = QLabel(
            "Save a folder of email or Word drafts from a spreadsheet. Nothing is sent unless you confirm."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        subtitle.setTextFormat(Qt.PlainText)
        layout.addWidget(subtitle, 1, Qt.AlignVCenter)
        version = QLabel(__version__)
        version.setObjectName("Hint")
        version.setTextFormat(Qt.PlainText)
        layout.addWidget(version, 0, Qt.AlignVCenter)
        return header

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        self.sidebar = sidebar
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(720)
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        self.side_scroll = QScrollArea()
        self.side_scroll.setObjectName("SideScroll")
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        viewport = self.side_scroll.viewport()
        viewport_palette = viewport.palette()
        viewport_palette.setColor(QPalette.Window, QColor("#0C1622"))
        viewport.setPalette(viewport_palette)
        viewport.setAutoFillBackground(True)
        inner = QWidget()
        inner.setObjectName("SidebarInner")
        inner.setAttribute(Qt.WA_StyledBackground, True)
        inner.setMinimumWidth(0)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 18)
        layout.setSpacing(8)

        layout.addWidget(section_label("Source"))
        self.path_edit = self._line("")
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No file selected")
        layout.addWidget(self.path_edit)
        self.browse_btn = make_button("Browse for a file", "GhostButton")
        self.sample_btn = make_button("Load sample", "GhostButton")
        self.view_btn = make_button("View rows", "GhostButton")
        for button in (self.browse_btn, self.sample_btn, self.view_btn):
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setMinimumWidth(0)
        layout.addWidget(self.browse_btn)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.sample_btn)
        row.addWidget(self.view_btn)
        layout.addLayout(row)
        self.sheet_combo = QComboBox()
        self.sheet_wrap = labeled("Sheet", self.sheet_combo)
        self.sheet_wrap.setVisible(False)
        layout.addWidget(self.sheet_wrap)
        self.source_summary = hint_label("No spreadsheet loaded.")
        layout.addWidget(self.source_summary)
        layout.addWidget(hint_label("The first row should be the column names. You can also drop a file here."))

        layout.addSpacing(8)
        layout.addWidget(section_label("Fields"))
        self.insert_hint = hint_label("Load a spreadsheet, then click a column to insert it.")
        layout.addWidget(self.insert_hint)
        self.field_host = FieldHost()
        layout.addWidget(self.field_host)
        self.zip_combo = QComboBox()
        self.zip_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(labeled("ZIP column", self.zip_combo))
        layout.addWidget(
            hint_label(
                "Nearest City is the closest of the 56 FBI field offices. "
                "It is calculated on this computer."
            )
        )
        self._fill_zip()
        self._fill_fields()

        layout.addSpacing(8)
        layout.addWidget(section_label("Save to"))
        self.output_dir = self._line("")
        self.output_browse = make_button("Browse", "GhostButton")
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self.output_dir, 1)
        folder_row.addWidget(self.output_browse)
        layout.addLayout(folder_row)
        layout.addWidget(hint_label("Each run creates a new dated folder inside this one."))
        self.create_zip = QCheckBox("Also create a .zip of the generated files")
        layout.addWidget(self.create_zip)
        self.filename_edit = self._line("[Last Name]_[First Name]")
        layout.addWidget(labeled("File name", self.filename_edit))
        self.filename_preview = hint_label("Each row becomes its own file.")
        layout.addWidget(self.filename_preview)

        self.from_name = self._line("")
        self.from_email = self._line("Optional")
        self.identity_row = QWidget()
        identity = QVBoxLayout(self.identity_row)
        identity.setContentsMargins(0, 8, 0, 0)
        identity.setSpacing(6)
        pair = QHBoxLayout()
        pair.setSpacing(8)
        pair.addWidget(labeled("From name", self.from_name))
        pair.addWidget(labeled("From email", self.from_email))
        identity.addLayout(pair)
        identity.addWidget(hint_label("Optional. Written into the draft only. Not used unless you send."))
        layout.addWidget(self.identity_row)
        layout.addStretch(1)

        self.side_scroll.setWidget(inner)
        outer.addWidget(self.side_scroll)

        self.browse_btn.clicked.connect(self.browse_source)
        self.sample_btn.clicked.connect(self.load_sample)
        self.view_btn.clicked.connect(self.view_rows)
        self.output_browse.clicked.connect(self.browse_output)
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)
        self.filename_edit.textEdited.connect(self._on_filename_edited)
        self.filename_edit.textChanged.connect(self._sync_filename_preview)
        self.zip_combo.currentIndexChanged.connect(self._on_zip_changed)
        self.sample_btn.setVisible(sample_csv().is_file())
        return sidebar

    def _build_main(self) -> QWidget:
        main = QWidget()
        main.setObjectName("Main")
        main.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(main)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(10)

        self.email_btn = make_button("Email drafts", "SegmentButton")
        self.word_btn = make_button("Word documents", "SegmentButton")
        self.email_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.word_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        segment = QFrame()
        segment.setObjectName("Segment")
        segment.setAttribute(Qt.WA_StyledBackground, True)
        segment_row = QHBoxLayout(segment)
        segment_row.setContentsMargins(4, 4, 4, 4)
        segment_row.setSpacing(4)
        segment_row.addWidget(self.email_btn)
        segment_row.addWidget(self.word_btn)
        layout.addWidget(segment)
        self.kind_hint = hint_label("One .eml file per row. Nothing is sent when you generate.")
        layout.addWidget(self.kind_hint)

        self.recipient = QComboBox()
        self.recipient.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.subject_edit = self._line("Hello [First Name]")
        self.subject_row = QWidget()
        subject_layout = QHBoxLayout(self.subject_row)
        subject_layout.setContentsMargins(0, 0, 0, 0)
        subject_layout.setSpacing(8)
        recipient_wrap = labeled("Email column", self.recipient)
        recipient_wrap.setFixedWidth(230)
        subject_layout.addWidget(recipient_wrap)
        subject_layout.addWidget(labeled("Subject", self.subject_edit), 1)
        layout.addWidget(self.subject_row)

        card = QFrame()
        card.setObjectName("EditorCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)
        toolbar = QHBoxLayout()
        toolbar.addWidget(section_label("Message"))
        toolbar.addStretch(1)
        self.example_btn = make_button("Insert example", "GhostButton")
        self.clear_btn = make_button("Clear", "GhostButton")
        toolbar.addWidget(self.example_btn)
        toolbar.addWidget(self.clear_btn)
        card_layout.addLayout(toolbar)
        self.body_edit = QPlainTextEdit()
        self.body_edit.setObjectName("TemplateEdit")
        self.body_edit.setPlaceholderText("Write the message here. Click a column on the left to insert it.")
        self.body_edit.setMinimumHeight(120)
        card_layout.addWidget(self.body_edit, 1)
        layout.addWidget(card, 1)

        preview_head = QHBoxLayout()
        preview_head.addWidget(section_label("Preview"))
        preview_head.addStretch(1)
        self.prev_btn = make_button("‹", "GhostButton")
        self.next_btn = make_button("›", "GhostButton")
        self.prev_btn.setFixedWidth(36)
        self.next_btn.setFixedWidth(36)
        self.prev_btn.setToolTip("Previous row")
        self.next_btn.setToolTip("Next row")
        self.position_label = QLabel("1 of 1")
        self.position_label.setObjectName("FieldLabel")
        self.position_label.setTextFormat(Qt.PlainText)
        self.nav_box = QWidget()
        nav = QHBoxLayout(self.nav_box)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(6)
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.position_label)
        nav.addWidget(self.next_btn)
        preview_head.addWidget(self.nav_box)
        layout.addLayout(preview_head)

        self.paper = PaperCard()
        paper_layout = QVBoxLayout(self.paper)
        paper_layout.setContentsMargins(18, 16, 28, 16)
        paper_layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty_state())
        self.stack.addWidget(self._build_preview_page())
        paper_layout.addWidget(self.stack)
        layout.addWidget(self.paper)
        self.unknown_label = QLabel("")
        self.unknown_label.setObjectName("StatusWarn")
        self.unknown_label.setWordWrap(True)
        self.unknown_label.setTextFormat(Qt.PlainText)
        self.unknown_label.setVisible(False)
        layout.addWidget(self.unknown_label)

        self.email_btn.clicked.connect(lambda: self.set_kind(EMAIL))
        self.word_btn.clicked.connect(lambda: self.set_kind(WORD))
        self.example_btn.clicked.connect(self.insert_example)
        self.clear_btn.clicked.connect(self.clear_message)
        self.prev_btn.clicked.connect(self.prev_record)
        self.next_btn.clicked.connect(self.next_record)
        self.recipient.currentIndexChanged.connect(self._on_recipient_changed)
        self.subject_edit.textEdited.connect(self._on_subject_edited)
        self.subject_edit.textChanged.connect(self.refresh_preview)
        self.body_edit.textChanged.connect(self._on_body_changed)
        return main

    def _build_empty_state(self) -> QWidget:
        page = QWidget()
        self._paint_cream(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addStretch(1)
        title = ink_label("Compose from a spreadsheet", size=22, weight=700, family="Georgia")
        title.setAlignment(Qt.AlignHCenter)
        body = ink_label(
            "Open a CSV or Excel file with one person per row. Tokens such as [First Name] "
            "are filled from the columns. Composer saves a folder of drafts and does not send "
            "email unless you confirm.",
            size=13,
        )
        body.setAlignment(Qt.AlignHCenter)
        body.setMaximumWidth(560)
        layout.addWidget(title, 0, Qt.AlignHCenter)
        layout.addWidget(body, 0, Qt.AlignHCenter)
        self.paper_sample_btn = make_button("Load the sample", "PaperPrimary")
        self.paper_browse_btn = make_button("Browse for a file", "PaperSecondary")
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        buttons.addWidget(self.paper_sample_btn)
        buttons.addWidget(self.paper_browse_btn)
        buttons.addStretch(1)
        layout.addSpacing(6)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self.paper_sample_btn.setVisible(sample_csv().is_file())
        self.paper_sample_btn.clicked.connect(self.load_sample)
        self.paper_browse_btn.clicked.connect(self.browse_source)
        return page

    def _build_preview_page(self) -> QWidget:
        page = QWidget()
        self._paint_cream(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 0, 6, 0)
        layout.setSpacing(3)
        self.draft_kicker = ink_label("Email draft", size=11, weight=700)
        self.who_label = ink_label("Draft", size=18, weight=700, family="Georgia")
        self.meta_label = ink_label("", size=12)
        self.subject_preview = ink_label("", size=14, weight=700, family="Georgia")
        self.row_warning = QLabel("")
        self.row_warning.setWordWrap(True)
        self.row_warning.setTextFormat(Qt.PlainText)
        self.row_warning.setStyleSheet("color: #8A4B12; background: transparent; font-size: 12px;")
        self.row_warning.setVisible(False)
        self.preview_line = QFrame()
        self.preview_line.setFixedHeight(1)
        self.preview_line.setStyleSheet("background: #E4DCCB; border: none;")
        self.preview_line.setAttribute(Qt.WA_StyledBackground, True)
        self.preview_body = QTextEdit()
        self.preview_body.setReadOnly(True)
        self.preview_body.setFrameShape(QFrame.NoFrame)
        self.preview_body.setMinimumHeight(96)
        self.preview_body.setStyleSheet(
            "QTextEdit { color: #14283A; background: #F4F0E6; border: none; font-family: Georgia; font-size: 15px; }"
        )
        palette = self.preview_body.palette()
        palette.setColor(QPalette.Base, QColor(CREAM))
        palette.setColor(QPalette.Text, QColor("#14283A"))
        self.preview_body.setPalette(palette)
        self.preview_body.viewport().setAutoFillBackground(True)
        self.preview_body.viewport().setPalette(palette)
        layout.addWidget(self.draft_kicker)
        layout.addWidget(self.who_label)
        layout.addWidget(self.meta_label)
        layout.addWidget(self.subject_preview)
        layout.addWidget(self.row_warning)
        layout.addWidget(self.preview_line)
        layout.addWidget(self.preview_body, 1)
        return page

    def _build_footer(self) -> QWidget:
        footer = QFrame()
        footer.setObjectName("Footer")
        footer.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setObjectName("StatusMuted")
        layout.addWidget(self.status_label, 1)
        self.open_btn = make_button("Open folder", "SecondaryButton")
        self.send_btn = make_button("Send all...", "SecondaryButton")
        self.generate_btn = make_button("Generate emails", "PrimaryButton")
        self.open_btn.setMinimumWidth(120)
        self.send_btn.setMinimumWidth(120)
        self.generate_btn.setMinimumWidth(168)
        self.open_btn.setToolTip("Open the folder of drafts after you generate them.")
        self.send_btn.setToolTip("Send the drafts you just generated. Composer asks you to confirm first.")
        layout.addWidget(self.open_btn)
        layout.addWidget(self.send_btn)
        layout.addWidget(self.generate_btn)
        self.open_btn.clicked.connect(self.open_folder)
        self.send_btn.clicked.connect(self.open_send)
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        return footer

    def _install_shortcuts(self) -> None:
        open_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Open), self)
        open_shortcut.activated.connect(self.browse_source)
        generate_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        generate_shortcut.activated.connect(self.on_generate_clicked)
        self._shortcuts.extend([open_shortcut, generate_shortcut])

    def _line(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return edit

    def _paint_cream(self, widget: QWidget) -> None:
        palette = widget.palette()
        palette.setColor(QPalette.Window, QColor(CREAM))
        widget.setPalette(palette)
        widget.setAutoFillBackground(True)

    @contextmanager
    def _editing(self):
        self._programmatic += 1
        try:
            yield
        finally:
            self._programmatic -= 1

    def _apply_settings(self, settings: dict[str, object]) -> None:
        self._smtp = {
            "smtp_host": str(settings.get("smtp_host") or ""),
            "smtp_port": settings.get("smtp_port") or 587,
            "smtp_security": str(settings.get("smtp_security") or "starttls"),
            "smtp_username": str(settings.get("smtp_username") or ""),
        }
        self._preferred_recipient = str(settings.get("recipient_column") or "")
        self._preferred_zip = str(settings.get("zip_column") or "")
        try:
            self._sidebar_width = int(settings.get("sidebar_width") or 420)
        except (TypeError, ValueError):
            self._sidebar_width = 420
        self._sidebar_width = max(280, min(720, self._sidebar_width))
        with self._editing():
            if settings.get("body_edited"):
                self.body_edit.setPlainText(str(settings.get("body") or ""))
                self._body_edited = True
            else:
                self.body_edit.setPlainText(EXAMPLE_BODY)
            if settings.get("subject_edited"):
                self.subject_edit.setText(str(settings.get("subject") or ""))
                self._subject_edited = True
            else:
                self.subject_edit.setText(EXAMPLE_SUBJECT)
            if settings.get("filename_edited"):
                self.filename_edit.setText(str(settings.get("filename_pattern") or ""))
                self._filename_edited = True
            self.from_name.setText(str(settings.get("from_name") or ""))
            self.from_email.setText(str(settings.get("from_email") or ""))
            output = str(settings.get("output_dir") or "") or str(default_output_dir())
            self.output_dir.setText(output)
            self.create_zip.setChecked(bool(settings.get("create_zip")))
        self._restored_geometry = self._restore_geometry(settings.get("geometry"))
        self.set_kind(WORD if settings.get("kind") == WORD else EMAIL)

    def _restore_geometry(self, encoded: object) -> bool:
        if not isinstance(encoded, str) or not encoded:
            self.resize(1280, 900)
            return False
        try:
            restored = self.restoreGeometry(QByteArray.fromHex(encoded.encode("ascii")))
        except (ValueError, TypeError):
            restored = False
        if not restored:
            self.resize(1280, 900)
        return bool(restored)

    def _restore_last_source(self) -> None:
        raw = str(self._settings.get("source") or "")
        sheet = str(self._settings.get("sheet") or "") or None
        if raw and Path(raw).is_file():
            self.load_file(raw, sheet=sheet)

    def _save_settings(self) -> None:
        save_settings(
            {
                "geometry": bytes(self.saveGeometry()).hex(),
                "sidebar_width": self.splitter.sizes()[0] if self.splitter.sizes() else self._sidebar_width,
                "source": str(self.table.source) if self.table else "",
                "sheet": (self.table.sheet or "") if self.table else "",
                "output_dir": self.output_dir.text().strip(),
                "create_zip": self.create_zip.isChecked(),
                "kind": self._kind,
                "subject": self.subject_edit.text() if self._subject_edited else "",
                "body": self.body_edit.toPlainText() if self._body_edited else "",
                "filename_pattern": self.filename_edit.text() if self._filename_edited else "",
                "recipient_column": self._preferred_recipient,
                "zip_column": self._preferred_zip,
                "from_name": self.from_name.text().strip(),
                "from_email": self.from_email.text().strip(),
                "smtp_host": self._smtp.get("smtp_host", ""),
                "smtp_port": self._smtp.get("smtp_port", 587),
                "smtp_security": self._smtp.get("smtp_security", "starttls"),
                "smtp_username": self._smtp.get("smtp_username", ""),
                "body_edited": self._body_edited,
                "subject_edited": self._subject_edited,
                "filename_edited": self._filename_edited,
            }
        )

    def set_kind(self, kind: str) -> None:
        self._kind = WORD if kind == WORD else EMAIL
        email = self._kind == EMAIL
        self.email_btn.setProperty("selected", email)
        self.word_btn.setProperty("selected", not email)
        repolish(self.email_btn)
        repolish(self.word_btn)
        self.subject_row.setVisible(email)
        self.identity_row.setVisible(email)
        self.send_btn.setVisible(email)
        self.kind_hint.setText(
            "One .eml file per row. Nothing is sent when you generate."
            if email
            else "One Word document per row."
        )
        if email:
            self._show_idle_status()
        else:
            self._hide_send_status()
        self._sync_actions()
        self.refresh_preview()

    def load_file(self, path: str | Path, sheet: str | None = None) -> None:
        if self._busy:
            return
        try:
            table = load_table(path, sheet=sheet)
        except Exception as exc:
            show_error(self, str(exc))
            return
        self.table = table
        self.record_index = 0
        self._fill_sheets()
        self._fill_recipient()
        self._fill_zip()
        self._fill_fields()
        self._show_source()
        if not self._filename_edited:
            with self._editing():
                self.filename_edit.setText(default_filename_pattern(table.headers))
        self.setWindowTitle(f"Composer {__version__} — {table.source.name}")
        self.refresh_preview()
        self._sync_actions()
        loaded = f"Loaded {len(table.records)} records from {table.source.name}."
        if self._kind == EMAIL:
            loaded += " Nothing has been sent."
        self.set_status(loaded)

    def load_sample(self) -> None:
        path = sample_csv()
        if path.is_file():
            self.load_file(path)

    def browse_source(self) -> None:
        if self._busy:
            return
        start = str(self.table.source.parent) if self.table else str(Path.home())
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            "Open a spreadsheet",
            start,
            "Spreadsheets (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)",
        )
        if chosen:
            self.load_file(chosen)

    def browse_output(self) -> None:
        if self._busy:
            return
        current = self.output_dir.text().strip()
        start = current if current and Path(current).is_dir() else str(default_output_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Choose where Composer should save drafts", start)
        if chosen:
            self.output_dir.setText(chosen)

    def view_rows(self) -> None:
        if self.table is None or self._busy:
            return
        DataDialog(self, self.table).exec()

    def insert_example(self) -> None:
        if self._busy:
            return
        current = self.body_edit.toPlainText()
        if current.strip() and current != EXAMPLE_BODY:
            if not ask(self, "Replace the current message with the example?"):
                return
        with self._editing():
            self.body_edit.setPlainText(EXAMPLE_BODY)
        self._body_edited = True
        if not self.subject_edit.text().strip():
            with self._editing():
                self.subject_edit.setText(EXAMPLE_SUBJECT)
        self.refresh_preview()

    def clear_message(self) -> None:
        if self._busy:
            return
        cursor = self.body_edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self._body_edited = True
        self.body_edit.setFocus()

    def insert_token(self, token: str) -> None:
        if self._busy:
            return
        target = self._insert_target or self.body_edit
        if isinstance(target, QLineEdit):
            target.insert(token)
        else:
            target.insertPlainText(token)
        target.setFocus()

    def prev_record(self) -> None:
        if self.table is None or self.record_index <= 0:
            return
        self.record_index -= 1
        self.refresh_preview()

    def next_record(self) -> None:
        if self.table is None or self.record_index >= len(self.table.records) - 1:
            return
        self.record_index += 1
        self.refresh_preview()

    def refresh_preview(self) -> None:
        if self.table is None:
            self.stack.setCurrentIndex(0)
            self.nav_box.setVisible(False)
            self.unknown_label.setVisible(False)
            self._sync_filename_preview()
            return
        self.stack.setCurrentIndex(1)
        self.nav_box.setVisible(True)
        total = len(self.table.records)
        self.record_index = max(0, min(self.record_index, total - 1))
        record = self.table.records[self.record_index]
        row_number = self.record_index + 1
        self.position_label.setText(f"{row_number} of {total}")
        self.prev_btn.setEnabled(self.record_index > 0 and not self._busy)
        self.next_btn.setEnabled(self.record_index < total - 1 and not self._busy)
        extras = self._extras(record)
        body = render(self.body_edit.toPlainText(), record, self.table.headers, row_number, extras)
        subject = render(self.subject_edit.text(), record, self.table.headers, row_number, extras)
        self.who_label.setText(record_title(record, self.table.headers))
        if self.preview_body.toPlainText() != body.text:
            self.preview_body.setPlainText(body.text)
        email = self._kind == EMAIL
        self.draft_kicker.setText("Email draft" if email else "Word document")
        self.meta_label.setVisible(email)
        self.subject_preview.setVisible(email)
        if email:
            recipient = record.get(self._recipient_column(), "")
            self.meta_label.setText(f"To:  {recipient or '(no email)'}")
            self.subject_preview.setText(f"Subject:  {subject.text.strip() or '(none)'}")
            invalid = not looks_like_email(recipient)
            city_note = "" if invalid else self._city_note(record)
            self.row_warning.setVisible(invalid or bool(city_note))
            if invalid:
                self.row_warning.setText("This row will be skipped because the email address is missing or not valid.")
            else:
                self.row_warning.setText(city_note)
        else:
            city_note = self._city_note(record)
            self.row_warning.setVisible(bool(city_note))
            self.row_warning.setText(city_note)
        unknown = list(dict.fromkeys([*body.unknown, *subject.unknown]))
        if unknown:
            self.unknown_label.setText(self._unknown_message(unknown))
            self.unknown_label.setVisible(True)
        else:
            self.unknown_label.setVisible(False)
        self._sync_filename_preview()

    def preview_plain(self) -> str:
        return self.preview_body.toPlainText()

    def preview_subject(self) -> str:
        return self.subject_preview.text()

    def on_generate_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.generate_btn.setEnabled(False)
            stopping = "Stopping… drafts already written will stay in the folder."
            if self._kind == EMAIL:
                stopping += " Nothing will be sent."
            self.set_status(stopping, "warn")
            return
        self._start_generate()

    def open_folder(self) -> None:
        if self.last_report is None or not self.last_report.folder.is_dir():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_report.folder)))

    def open_send(self) -> None:
        if self._kind != EMAIL or self.last_report is None or self.last_report.kind != EMAIL:
            show_info(
                self,
                "Generate email drafts first. Composer saves them in a folder so you can review them. Nothing has been sent.",
            )
            return
        files = [draft.path for draft in self.last_report.written if draft.path.is_file()]
        if not files:
            show_info(self, "Those drafts are no longer in the folder. Generate them again if you still want to send.")
            return
        dialog = SendDialog(
            self,
            files=files,
            folder=self.last_report.folder,
            from_name=self.from_name.text(),
            from_email=self.from_email.text(),
            smtp=self._smtp,
            password=self._smtp_password,
        )
        dialog.exec()
        remembered, password = dialog.memory()
        self._smtp_password = password
        self._smtp = {
            "smtp_host": remembered["smtp_host"],
            "smtp_port": remembered["smtp_port"],
            "smtp_security": remembered["smtp_security"],
            "smtp_username": remembered["smtp_username"],
        }
        self.from_name.setText(str(remembered["from_name"]))
        self.from_email.setText(str(remembered["from_email"]))
        try:
            self._save_settings()
        except OSError:
            pass
        if dialog.sent_count:
            self._batch_sent = True
            if dialog.fail_count:
                self.set_status(
                    f"Sent {dialog.sent_count}. {dialog.fail_count} failed. Nothing else was sent.",
                    "warn",
                )
            else:
                self.set_status(f"Sent {dialog.sent_count} emails.", "ok")
        self._sync_actions()

    def _show_idle_status(self) -> None:
        if self._kind != EMAIL:
            self._hide_send_status()
            return
        current = self.status_label.text()
        if not current.strip() or "sent" in current.casefold() or "send" in current.casefold():
            self.set_status("Nothing is sent unless you choose Send all and confirm.")

    def _hide_send_status(self) -> None:
        text = self.status_label.text()
        for phrase in (
            " Nothing is sent unless you choose Send all and confirm.",
            " Nothing has been sent.",
            " Nothing was sent.",
            " Nothing will be sent.",
            " Nothing else was sent.",
        ):
            text = text.replace(phrase, "")
        text = text.strip()
        if text.casefold().startswith("nothing ") and "sent" in text.casefold():
            text = ""
        self.set_status(text)

    def set_status(self, text: str, tone: str = "muted") -> None:
        names = {
            "muted": "StatusMuted",
            "ok": "StatusOk",
            "warn": "StatusWarn",
            "error": "StatusError",
        }
        self.status_label.setObjectName(names.get(tone, "StatusMuted"))
        self.status_label.setText(text)
        repolish(self.status_label)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._did_show:
            self._did_show = True
            if not self._restored_geometry:
                self._center()
            self._apply_sidebar_width()
            QTimer.singleShot(0, self._fit_chips)

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            if not ask(self, "Composer is still writing files. Stop and close?"):
                event.ignore()
                return
            self._worker.requestInterruption()
            self._worker.wait(4000)
        try:
            self._save_settings()
        except OSError:
            pass
        event.accept()

    def dragEnterEvent(self, event) -> None:
        if not self._busy and self._dropped_spreadsheet(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        path = self._dropped_spreadsheet(event)
        if path and not self._busy:
            self.load_file(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.FocusIn and watched in (self.subject_edit, self.body_edit, self.filename_edit):
            self._insert_target = watched
            self._update_insert_hint()
        return super().eventFilter(watched, event)

    def _start_generate(self) -> None:
        if self._busy:
            return
        if self.table is None:
            show_error(self, "Load a CSV or Excel file first.")
            return
        if not self.body_edit.toPlainText().strip():
            show_error(self, "Write a message first. Click a column name to insert it, or use the example.")
            return
        from_email = single_line(self.from_email.text())
        if from_email and not looks_like_email(from_email):
            show_error(
                self,
                "The From email address does not look valid. Clear it, or enter an address like name@example.com.",
            )
            return
        if self._kind == EMAIL:
            column = self._recipient_column()
            if not column:
                show_error(self, "Choose the column that contains email addresses.")
                return
            if not any(looks_like_email(record.get(column, "")) for record in self.table.records):
                show_error(
                    self,
                    f'None of the rows have a valid email address in the column "{column}". '
                    "Choose the email column and try again.",
                )
                return
        output = Path(self.output_dir.text().strip() or default_output_dir())
        if output.exists() and not output.is_dir():
            show_error(self, "The output location is a file. Choose a folder instead.")
            return
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            show_error(self, f"Could not create the output folder.\n{exc}")
            return

        notes: list[str] = []
        if self._kind == EMAIL and not self.subject_edit.text().strip():
            notes.append("The subject is empty.")
        probe = render(
            "\n".join((self.body_edit.toPlainText(), self.subject_edit.text(), self.filename_edit.text())),
            self.table.records[0],
            self.table.headers,
            1,
            self._extras(self.table.records[0]),
        )
        if probe.unknown:
            notes.append("These tokens do not match a column: " + ", ".join(probe.unknown) + ".")
        if notes:
            question = "Generate these drafts anyway?\n\n" + "\n".join(f"• {note}" for note in notes)
            question += "\n\nNothing will be sent."
            if not ask(self, question):
                return

        job = ExportJob(
            kind=self._kind,
            headers=list(self.table.headers),
            records=[dict(record) for record in self.table.records],
            source_name=self.table.source.name,
            output_dir=output,
            subject_template=self.subject_edit.text(),
            body_template=self.body_edit.toPlainText(),
            filename_template=self.filename_edit.text(),
            recipient_column=self._recipient_column(),
            zip_column=self._zip_column(),
            from_name=single_line(self.from_name.text()),
            from_email=from_email,
            create_zip=self.create_zip.isChecked(),
        )
        self._set_busy(True)
        self._worker = GenerateWorker(job)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_generated)
        self._worker.failed.connect(self._on_generate_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        noun = "email drafts" if self._kind == EMAIL else "documents"
        self.set_status(f"Writing {done} of {total} {noun}…")

    def _on_generated(self, report: object) -> None:
        if not isinstance(report, BatchReport):
            return
        self.last_report = report
        self._batch_sent = False
        count = len(report.written)
        skipped = len(report.skipped)
        kind = "email draft" if report.kind == EMAIL else "document"
        if count != 1:
            kind += "s"
        sent_note = "" if report.kind == WORD else " Nothing was sent."
        zip_note = f' Zip file: "{report.archive.name}".' if report.archive else ""
        if report.cancelled:
            message = f'Stopped early. Saved {count} {kind} in "{report.folder.name}".{zip_note}{sent_note}'
            tone = "warn"
        elif skipped:
            message = f'Saved {count} {kind} in "{report.folder.name}". Skipped {skipped} rows.{zip_note}{sent_note}'
            tone = "warn"
        else:
            message = f'Saved {count} {kind} in "{report.folder.name}".{zip_note}{sent_note}'
            tone = "ok"
        self.set_status(message, tone)
        tip = str(report.folder if report.archive is None else f"{report.folder}\n{report.archive}")
        self.status_label.setToolTip(tip)
        self.open_btn.setToolTip(tip)

    def _on_generate_failed(self, message: str) -> None:
        failed = "Could not finish writing the drafts."
        if self._kind == EMAIL:
            failed += " Nothing was sent."
        self.set_status(failed, "error")
        show_error(self, message)

    def _on_worker_finished(self) -> None:
        self._set_busy(False)
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _fill_sheets(self) -> None:
        sheets = self.table.sheets if self.table else []
        self.sheet_wrap.setVisible(len(sheets) > 1)
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        for name in sheets:
            self.sheet_combo.addItem(name)
        if self.table and self.table.sheet:
            index = self.sheet_combo.findText(self.table.sheet)
            if index >= 0:
                self.sheet_combo.setCurrentIndex(index)
        self.sheet_combo.blockSignals(False)

    def _fill_recipient(self) -> None:
        self.recipient.blockSignals(True)
        self.recipient.clear()
        self.recipient.addItem("Choose a column", "")
        choice = ""
        if self.table:
            for header in self.table.headers:
                self.recipient.addItem(header.replace("&", "&&"), header)
            if self._preferred_recipient in self.table.headers:
                choice = self._preferred_recipient
            else:
                choice = guess_email_column(self.table.headers) or ""
        index = self.recipient.findData(choice) if choice else 0
        self.recipient.setCurrentIndex(index if index >= 0 else 0)
        self.recipient.blockSignals(False)
        if choice:
            self._preferred_recipient = choice

    def _fill_zip(self) -> None:
        self.zip_combo.blockSignals(True)
        self.zip_combo.clear()
        self.zip_combo.addItem("Choose a column", "")
        choice = ""
        if self.table:
            for header in self.table.headers:
                self.zip_combo.addItem(header.replace("&", "&&"), header)
            if self._preferred_zip in self.table.headers:
                choice = self._preferred_zip
            else:
                choice = guess_zip_column(self.table.headers) or ""
        index = self.zip_combo.findData(choice) if choice else 0
        self.zip_combo.setCurrentIndex(index if index >= 0 else 0)
        self.zip_combo.blockSignals(False)
        if choice:
            self._preferred_zip = choice

    def _fill_fields(self) -> None:
        self.field_host.flow.clear()
        headers = self.table.headers if self.table else []
        for header in headers:
            self._add_chip(header, f"[{header}]", f"Insert [{header}]")
        if self.table and not any(header.casefold() == "row" for header in headers):
            self._add_chip("Row", "[Row]", "Insert the row number, starting at 1. This is not a column in the file.")
        if find_header(headers, ("nearest city",)) is None:
            self._add_chip(
                NEAREST_CITY,
                f"[{NEAREST_CITY}]",
                "Closest of the 56 FBI field offices to this ZIP code. Calculated on this computer.",
            )
        self._update_insert_hint()
        self._fit_chips()

    def _add_chip(self, label: str, token: str, tip: str) -> None:
        button = make_button(label.replace("&", "&&"), "FieldChip")
        button.setProperty("chipLabel", label)
        button.setToolTip(tip)
        button.clicked.connect(lambda _checked=False, value=token: self.insert_token(value))
        self.field_host.flow.addWidget(button)

    def _apply_sidebar_width(self) -> None:
        total = max(self.splitter.width(), 1)
        side = max(280, min(720, self._sidebar_width))
        self.splitter.setSizes([side, max(320, total - side)])

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        sizes = self.splitter.sizes()
        if sizes:
            self._sidebar_width = sizes[0]
        self._fit_chips()

    def _fit_chips(self) -> None:
        if self._fitting_chips:
            return
        self._fitting_chips = True
        try:
            available = self.field_host.width()
            if available < 80:
                available = max(160, self.sidebar.width() - 48)
            available = max(80, available)
            for button in self.field_host.findChildren(QPushButton):
                full = button.property("chipLabel")
                if not isinstance(full, str) or not full:
                    continue
                metrics = QFontMetrics(button.font())
                padding = 28
                natural = metrics.horizontalAdvance(full) + padding
                width = min(max(natural, 48), available)
                button.setFixedWidth(width)
                shown = metrics.elidedText(full, Qt.TextElideMode.ElideMiddle, max(16, width - padding))
                button.setText(shown.replace("&", "&&"))
            self.field_host.refresh()
        finally:
            self._fitting_chips = False

    def _show_source(self) -> None:
        if self.table is None:
            self.source_summary.setText("No spreadsheet loaded.")
            self.path_edit.setText("")
            self.path_edit.setToolTip("")
            return
        count = len(self.table.records)
        noun = "record" if count == 1 else "records"
        self.source_summary.setText(f"{count} {noun} in {self.table.source.name}")
        self.path_edit.setText(str(self.table.source))
        self.path_edit.setToolTip(str(self.table.source))

    def _sync_actions(self) -> None:
        busy = self._busy
        has_table = self.table is not None
        self.browse_btn.setEnabled(not busy)
        self.paper_browse_btn.setEnabled(not busy)
        self.sample_btn.setEnabled(not busy)
        self.paper_sample_btn.setEnabled(not busy)
        self.view_btn.setEnabled(not busy and has_table)
        self.email_btn.setEnabled(not busy)
        self.word_btn.setEnabled(not busy)
        self.sheet_combo.setEnabled(not busy)
        self.recipient.setEnabled(not busy)
        self.zip_combo.setEnabled(not busy)
        self.subject_edit.setEnabled(not busy)
        self.body_edit.setEnabled(not busy)
        self.from_name.setEnabled(not busy)
        self.from_email.setEnabled(not busy)
        self.filename_edit.setEnabled(not busy)
        self.output_dir.setEnabled(not busy)
        self.output_browse.setEnabled(not busy)
        self.create_zip.setEnabled(not busy)
        self.example_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.field_host.setEnabled(not busy)
        self.open_btn.setEnabled(
            not busy and self.last_report is not None and self.last_report.folder.is_dir()
        )
        if busy:
            self.generate_btn.setText("Stop")
            self.generate_btn.setToolTip("Stop writing files. Nothing will be sent.")
            self.generate_btn.setEnabled(True)
        else:
            self.generate_btn.setText("Generate emails" if self._kind == EMAIL else "Generate documents")
            self.generate_btn.setToolTip("Write the drafts into a new folder. This does not send email.")
            self.generate_btn.setEnabled(True)
        self._sync_send_enabled()

    def _sync_send_enabled(self) -> None:
        report = self.last_report
        enabled = (
            not self._busy
            and not self._batch_sent
            and self._kind == EMAIL
            and report is not None
            and report.kind == EMAIL
            and any(draft.path.is_file() for draft in report.written)
        )
        self.send_btn.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._sync_actions()
        self.refresh_preview()

    def _sync_filename_preview(self) -> None:
        extension = ".eml" if self._kind == EMAIL else ".docx"
        if self.table is None:
            self.filename_preview.setText("Each row becomes its own file.")
            return
        rendered = render(
            self.filename_edit.text(),
            self.table.records[self.record_index],
            self.table.headers,
            self.record_index + 1,
            self._extras(self.table.records[self.record_index]),
        )
        stem = safe_stem(rendered.text) or f"draft_{self.record_index + 1}"
        self.filename_preview.setText(f"File name: {stem}{extension}")

    def _unknown_message(self, tokens: list[str]) -> str:
        headers = self.table.headers if self.table else []
        parts: list[str] = []
        for token in tokens[:6]:
            suggestion = closest_header(token[1:-1], headers)
            if suggestion:
                parts.append(f"{token} (try [{suggestion}])")
            else:
                parts.append(token)
        extra = "" if len(tokens) <= 6 else f" and {len(tokens) - 6} more"
        return (
            "No column matches "
            + ", ".join(parts)
            + extra
            + ". Those words will stay in the draft until the names match."
        )

    def _update_insert_hint(self) -> None:
        if self.table is None:
            self.insert_hint.setText("Nearest City uses the ZIP column. Load a spreadsheet to see its other fields.")
            return
        target = self._insert_target
        if target is self.subject_edit:
            text = "Click a field to insert it into the subject."
        elif target is self.filename_edit:
            text = "Click a field to insert it into the file name."
        else:
            text = "Click a field to insert it into the message."
        self.insert_hint.setText(text)

    def _recipient_column(self) -> str:
        data = self.recipient.currentData()
        return data if isinstance(data, str) else ""

    def _zip_column(self) -> str:
        data = self.zip_combo.currentData()
        return data if isinstance(data, str) else ""

    def _extras(self, record: dict[str, str]) -> dict[str, str]:
        headers = self.table.headers if self.table else []
        return computed_fields(record, headers, self._zip_column())

    def _city_note(self, record: dict[str, str]) -> str:
        if self.table is None or find_header(self.table.headers, ("nearest city",)):
            return ""
        templates = "\n".join(
            (self.body_edit.toPlainText(), self.subject_edit.text(), self.filename_edit.text())
        )
        if "nearest city" not in templates.casefold():
            return ""
        column = self._zip_column()
        if not column:
            return "Choose the ZIP column to fill Nearest City."
        raw = record.get(column, "")
        if not normalize_zip(raw):
            return "This row has no ZIP code, so Nearest City is blank."
        if not nearest_city(raw):
            return "This ZIP code is not in the offline list, so Nearest City is blank."
        return ""

    def _on_zip_changed(self) -> None:
        self._preferred_zip = self._zip_column()
        self.refresh_preview()

    def _on_sheet_changed(self, name: str) -> None:
        if self._busy or self.table is None or not name or name == self.table.sheet:
            return
        self.load_file(self.table.source, sheet=name)

    def _on_recipient_changed(self) -> None:
        column = self._recipient_column()
        self._preferred_recipient = column
        self.refresh_preview()

    def _on_subject_edited(self) -> None:
        self._subject_edited = True

    def _on_filename_edited(self) -> None:
        self._filename_edited = True

    def _on_body_changed(self) -> None:
        if self._programmatic == 0:
            self._body_edited = True
        self.refresh_preview()

    def _dropped_spreadsheet(self, event) -> str:
        if not event.mimeData().hasUrls():
            return ""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).suffix.lower() in {".csv", ".xlsx", ".xlsm", ".xls"}:
                return path
        return ""

    def _center(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())
