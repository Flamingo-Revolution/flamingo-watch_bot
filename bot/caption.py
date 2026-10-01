"""Caption format shared between the Discord message and the eventual Instagram post
(CLAUDE.md section 8.2). Built once so Phase 1 (Discord) and Phase 3 (Instagram)
never drift apart.

    {title}

    {summary}

    Source: {source}
    {url}

    Automated summary, check the original.
    {HASHTAGS}

Empty parts (no summary) are skipped cleanly. Only the summary is ever truncated to
fit MAX_CAPTION -- the source, url, disclaimer and hashtags are never cut.
"""
from __future__ import annotations

MAX_CAPTION = 2200
DISCLAIMER = "Automated summary, check the original."


def _build(title: str, summary: str, source: str, url: str, hashtags: str) -> str:
    parts = [title]
    if summary:
        parts.append(summary)
    parts.append(f"Source: {source}\n{url}")
    parts.append(DISCLAIMER)
    if hashtags:
        parts.append(hashtags)
    return "\n\n".join(parts)


def build(title: str, summary: str | None, source: str, url: str, hashtags: str = "") -> str:
    summary = summary or ""
    caption = _build(title, summary, source, url, hashtags)
    if len(caption) <= MAX_CAPTION or not summary:
        return caption[:MAX_CAPTION]

    excess = len(caption) - MAX_CAPTION
    # Reserve one extra character for the ellipsis we're about to append.
    keep = max(0, len(summary) - excess - 1)
    trimmed = (summary[:keep].rstrip() + "…") if keep > 0 else ""
    caption = _build(title, trimmed, source, url, hashtags)
    return caption[:MAX_CAPTION]
