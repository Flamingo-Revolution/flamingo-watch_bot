import sys

import cards_to_discord
from bot.feed import Story

# NEWEST_FIRST mirrors the real feed's order (docs/bot-discovery.md section 2:
# the groups array is newest-lead-article-first).
NEWEST_FIRST = [
    Story(key="s5", title="Story 5", summary="Summary.", source="Outlet",
          url="https://example.com/s5", published="2026-10-01T15:00:00Z", lang="sq"),
    Story(key="s4", title="Story 4", summary="Summary.", source="Outlet",
          url="https://example.com/s4", published="2026-10-01T14:00:00Z", lang="sq"),
    Story(key="s3", title="Story 3", summary="Summary.", source="Outlet",
          url="https://example.com/s3", published="2026-10-01T13:00:00Z", lang="sq"),
    Story(key="s2", title="Story 2", summary="Summary.", source="Outlet",
          url="https://example.com/s2", published="2026-10-01T12:00:00Z", lang="sq"),
    Story(key="s1", title="Story 1", summary="Summary.", source="Outlet",
          url="https://example.com/s1", published="2026-10-01T11:00:00Z", lang="sq"),
]


def _seed_state(path, already_seen_keys):
    pre = cards_to_discord.state_mod.empty()
    for k in already_seen_keys:
        cards_to_discord.state_mod.mark_seen(pre, k)
    cards_to_discord.state_mod.save(path, pre)


def test_first_run_posts_only_newest_and_seeds_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))
    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", lambda *a, **kw: None)

    state_path = tmp_path / "state.json"
    count = cards_to_discord.run(lang="sq", max_per_run=5, first_run_post=3,
                                  webhook_url="https://discord.example/webhook",
                                  hashtags="#Albania", state_path=state_path,
                                  dry_run=False, out_dir=tmp_path / "out")

    assert count == 3  # only the 3 newest posted, no flood
    seen = set(cards_to_discord.state_mod.load(state_path)["seen"])
    assert seen == {"s1", "s2", "s3", "s4", "s5"}  # the other 2 seeded as seen, not posted


def test_later_run_posts_unseen_oldest_first_capped_at_max_per_run(tmp_path, monkeypatch):
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))
    posted_order = []

    def fake_post(webhook_url, content, filename, image_bytes, client=None):
        posted_order.append(filename)

    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", fake_post)

    state_path = tmp_path / "state.json"
    _seed_state(state_path, ["s5", "s4", "s3"])  # as if a prior run already posted these

    count = cards_to_discord.run(lang="sq", max_per_run=1, first_run_post=3,
                                  webhook_url="https://discord.example/webhook",
                                  hashtags="#Albania", state_path=state_path,
                                  dry_run=False, out_dir=tmp_path / "out")

    assert count == 1
    assert posted_order == [f"{cards_to_discord._slug('s1')}.jpg"]  # s1 is older than s2 -> goes first


def test_never_crashes_on_one_bad_item_and_does_not_mark_it_seen(tmp_path, monkeypatch):
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))

    real_render = cards_to_discord.card.render

    def flaky_render(story, lang):
        if story.key == "s2":
            raise ValueError("boom")
        return real_render(story, lang)

    monkeypatch.setattr(cards_to_discord.card, "render", flaky_render)
    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", lambda *a, **kw: None)

    state_path = tmp_path / "state.json"
    _seed_state(state_path, ["s5", "s4", "s3"])

    count = cards_to_discord.run(lang="sq", max_per_run=5, first_run_post=3,
                                  webhook_url="https://discord.example/webhook",
                                  hashtags="#Albania", state_path=state_path,
                                  dry_run=False, out_dir=tmp_path / "out")

    assert count == 1  # s1 succeeded; s2 failed and was skipped, not counted
    seen = cards_to_discord.state_mod.load(state_path)["seen"]
    assert "s1" in seen
    assert "s2" not in seen  # left unseen so a future run retries it


def test_idempotent_second_run_against_same_feed_posts_nothing_new(tmp_path, monkeypatch):
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))
    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", lambda *a, **kw: None)

    state_path = tmp_path / "state.json"
    kwargs = dict(lang="sq", max_per_run=5, first_run_post=3,
                  webhook_url="https://discord.example/webhook", hashtags="#Albania",
                  state_path=state_path, dry_run=False, out_dir=tmp_path / "out")

    first = cards_to_discord.run(**kwargs)
    second = cards_to_discord.run(**kwargs)

    assert first == 3
    assert second == 0


def test_dry_run_never_calls_discord_and_writes_jpgs(tmp_path, monkeypatch):
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))

    def fail_if_called(*a, **kw):
        raise AssertionError("dry-run must never call Discord")

    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", fail_if_called)

    state_path = tmp_path / "state.json"
    out_dir = tmp_path / "out"
    count = cards_to_discord.run(lang="sq", max_per_run=5, first_run_post=3,
                                  webhook_url=None, hashtags="#Albania",
                                  state_path=state_path, dry_run=True, out_dir=out_dir)

    assert count == 3
    assert len(list(out_dir.glob("*.jpg"))) == 3


def test_dry_run_leaves_no_state_footprint(tmp_path, monkeypatch):
    """Regression test: an earlier bug saved state.json during --dry-run, which (once
    committed to bot-state by the workflow) silently consumed the real run's first-run
    seeding, leaving nothing left to actually post. --dry-run must never write state."""
    monkeypatch.setattr(cards_to_discord.feed, "fetch", lambda lang, **kw: list(NEWEST_FIRST))
    monkeypatch.setattr(cards_to_discord.discord_webhook, "post", lambda *a, **kw: None)

    state_path = tmp_path / "state.json"
    dry_count = cards_to_discord.run(lang="sq", max_per_run=5, first_run_post=3,
                                      webhook_url=None, hashtags="#Albania",
                                      state_path=state_path, dry_run=True,
                                      out_dir=tmp_path / "out")
    assert dry_count == 3
    assert not state_path.exists()  # no footprint at all

    real_count = cards_to_discord.run(lang="sq", max_per_run=5, first_run_post=3,
                                       webhook_url="https://discord.example/webhook",
                                       hashtags="#Albania", state_path=state_path,
                                       dry_run=False, out_dir=tmp_path / "out")
    assert real_count == 3  # still a first run -- dry-run didn't consume it


def test_build_message_hard_capped_at_1990_chars():
    story = NEWEST_FIRST[0]
    msg = cards_to_discord.build_message(story, "caption " * 500)
    assert len(msg) <= 1990


def test_main_requires_webhook_unless_dry_run(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["cards_to_discord.py"])
    assert cards_to_discord.main() == 1
