"""Post cards to Discord via webhook (Phase 1; the bot REST API arrives in Phase 2+
when voting needs to read reactions back). Handles Discord's 429 rate-limit
response using the `retry_after` it returns.
"""
from __future__ import annotations

import json as _json
import time

import httpx

TIMEOUT = 30.0
MAX_RETRIES = 4


def post(webhook_url: str, content: str, filename: str, file_bytes: bytes,
         client: httpx.Client | None = None) -> httpx.Response:
    """POST a message + image attachment to a Discord webhook."""
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        payload = {"content": content}
        resp = None
        for _attempt in range(MAX_RETRIES):
            files = {
                "payload_json": (None, _json.dumps(payload), "application/json"),
                "files[0]": (filename, file_bytes, "image/jpeg"),
            }
            resp = client.post(webhook_url, files=files)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = 1.0
            if resp.content:
                try:
                    retry_after = float(resp.json().get("retry_after", 1))
                except (ValueError, TypeError):
                    pass
            time.sleep(retry_after + 0.5)
        resp.raise_for_status()
        return resp
    finally:
        if owns_client:
            client.close()


def post_text(webhook_url: str, content: str, client: httpx.Client | None = None) -> httpx.Response:
    """Plain text message, no attachment -- used for failure alerts (ALERT_WEBHOOK_URL)."""
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = None
        for _attempt in range(MAX_RETRIES):
            resp = client.post(webhook_url, json={"content": content[:1990]})
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = 1.0
            if resp.content:
                try:
                    retry_after = float(resp.json().get("retry_after", 1))
                except (ValueError, TypeError):
                    pass
            time.sleep(retry_after + 0.5)
        resp.raise_for_status()
        return resp
    finally:
        if owns_client:
            client.close()
