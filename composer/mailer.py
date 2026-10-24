"""Send drafts the user has already reviewed and explicitly confirmed."""

from __future__ import annotations

import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import formataddr
from pathlib import Path

from composer.data import looks_like_email, single_line


@dataclass
class SmtpConfig:
    host: str
    port: int
    security: str
    username: str
    password: str
    from_name: str
    from_email: str


@dataclass
class SendResult:
    sent: list[str]
    failed: list[tuple[str, str]]
    stopped: bool
    error: str | None = None


def send_files(
    paths: list[Path],
    config: SmtpConfig,
    *,
    confirmed: bool,
    log: Callable[[str], None] | None = None,
    stop: Callable[[], bool] | None = None,
) -> SendResult:
    """Deliver existing draft files. This refuses to run unless confirmed is True."""
    if confirmed is not True:
        raise RuntimeError("Refusing to send because the send was not confirmed.")
    write = log or (lambda _line: None)
    sent: list[str] = []
    failed: list[tuple[str, str]] = []
    if not paths:
        message = "There are no drafts to send."
        write(message)
        return SendResult(sent, failed, False, message)

    server = None
    try:
        server = _connect(config)
        write(f"Connected to {config.host.strip()}.")
    except Exception as exc:
        message = f"Could not connect or sign in: {_public_error(exc, config.password)}"
        return SendResult(sent, failed, False, message)

    stopped = False
    try:
        total = len(paths)
        for index, path in enumerate(paths, start=1):
            if stop and stop():
                stopped = True
                write("Stopped before the remaining drafts.")
                break
            try:
                recipient = _send_one(server, path, config)
                sent.append(f"{path.name} -> {recipient}")
                write(f"Sent {index} of {total}: {recipient}")
            except Exception as exc:
                detail = _public_error(exc, config.password)
                failed.append((path.name, detail))
                write(f"Failed {path.name}: {detail}")
    finally:
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass
    return SendResult(sent, failed, stopped, None)


def _connect(config: SmtpConfig) -> smtplib.SMTP:
    host = config.host.strip()
    if not host:
        raise ValueError("Enter the mail server host.")
    if config.security not in {"starttls", "ssl", "none"}:
        raise ValueError("Choose STARTTLS, SSL, or no encryption.")
    if not looks_like_email(config.from_email):
        raise ValueError("Enter a valid From email address.")
    context = ssl.create_default_context()
    if config.security == "ssl":
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, int(config.port), timeout=30, context=context)
    else:
        server = smtplib.SMTP(host, int(config.port), timeout=30)
        server.ehlo()
        if config.security == "starttls":
            server.starttls(context=context)
            server.ehlo()
    username = config.username.strip()
    if username:
        server.login(username, config.password)
    return server


def _send_one(server: smtplib.SMTP, path: Path, config: SmtpConfig) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    recipient = single_line(str(message.get("To", "")))
    if not looks_like_email(recipient):
        raise ValueError("the draft has no valid To address")
    for header in ("From", "X-Unsent", "X-Composer"):
        if header in message:
            del message[header]
    from_name = single_line(config.from_name)
    from_email = single_line(config.from_email)
    message["From"] = formataddr((from_name, from_email)) if from_name else from_email
    server.send_message(message)
    return recipient


def _public_error(exc: Exception, password: str) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if password:
        text = text.replace(password, "••••")
    return text
