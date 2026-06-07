"""Deterministic query rewriter implementations."""

from __future__ import annotations

import re
from typing import Pattern


# Regex that matches identifiers, numbers, and URLs that should never be
# lowercased.  This preserves case-sensitive tokens while normalising the
# rest of the query.
#   - URLs:     https?://... 
#   - Tickers:  $AAPL, $BTC
#   - IDs:      uuid-like hex, short hex (0x...), common IDs
#   - Numbers:  integers, decimals, percentages
_PRESERVE_PATTERN: Pattern[str] = re.compile(
    r"https?://\S+"
    r"|\$[A-Za-z0-9]+"
    r"|0x[a-fA-F0-9]+"
    r"|[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
    r"|\d+\.?\d*%?"
)


def _tokenise_preserving(text: str) -> list[tuple[str, bool]]:
    """Split text into segments that are either preserved or normalised.

    Each segment is a ``(text, preserve_case)`` pair where ``preserve_case``
    is ``True`` for tokens that matched the preserve pattern.

    Args:
        text: Raw input text.

    Returns:
        List of (segment, preserve_case) tuples in order.
    """
    segments: list[tuple[str, bool]] = []
    last_end = 0

    for match in _PRESERVE_PATTERN.finditer(text):
        # Normalise everything before this match
        if match.start() > last_end:
            segments.append((text[last_end : match.start()], False))
        # Preserve the matched token as-is
        segments.append((match.group(), True))
        last_end = match.end()

    # Remaining text after the last match
    if last_end < len(text):
        segments.append((text[last_end:], False))

    return segments


class DeterministicQueryRewriter:
    """Query rewriter that normalises whitespace and casing safely.

    Operations applied in order:

    1. Strip leading/trailing whitespace.
    2. Normalise multiple internal whitespace runs to a single space.
    3. Lowercase the query text **except** for tokens that match known
       patterns (URLs, tickers, UUIDs, hex literals, numbers).
    4. Return the cleaned string.

    The rewriter is fully deterministic — same input always produces
    the same output — which makes it safe for cache-key derivation.
    """

    def rewrite(self, query_text: str) -> str:
        """Rewrite a raw query for deterministic retrieval.

        Args:
            query_text: Raw user query.

        Returns:
            Normalised query string.
        """
        if not query_text:
            return ""

        # 1. Strip leading/trailing whitespace
        trimmed = query_text.strip()

        # 2. Normalise internal whitespace
        normalised = re.sub(r"\s+", " ", trimmed)

        # 3. Tokenise preserving case for IDs/URLs/numbers
        segments = _tokenise_preserving(normalised)

        out_parts: list[str] = []
        for text, preserve in segments:
            if preserve:
                out_parts.append(text)
            else:
                out_parts.append(text.lower())

        return "".join(out_parts)
