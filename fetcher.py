from __future__ import annotations

import re
import time

import requests


class FetchError(RuntimeError):
    pass


def _validate_share_url(url: str) -> None:
    if not isinstance(url, str) or not url.strip():
        raise FetchError("Invalid share link: empty url")

    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        raise FetchError("Invalid share link: must start with http:// or https://")

    if "chat.openai.com/share/" not in url and "chatgpt.com/share/" not in url:
        raise FetchError("Invalid share link: expected a public ChatGPT share URL")


def fetch_html(url: str, *, timeout_s: int = 30) -> str:
    """Fetch raw HTML for a public ChatGPT share page."""

    _validate_share_url(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": "https://chatgpt.com/",
    }

    session = requests.Session()
    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            resp = session.get(url, headers=headers, timeout=timeout_s)
            last_exc = None
            break
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if attempt < 5:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise FetchError(f"Failed to fetch share link: {e}") from e
        except requests.RequestException as e:
            raise FetchError(f"Failed to fetch share link: {e}") from e

    if last_exc is not None:
        raise FetchError(f"Failed to fetch share link: {last_exc}")

    if resp.status_code != 200:
        raise FetchError(
            f"Failed to fetch share link: HTTP {resp.status_code} {resp.reason}"
        )

    return resp.text