"""Structure-aware Markdown chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.knowledge.markdown_parser import MarkdownDocument, MarkdownSection, parse_sections


@dataclass(frozen=True)
class KnowledgeChunkDraft:
    """A chunk before persistence metadata is attached."""

    document_path: str
    section_path: tuple[str, ...]
    text: str
    ordinal: int
    token_count: int


_TOKEN_RE = re.compile(r"\S+")


def approximate_token_count(text: str) -> int:
    """Count whitespace-delimited tokens deterministically."""
    return len(_TOKEN_RE.findall(text))


def chunk_document(
    document: MarkdownDocument,
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[KnowledgeChunkDraft]:
    """Parse and chunk a Markdown document by heading section."""
    chunks: list[KnowledgeChunkDraft] = []
    for section in parse_sections(document):
        chunks.extend(_chunk_section(section, len(chunks), target_tokens, overlap_tokens))
    return chunks


def _chunk_section(
    section: MarkdownSection,
    start_ordinal: int,
    target_tokens: int,
    overlap_tokens: int,
) -> list[KnowledgeChunkDraft]:
    tokens = _TOKEN_RE.findall(section.text)
    if not tokens:
        return []
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")
    overlap = max(0, min(overlap_tokens, target_tokens - 1))
    step = target_tokens - overlap
    drafts: list[KnowledgeChunkDraft] = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + target_tokens]
        if not window:
            break
        text = _format_chunk_text(section.section_path, " ".join(window))
        drafts.append(
            KnowledgeChunkDraft(
                document_path=section.document_path,
                section_path=section.section_path,
                text=text,
                ordinal=start_ordinal + len(drafts),
                token_count=len(window),
            )
        )
        if start + target_tokens >= len(tokens):
            break
    return drafts


def _format_chunk_text(section_path: tuple[str, ...], body: str) -> str:
    prefix = " > ".join(section_path)
    return f"Section: {prefix}\n\n{body}".strip() + "\n"
