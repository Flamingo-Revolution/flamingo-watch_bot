import httpx
import pytest

from bot import discord_webhook


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_post_sends_multipart_with_payload_json_and_file():
    seen = {}

    def handler(request):
        seen["content_type"] = request.headers.get("content-type", "")
        seen["body"] = request.content
        return httpx.Response(200, json={"id": "123"})

    resp = discord_webhook.post("https://discord.example/webhook", "hello", "card.jpg",
                                 b"fakejpegbytes", client=_client(handler))
    assert resp.status_code == 200
    assert "multipart/form-data" in seen["content_type"]
    assert b"card.jpg" in seen["body"]
    assert b"fakejpegbytes" in seen["body"]
    assert b"payload_json" in seen["body"]


def test_post_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(discord_webhook.time, "sleep", lambda _: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"retry_after": 0.01})
        return httpx.Response(200, json={"id": "123"})

    resp = discord_webhook.post("https://discord.example/webhook", "hi", "f.jpg", b"x",
                                 client=_client(handler))
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_post_raises_after_retries_exhausted(monkeypatch):
    monkeypatch.setattr(discord_webhook.time, "sleep", lambda _: None)

    def handler(request):
        return httpx.Response(429, json={"retry_after": 0.01})

    with pytest.raises(httpx.HTTPStatusError):
        discord_webhook.post("https://discord.example/webhook", "hi", "f.jpg", b"x",
                              client=_client(handler))


def test_post_text_alert_sends_content():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, json={})

    discord_webhook.post_text("https://discord.example/webhook", "alert message",
                               client=_client(handler))
    assert b"alert message" in seen["body"]
