from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StorageError(RuntimeError):
    pass


_OG_TITLE_RE = re.compile(
    r"<meta[^>]+property=(?:\"og:title\"|'og:title')[^>]+content=(?:\"(?P<t1>[^\"]*)\"|'(?P<t2>[^']*)')[^>]*>",
    flags=re.IGNORECASE,
)
_TITLE_TAG_RE = re.compile(r"<title>(?P<title>.*?)</title>", flags=re.IGNORECASE | re.DOTALL)


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_share_id(share_url: str) -> str:
    if not isinstance(share_url, str) or not share_url.strip():
        raise StorageError("Invalid share_url: empty")

    m = re.search(r"/share/(?P<id>[A-Za-z0-9_-]+)", share_url)
    if not m:
        raise StorageError("Invalid share_url: could not extract share_id")
    return m.group("id")


def _extract_title_from_html(html: str) -> str | None:
    if not isinstance(html, str) or not html.strip():
        return None

    m = _OG_TITLE_RE.search(html)
    if m:
        t = (m.group("t1") or m.group("t2") or "").strip()
        if t:
            return t

    m2 = _TITLE_TAG_RE.search(html)
    if m2:
        t2 = (m2.group("title") or "").strip()
        t2 = re.sub(r"\s+", " ", t2)
        if t2:
            return t2

    return None


def sanitize_chat_title(title: str) -> str:
    if not isinstance(title, str):
        title = ""
    s = title.strip().lower()
    s = s.replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def determine_chat_title(*, share_id: str, html: str) -> str:
    raw = _extract_title_from_html(html)
    if raw:
        sanitized = sanitize_chat_title(raw)
        if sanitized:
            return sanitized
    return f"chat_{share_id[:8]}"


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise StorageError(f"Failed to write file: {path}: {e}") from e


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise StorageError(f"Failed to read metadata: {e}") from e

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise StorageError(f"Invalid metadata.json: {e}") from e

    if not isinstance(obj, dict):
        raise StorageError("Invalid metadata.json: must be an object")

    return obj


def _find_existing_chat_dir(data_dir: Path, share_id: str) -> Path | None:
    if not data_dir.exists():
        return None

    try:
        for child in data_dir.iterdir():
            if not child.is_dir():
                continue
            meta_path = child / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                meta = _read_metadata(meta_path)
            except StorageError:
                continue
            if meta.get("share_id") == share_id:
                return child
    except OSError as e:
        raise StorageError(f"Failed to scan data directory: {e}") from e

    return None


def store_archive(
    *,
    share_url: str,
    html: str,
    archive: dict[str, Any],
    message_count: int,
    data_root: Path | None = None,
) -> Path:
    if data_root is None:
        data_root = Path("data")

    share_id = extract_share_id(share_url)

    try:
        data_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise StorageError(f"Failed to create data directory: {e}") from e

    existing_dir = _find_existing_chat_dir(data_root, share_id)

    if existing_dir is not None:
        chat_dir = existing_dir
        meta_path = chat_dir / "metadata.json"
        meta = _read_metadata(meta_path)

        stored_at = meta.get("stored_at")
        if not isinstance(stored_at, str) or not stored_at.strip():
            stored_at = _iso_utc_now()

        chat_title = meta.get("chat_title")
        if not isinstance(chat_title, str) or not chat_title.strip():
            chat_title = chat_dir.name

        new_meta = {
            "share_url": share_url,
            "share_id": share_id,
            "chat_title": chat_title,
            "stored_at": stored_at,
            "last_updated_at": _iso_utc_now(),
            "message_count": int(message_count),
        }
    else:
        chat_title = determine_chat_title(share_id=share_id, html=html)
        chat_dir = data_root / chat_title

        # Prevent mixing: if a folder name exists but belongs to different share_id, suffix deterministically.
        if chat_dir.exists():
            meta_path = chat_dir / "metadata.json"
            if meta_path.exists():
                meta = _read_metadata(meta_path)
                if meta.get("share_id") != share_id:
                    chat_dir = data_root / f"{chat_title}_{share_id[:8]}"

        try:
            chat_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Failed to create chat directory: {e}") from e

        now = _iso_utc_now()
        new_meta = {
            "share_url": share_url,
            "share_id": share_id,
            "chat_title": chat_dir.name,
            "stored_at": now,
            "last_updated_at": now,
            "message_count": int(message_count),
        }

    archive_path = chat_dir / "archive.json"
    metadata_path = chat_dir / "metadata.json"

    archive_text = json.dumps(archive, ensure_ascii=False, indent=2) + "\n"
    meta_text = json.dumps(new_meta, ensure_ascii=False, indent=2) + "\n"

    _atomic_write_text(archive_path, archive_text)
    _atomic_write_text(metadata_path, meta_text)

    return chat_dir
