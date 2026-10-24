"""Write review drafts to a folder. This module never sends email."""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from composer.data import (
    EMAIL,
    WORD,
    looks_like_email,
    render,
    safe_stem,
    single_line,
)


@dataclass
class Draft:
    row_number: int
    filename: str
    path: Path
    recipient: str
    subject: str


@dataclass
class BatchReport:
    folder: Path
    kind: str
    written: list[Draft] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    unknown_tokens: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass
class ExportJob:
    kind: str
    headers: list[str]
    records: list[dict[str, str]]
    source_name: str
    output_dir: Path
    subject_template: str
    body_template: str
    filename_template: str
    recipient_column: str
    from_name: str = ""
    from_email: str = ""


def export_batch(
    job: ExportJob,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> BatchReport:
    job.output_dir.mkdir(parents=True, exist_ok=True)
    folder = _create_batch_folder(job.output_dir, "Emails" if job.kind == EMAIL else "Documents")
    report = BatchReport(folder=folder, kind=job.kind)
    seen_unknown: set[str] = set()
    used_names: set[str] = set()
    extension = ".eml" if job.kind == EMAIL else ".docx"
    total = len(job.records)
    from_email = single_line(job.from_email)
    from_name = single_line(job.from_name)
    if from_email and not looks_like_email(from_email):
        from_email = ""
        from_name = ""

    for index, record in enumerate(job.records, start=1):
        if cancel and cancel():
            report.cancelled = True
            break
        body = render(job.body_template, record, job.headers, index)
        subject = render(job.subject_template, record, job.headers, index)
        filename_render = render(job.filename_template, record, job.headers, index)
        for token in (*body.unknown, *subject.unknown, *filename_render.unknown):
            if token not in seen_unknown:
                seen_unknown.add(token)
                report.unknown_tokens.append(token)
        subject_text = single_line(subject.text)
        recipient = ""
        if job.kind == EMAIL:
            recipient = single_line(record.get(job.recipient_column, ""))
            if not looks_like_email(recipient):
                if recipient:
                    shown = recipient if len(recipient) <= 80 else recipient[:77] + "..."
                    reason = f"Row {index} does not have a valid email address ({shown})."
                else:
                    reason = f"Row {index} has no email address."
                report.skipped.append((index, reason))
                if progress:
                    progress(index, total)
                continue
        stem = safe_stem(filename_render.text)
        for suffix in (".eml", ".docx", ".txt"):
            if stem.lower().endswith(suffix):
                stem = safe_stem(stem[: -len(suffix)])
                break
        if not stem:
            stem = f"draft_{index}"
        filename = _allocate_name(folder, stem, extension, used_names)
        path = folder / filename
        if job.kind == EMAIL:
            _write_eml(
                path,
                subject=subject_text,
                body=body.text,
                recipient=recipient,
                from_name=from_name,
                from_email=from_email,
            )
        else:
            _write_docx(path, body.text)
        report.written.append(
            Draft(
                row_number=index,
                filename=filename,
                path=path,
                recipient=recipient,
                subject=subject_text,
            )
        )
        if progress:
            progress(index, total)

    _write_review(report, job.source_name)
    return report


def _create_batch_folder(parent: Path, label: str) -> Path:
    for _attempt in range(5):
        folder = _fresh_folder(parent, label)
        try:
            folder.mkdir(parents=True, exist_ok=False)
            return folder
        except FileExistsError:
            continue
    raise OSError("Could not create a new folder for the drafts.")


def _fresh_folder(parent: Path, label: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d %H-%M")
    folder = parent / f"{label} {stamp}"
    if not folder.exists():
        return folder
    stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    folder = parent / f"{label} {stamp}"
    number = 2
    while folder.exists():
        folder = parent / f"{label} {stamp} {number}"
        number += 1
    return folder


def _allocate_name(folder: Path, stem: str, extension: str, used: set[str]) -> str:
    candidate = f"{stem}{extension}"
    number = 2
    while candidate.casefold() in used or (folder / candidate).exists():
        candidate = f"{stem}_{number}{extension}"
        number += 1
    used.add(candidate.casefold())
    return candidate


def _write_eml(
    path: Path,
    *,
    subject: str,
    body: str,
    recipient: str,
    from_name: str,
    from_email: str,
) -> None:
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    if from_email:
        message["From"] = formataddr((from_name, from_email)) if from_name else from_email
    message["Date"] = formatdate(localtime=True)
    message["X-Unsent"] = "1"
    message["X-Composer"] = "draft"
    message.set_content(body)
    path.write_bytes(message.as_bytes())


def _write_docx(path: Path, body: str) -> None:
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor(0x14, 0x28, 0x3A)
    for line in body.split("\n"):
        paragraph = document.add_paragraph(line)
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.paragraph_format.space_before = Pt(0)
    document.save(path)


def _write_review(report: BatchReport, source_name: str) -> None:
    kind_label = "email drafts" if report.kind == EMAIL else "Word documents"
    lines = [
        "These files are drafts for you to review.",
        "Composer did not send any email.",
        "",
        f"Source: {source_name}",
        f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Draft type: {kind_label}",
        f"Files written: {len(report.written)}",
        f"Rows skipped: {len(report.skipped)}",
    ]
    if report.cancelled:
        lines.append("Generation was stopped before every row was finished.")
    if report.unknown_tokens:
        lines.extend(["", "These tokens did not match a column and were left unchanged:"])
        lines.extend(f"- {token}" for token in report.unknown_tokens)
    if report.skipped:
        lines.extend(["", "Skipped rows:"])
        lines.extend(f"- {reason}" for _, reason in report.skipped)
    lines.extend(["", "Files:"])
    if not report.written:
        lines.append("- None")
    for draft in report.written:
        if draft.recipient:
            lines.append(f"- {draft.filename} -> {draft.recipient}")
        else:
            lines.append(f"- {draft.filename}")
    (report.folder / "Review notes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (report.folder / "Review index.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "row", "to", "subject", "status"])
        for draft in report.written:
            writer.writerow([draft.filename, draft.row_number, draft.recipient, draft.subject, "draft"])
        for row_number, reason in report.skipped:
            writer.writerow(["", row_number, "", "", reason])
