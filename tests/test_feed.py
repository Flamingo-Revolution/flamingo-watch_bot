import httpx
import pytest

from bot import feed

SAMPLE_PAYLOAD = {
    "groups": [
        {
            "key": "story-a",
            "slug": None,
            "articles": [
                {"id": 1, "url": "https://example.com/a", "source": "Outlet A",
                 "published_at": "2026-10-01T10:00:00Z", "lang": "sq",
                 "title": "Title A", "summary": "Summary A", "tags": [], "ai": True},
            ],
        },
        {
            "key": "story-b",
            "slug": None,
            "articles": [
                {"id": 2, "url": "https://example.com/b", "source": "Outlet B",
                 "published_at": "2026-10-01T09:00:00Z", "lang": "sq",
                 "title": "Title B", "summary": None, "tags": [], "ai": False},
            ],
        },
    ]
}


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_and_fetch_happy_path():
    def handler(request):
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    stories = feed.fetch("sq", client=_client(handler))
    assert [s.key for s in stories] == ["story-a", "story-b"]
    assert stories[0].title == "Title A"
    assert stories[0].summary == "Summary A"
    assert stories[0].source == "Outlet A"
    assert stories[0].url == "https://example.com/a"
    assert stories[0].published == "2026-10-01T10:00:00Z"
    assert stories[0].lang == "sq"
    assert stories[1].summary is None  # ai: false -> no AI summary available


def test_fetch_falls_back_to_next_url_when_first_fails(monkeypatch):
    monkeypatch.setenv("FEED_URL", "https://bad.example/x.json,https://good.example/y.json")

    def handler(request):
        if "bad.example" in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    stories = feed.fetch("sq", client=_client(handler))
    assert len(stories) == 2


def test_fetch_raises_clear_error_when_every_url_fails(monkeypatch):
    monkeypatch.setenv("FEED_URL", "https://bad.example/x.json")

    def handler(request):
        return httpx.Response(500)

    with pytest.raises(RuntimeError, match="Could not read the feed. Last error:"):
        feed.fetch("sq", client=_client(handler))


def test_fetch_raises_when_feed_has_zero_stories(monkeypatch):
    monkeypatch.setenv("FEED_URL", "https://good.example/empty.json")

    def handler(request):
        return httpx.Response(200, json={"groups": []})

    with pytest.raises(RuntimeError, match="Could not read the feed"):
        feed.fetch("sq", client=_client(handler))


def test_group_with_no_articles_is_skipped_not_crashed():
    payload = {"groups": [{"key": "empty-group", "articles": []}, *SAMPLE_PAYLOAD["groups"]]}

    def handler(request):
        return httpx.Response(200, json=payload)

    stories = feed.fetch("sq", client=_client(handler))
    assert len(stories) == 2


def test_default_feed_url_matches_language():
    assert feed.feed_urls("en") == ["https://flamingo-watch.com/data/articles-en.json"]
    assert feed.feed_urls("sq") == ["https://flamingo-watch.com/data/articles-sq.json"]


def test_feed_url_env_overrides_default_and_is_comma_split(monkeypatch):
    monkeypatch.setenv("FEED_URL", " https://a.example/x.json , https://b.example/y.json ")
    assert feed.feed_urls("sq") == ["https://a.example/x.json", "https://b.example/y.json"]
