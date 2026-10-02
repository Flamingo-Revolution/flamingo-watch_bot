#!/usr/bin/env python
"""Phase 1 entrypoint: fetch new Flamingo Watch stories, render cards, post them to
Discord via webhook. Run by .github/workflows/ig-cards.yml on a schedule, or by hand:

    python scripts/cards_to_discord.py --dry-run

See docs/BOT.md for configuration and docs/bot-discovery.md for the feed decisions.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import caption as caption_mod  # noqa: E402
from bot import card, discord_webhook, feed  # noqa: E402
from bot import state as state_mod  # noqa: E402
from bot.feed import Story  # noqa: E402

log = logging.getLogger("cards_to_discord")

MESSAGE_CAP = 1990


def _env(name: str, default: str) -> str:
    return os.getenv(name) or default


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "story"


def build_message(story: Story, caption: str) -> str:
    header = f"**{story.title}**\n{story.source} | {story.url}\n"
    body = f"```{caption}```"
    return (header + body)[:MESSAGE_CAP]


def _redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    return text


def run(*, lang: str, max_per_run: int, first_run_post: int, webhook_url: str | None,
        hashtags: str, state_path: Path, dry_run: bool, out_dir: Path) -> int:
    state = state_mod.load(state_path)
    is_first_run = len(state.get("seen", [])) == 0

    stories = feed.fetch(lang)  # newest-first (docs/bot-discovery.md section 2)
    oldest_first = list(reversed(stories))

    to_seed: list[Story] = []
    if is_first_run:
        newest_batch = stories[:first_run_post]
        to_post = list(reversed(newest_batch))  # post oldest-of-the-batch first
        posting_keys = {s.key for s in to_post}
        to_seed = [s for s in stories if s.key not in posting_keys]
        log.info("first run: posting %d newest, seeding %d older items as seen",
                  len(to_post), len(to_seed))
    else:
        unseen = [s for s in oldest_first if not state_mod.is_seen(state, s.key)]
        to_post = unseen[:max_per_run]
        log.info("%d unseen stories, posting %d (MAX_PER_RUN=%d)",
                  len(unseen), len(to_post), max_per_run)

    if dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    posted = 0
    for i, story in enumerate(to_post):
        try:
            image_bytes = card.render(story, lang)
            cap = caption_mod.build(story.title, story.summary, story.source, story.url, hashtags)
            message = build_message(story, cap)
            filename = f"{_slug(story.key)}.jpg"

            if dry_run:
                (out_dir / f"{i:02d}-{filename}").write_bytes(image_bytes)
                print(f"--- would post ({story.key}) ---")
                print(message)
                print()
            else:
                discord_webhook.post(webhook_url, message, filename, image_bytes)
                log.info("posted %s", story.key)
        except Exception:
            log.exception("failed to process story %s, skipping", story.key)
            continue

        state_mod.mark_seen(state, story.key)
        if not dry_run:
            state_mod.save(state_path, state)  # --dry-run must leave no footprint
        posted += 1

    if to_seed:
        for story in to_seed:
            state_mod.mark_seen(state, story.key)
        if not dry_run:
            state_mod.save(state_path, state)

    log.info("done: %d posted this run", posted)
    return posted


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="render cards to out/*.jpg and print messages instead of posting")
    args = parser.parse_args()

    lang = _env("CARD_LANG", "sq")
    max_per_run = int(_env("MAX_PER_RUN", "5"))
    first_run_post = int(_env("FIRST_RUN_POST", "3"))
    hashtags = _env("HASHTAGS", "#Albania #FlamingoRevolution")
    state_path = Path(_env("STATE_PATH", "state.json"))
    out_dir = Path(_env("OUT_DIR", "out"))
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    alert_webhook_url = os.getenv("ALERT_WEBHOOK_URL")

    if not args.dry_run and not webhook_url:
        log.error("DISCORD_WEBHOOK_URL is not set (required unless --dry-run)")
        return 1

    try:
        run(lang=lang, max_per_run=max_per_run, first_run_post=first_run_post,
            webhook_url=webhook_url, hashtags=hashtags, state_path=state_path,
            dry_run=args.dry_run, out_dir=out_dir)
        return 0
    except Exception:
        tb = _redact(traceback.format_exc(), [webhook_url, alert_webhook_url])[-1500:]
        log.error("job failed:\n%s", tb)
        if alert_webhook_url and not args.dry_run:
            try:
                discord_webhook.post_text(alert_webhook_url, f"Flamingo Watch job failed\n```{tb}```")
            except Exception:
                log.exception("also failed to send the alert")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
