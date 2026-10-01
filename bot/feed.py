"""Fetch and parse Flamingo Watch stories.

Source of truth: the static export's grouped JSON (`/data/articles-{lang}.json`), not
`feed.xml` -- see docs/bot-discovery.md section 3 for why (story grouping across
outlets, pre-translated title/summary, matching story keys across languages).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

DEFAULT_SITE = "https://flamingo-watch.com"
TIMEOUT = 30.0


@dataclass(frozen=True)
class Story:
    key: str
    title: str
    summary: str | None
    source: str
    url: str
    published: str
    lang: str


def _default_feed_urls(lang: str) -> list[str]:
    return [f"{DEFAULT_SITE}/data/articles-{lang}.json"]


def feed_urls(lang: str) -> list[str]:
    """FEED_URL env var is a comma-separated override/fallback list; falls back to
    the site's own export for the given language when unset."""
    raw = os.getenv("FEED_URL") or ""
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    return urls or _default_feed_urls(lang)


def _parse(payload: dict, lang: str) -> list[Story]:
    stories = []
    for group in payload.get("groups", []):
        articles = group.get("articles") or []
        if not articles:
            continue
        lead = articles[0]  # newest article in the group (see docs/bot-discovery.md)
        title = lead.get("title")
        if not title:
            continue
        key = group.get("key") or lead.get("url") or title
        stories.append(Story(
            key=key,
            title=title,
            summary=lead.get("summary") or None,
            source=lead.get("source") or "",
            url=lead.get("url") or "",
            published=lead.get("published_at") or "",
            lang=lang,
        ))
    return stories


def fetch(lang: str, client: httpx.Client | None = None) -> list[Story]:
    """Try each URL in feed_urls(lang) in order; return stories from the first one
    that works. Raise a clear error if every URL fails or returns zero stories."""
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    errors: list[str] = []
    try:
        for url in feed_urls(lang):
            try:
                resp = client.get(url)
                resp.raise_for_status()
                stories = _parse(resp.json(), lang)
                if stories:
                    return stories
                errors.append(f"{url}: parsed but zero stories")
            except Exception as e:  # noqa: BLE001 -- collected and surfaced below, keep trying
                errors.append(f"{url}: {e}")
    finally:
        if owns_client:
            client.close()
    last = errors[-1] if errors else "no feed URLs configured"
    raise RuntimeError(f"Could not read the feed. Last error: {last}")
