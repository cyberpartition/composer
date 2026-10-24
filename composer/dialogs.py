"""Spreadsheet preview and the explicit send confirmation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QComboBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from composer.data import Table, looks_like_email
from composer.mailer import SendResult, SmtpConfig, send_files
from composer.widgets import ClickLabel, hint_label, labeled, make_button, section_label


def show_error(parent: QWidget, text: str) -> None:
    _message(parent, text, QMessageBox.Critical)


def show_info(parent: QWidget, text: str) -> None:
    _message(parent, text, QMessageBox.Information)


def ask(parent: QWidget, text: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle("Composer")
    box.setTextFormat(Qt.PlainText)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    return box.exec() == QMessageBox.Yes


def _message(parent: QWidget, text: str, icon: QMessageBox.Icon) -> None:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle("Composer")
    box.setTextFormat(Qt.PlainText)
    box.setText(text)
    box.exec()


class RecordModel(QAbstractTableModel):
    def __init__(self, headers: list[str], records: list[dict[str, str]]) -> None:
        super().__init__()
        self.headers = headers
        self._all = list(enumerate(records, start=1))
        self._rows = list(self._all)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        return self._rows[index.row()][1].get(self.headers[index.column()], "")

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return str(self._rows[section][0])

    def filter(self, text: str) -> None:
        folded = text.casefold().strip()
        self.beginResetModel()
        if not folded:
            self._rows = list(self._all)
        else:
            self._rows = [
                pair
                for pair in self._all
                if any(folded in value.casefold() for value in pair[1].values())
            ]
        self.endResetModel()


class DataDialog(QDialog):
    def __init__(self, parent: QWidget, table: Table) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Spreadsheet — {table.source.name}")
        self.resize(920, 560)
        self.model = RecordModel(table.headers, table.records)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        title = section_label(table.source.name)
        layout.addWidget(title)
        self.count_label = hint_label("")
        layout.addWidget(self.count_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter rows")
        layout.addWidget(self.search)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.setWordWrap(False)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.verticalHeader().setDefaultSectionSize(28)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.view.horizontalHeader().setDefaultSectionSize(140)
        layout.addWidget(self.view, 1)
        close = make_button("Close", "SecondaryButton")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda: self._timer.start())
        self._update_count()

    def _apply_filter(self) -> None:
        self.model.filter(self.search.text())
        self._update_count()

    def _update_count(self) -> None:
        shown = self.model.rowCount()
        total = len(self.model._all)
        if shown == total:
            noun = "row" if total == 1 else "rows"
            self.count_label.setText(f"{total} {noun}")
        else:
            self.count_label.setText(f"{shown} of {total} rows")


class MailWorker(QThread):
    log_line = Signal(str)
    finished_result = Signal(object)

    def __init__(self, paths: list[Path], config: SmtpConfig) -> None:
        super().__init__()
        self.paths = paths
        self.config = config

    def run(self) -> None:
        try:
            result = send_files(
                self.paths,
                self.config,
                confirmed=True,
                log=self.log_line.emit,
                stop=self.isInterruptionRequested,
            )
        except Exception as exc:
            result = SendResult([], [], False, str(exc))
        self.finished_result.emit(result)


class SendDialog(QDialog):
    """Asks before any message leaves the machine. The send button starts disabled."""

    def __init__(
        self,
        parent: QWidget,
        *,
        files: list[Path],
        folder: Path,
        from_name: str,
        from_email: str,
        smtp: dict[str, object],
        password: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Send emails")
        self.setMinimumWidth(620)
        self.files = files
        self.folder = folder
        self._sending = False
        self._result: SendResult | None = None
        self._worker: MailWorker | None = None

        count = len(files)
        noun = "email" if count == 1 else "emails"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        title = QLabel("Send the drafts you reviewed")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        intro = hint_label(
            f"Composer will send {count} {noun} through the mail server below. "
            "Nothing is sent until you check the box and choose Send. "
            "Only these generated drafts are included."
        )
        layout.addWidget(intro)
        path = QLabel(str(folder))
        path.setWordWrap(True)
        path.setTextFormat(Qt.PlainText)
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path.setObjectName("Hint")
        layout.addWidget(path)

        self.host = QLineEdit()
        self.host.setPlaceholderText("smtp.example.com")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(587)
        self.security = QComboBox()
        self.security.addItem("STARTTLS", "starttls")
        self.security.addItem("SSL/TLS", "ssl")
        self.security.addItem("No encryption", "none")
        server_row = QHBoxLayout()
        server_row.addWidget(labeled("Mail server", self.host), 1)
        port_wrap = labeled("Port", self.port)
        port_wrap.setFixedWidth(100)
        server_row.addWidget(port_wrap)
        security_wrap = labeled("Security", self.security)
        security_wrap.setFixedWidth(170)
        server_row.addWidget(security_wrap)
        layout.addLayout(server_row)
        self.security_hint = hint_label("")
        layout.addWidget(self.security_hint)

        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        account = QHBoxLayout()
        account.addWidget(labeled("Username", self.username))
        account.addWidget(labeled("Password", self.password))
        layout.addLayout(account)
        layout.addWidget(hint_label("Your password stays in memory until you close Composer. It is not saved."))

        self.from_name = QLineEdit()
        self.from_email = QLineEdit()
        self.from_email.setPlaceholderText("you@example.com")
        identity = QHBoxLayout()
        identity.addWidget(labeled("From name", self.from_name))
        identity.addWidget(labeled("From email", self.from_email))
        layout.addLayout(identity)

        confirm_row = QHBoxLayout()
        self.confirm = QCheckBox()
        self.confirm_label = ClickLabel(
            f"I reviewed these drafts and I want Composer to send all {count} {noun} now."
        )
        confirm_row.addWidget(self.confirm, 0, Qt.AlignTop)
        confirm_row.addWidget(self.confirm_label, 1)
        layout.addLayout(confirm_row)
        self.confirm_label.clicked.connect(self.confirm.toggle)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("TemplateEdit")
        self.log.setFixedHeight(130)
        self.log.setVisible(False)
        layout.addWidget(self.log)

        self.send_btn = make_button(f"Send {count} {noun}", "PrimaryButton")
        self.stop_btn = make_button("Stop", "SecondaryButton")
        self.stop_btn.setVisible(False)
        self.close_btn = make_button("Cancel", "SecondaryButton")
        self.send_btn.setAutoDefault(False)
        self.send_btn.setDefault(False)
        self.close_btn.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.send_btn)
        layout.addLayout(buttons)

        self._apply(smtp, from_name, from_email, password)
        self.security.currentIndexChanged.connect(self._on_security)
        self.confirm.toggled.connect(self._sync_send_enabled)
        self.host.textChanged.connect(self._sync_send_enabled)
        self.from_email.textChanged.connect(self._sync_send_enabled)
        self.username.textChanged.connect(self._sync_send_enabled)
        self.password.textChanged.connect(self._sync_send_enabled)
        self.send_btn.clicked.connect(self._send)
        self.stop_btn.clicked.connect(self._stop)
        self.close_btn.clicked.connect(self._close)
        self._sync_security_hint()
        self._sync_send_enabled()
        self.close_btn.setFocus()

    @property
    def sent_count(self) -> int:
        return len(self._result.sent) if self._result else 0

    @property
    def fail_count(self) -> int:
        return len(self._result.failed) if self._result else 0

    def memory(self) -> tuple[dict[str, object], str]:
        return {
            "smtp_host": self.host.text().strip(),
            "smtp_port": int(self.port.value()),
            "smtp_security": self.security.currentData() or "starttls",
            "smtp_username": self.username.text().strip(),
            "from_name": self.from_name.text().strip(),
            "from_email": self.from_email.text().strip(),
        }, self.password.text()

    def closeEvent(self, event) -> None:
        if self._sending:
            self._append("Wait until sending finishes, or click Stop.")
            event.ignore()
            return
        super().closeEvent(event)

    def _apply(self, smtp: dict[str, object], from_name: str, from_email: str, password: str) -> None:
        self.host.setText(str(smtp.get("smtp_host") or ""))
        self.username.setText(str(smtp.get("smtp_username") or ""))
        self.from_name.setText(from_name)
        self.from_email.setText(from_email)
        self.password.setText(password)
        security = str(smtp.get("smtp_security") or "starttls")
        index = self.security.findData(security)
        self.security.blockSignals(True)
        self.port.blockSignals(True)
        if index >= 0:
            self.security.setCurrentIndex(index)
        try:
            self.port.setValue(int(smtp.get("smtp_port") or 587))
        except (TypeError, ValueError):
            self.port.setValue(587)
        self.security.blockSignals(False)
        self.port.blockSignals(False)

    def _on_security(self) -> None:
        defaults = {"starttls": 587, "ssl": 465, "none": 25}
        if self.port.value() in defaults.values():
            security = self.security.currentData()
            self.port.setValue(defaults.get(security, 587))
        self._sync_security_hint()

    def _sync_security_hint(self) -> None:
        security = self.security.currentData()
        if security == "none":
            self.security_hint.setText("This connection will not be encrypted.")
        elif security == "ssl":
            self.security_hint.setText("SSL/TLS usually uses port 465. Your password is not saved.")
        else:
            self.security_hint.setText("STARTTLS on port 587 is the usual choice. Your password is not saved.")

    def _sync_send_enabled(self) -> None:
        ready = (
            not self._sending
            and self.confirm.isChecked()
            and bool(self.host.text().strip())
            and looks_like_email(self.from_email.text())
        )
        self.send_btn.setEnabled(ready)

    def _send(self) -> None:
        if not self.confirm.isChecked() or self._sending:
            return
        if not looks_like_email(self.from_email.text()):
            show_error(self, "Enter a valid From email address before sending.")
            return
        self._sending = True
        self._sync_send_enabled()
        self.stop_btn.setVisible(True)
        self.close_btn.setEnabled(False)
        self.log.setVisible(True)
        self.log.clear()
        self._append(f"Sending {len(self.files)} drafts. You can stop after the current message.")
        config = SmtpConfig(
            host=self.host.text().strip(),
            port=int(self.port.value()),
            security=str(self.security.currentData() or "starttls"),
            username=self.username.text().strip(),
            password=self.password.text(),
            from_name=self.from_name.text().strip(),
            from_email=self.from_email.text().strip(),
        )
        self._worker = MailWorker(self.files, config)
        self._worker.log_line.connect(self._append)
        self._worker.finished_result.connect(self._on_finished)
        self._worker.start()

    def _stop(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.stop_btn.setEnabled(False)
            self._append("Stopping after the current message…")

    def _on_finished(self, result: SendResult) -> None:
        self._result = result
        self._sending = False
        self.stop_btn.setVisible(False)
        self.close_btn.setEnabled(True)
        self.close_btn.setText("Close")
        if result.error and not result.sent:
            self._append(result.error)
            self._append("No messages were sent.")
            self._sync_send_enabled()
            return
        self.send_btn.setEnabled(False)
        self.confirm.setEnabled(False)
        self.confirm_label.setEnabled(False)
        extra = " Stopped early." if result.stopped else ""
        self._append(f"Sent {len(result.sent)}. Failed {len(result.failed)}.{extra}")
        if result.failed:
            self._append("Open a failed draft from the folder if you want to send that one yourself.")

    def _append(self, line: str) -> None:
        self.log.setVisible(True)
        self.log.appendPlainText(line)

    def _close(self) -> None:
        if self._sending:
            return
        if self.sent_count:
            self.accept()
        else:
            self.reject()
