"""Deterministic Markdown extraction and section parsing."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class MarkdownDocument:
    """Normalized Markdown document extracted from raw input or ZIP."""

    path: str
    title: str
    text: str


@dataclass(frozen=True)
class MarkdownSection:
    """A heading-scoped section in a Markdown document."""

    document_path: str
    section_path: tuple[str, ...]
    text: str
    ordinal: int


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def normalize_markdown(text: str) -> str:
    """Normalize Markdown without interpreting source content."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized: list[str] = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                normalized.append("")
            continue
        blank_count = 0
        normalized.append(line)
    return "\n".join(normalized).strip() + "\n"


def extract_markdown_text(text: str, path: str = "source.md") -> list[MarkdownDocument]:
    """Return one normalized document for raw Markdown text."""
    normalized = normalize_markdown(text)
    return [MarkdownDocument(path=path, title=_title_from_path(path), text=normalized)]


def extract_markdown_zip(data: bytes) -> list[MarkdownDocument]:
    """Extract Markdown files from a ZIP in deterministic path order."""
    docs: list[MarkdownDocument] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if not name.endswith("/") and PurePosixPath(name).suffix.lower() in {".md", ".markdown"}
        )
        for name in names:
            raw = archive.read(name).decode("utf-8-sig")
            docs.append(MarkdownDocument(path=name, title=_title_from_path(name), text=normalize_markdown(raw)))
    return docs


def parse_sections(document: MarkdownDocument) -> list[MarkdownSection]:
    """Parse ATX headings into ordered section blocks with hierarchy paths."""
    sections: list[MarkdownSection] = []
    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_path: tuple[str, ...] = (document.title,)

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(
                MarkdownSection(
                    document_path=document.path,
                    section_path=current_path,
                    text=body + "\n",
                    ordinal=len(sections),
                )
            )
        current_lines = []

    for line in document.text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_path = tuple(heading_stack)
            current_lines.append(line)
        else:
            current_lines.append(line)
    flush()
    return sections


def _title_from_path(path: str) -> str:
    stem = PurePosixPath(path).stem.replace("-", "_").replace("_", " ").strip()
    return stem.title() or "Source"
