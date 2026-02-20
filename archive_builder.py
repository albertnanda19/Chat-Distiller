from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArchiveBuildError(RuntimeError):
    pass


def _iso_utc_now() -> str:
    # ISO 8601 UTC, stable format
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_messages(obj: Any) -> list[dict[str, str]]:
    if not isinstance(obj, list):
        raise ArchiveBuildError("Input must be a JSON array of messages")

    out: list[dict[str, str]] = []
    for i, item in enumerate(obj):
        if not isinstance(item, dict):
            raise ArchiveBuildError(f"Message at index {i} must be an object")

        if "role" not in item:
            raise ArchiveBuildError(f"Message at index {i} missing required field: role")
        if "content" not in item:
            raise ArchiveBuildError(f"Message at index {i} missing required field: content")

        role = item.get("role")
        content = item.get("content")

        if role not in ("user", "assistant"):
            raise ArchiveBuildError(
                f"Message at index {i} has invalid role {role!r} (must be 'user' or 'assistant')"
            )
        if not isinstance(content, str):
            raise ArchiveBuildError(f"Message at index {i} content must be a string")

        out.append({"role": role, "content": content})

    return out


def build_archive(messages: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(messages, list):
        raise ArchiveBuildError("messages must be a list")

    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")

    conversation: list[dict[str, Any]] = []
    for idx, m in enumerate(messages):
        role = m.get("role")
        content = m.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ArchiveBuildError(f"Invalid message structure at index {idx}")

        conversation.append(
            {
                "index": idx,
                "role": role,
                "content": content,
                "character_count": len(content),
            }
        )

    return {
        "meta": {
            "total_messages": len(conversation),
            "user_message_count": user_count,
            "assistant_message_count": assistant_count,
            "generated_at": _iso_utc_now(),
            "version": "2.0",
        },
        "conversation": conversation,
    }


def _validate_archive(obj: Any) -> list[dict[str, str]]:
    if not isinstance(obj, dict):
        raise ArchiveBuildError("Archive must be a JSON object")

    convo = obj.get("conversation")
    if not isinstance(convo, list):
        raise ArchiveBuildError("Archive missing required field: conversation")

    out: list[dict[str, str]] = []
    for i, item in enumerate(convo):
        if not isinstance(item, dict):
            raise ArchiveBuildError(f"Conversation item at index {i} must be an object")
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant"):
            raise ArchiveBuildError(
                f"Conversation item at index {i} has invalid role {role!r} (must be 'user' or 'assistant')"
            )
        if not isinstance(content, str):
            raise ArchiveBuildError(f"Conversation item at index {i} content must be a string")
        out.append({"role": role, "content": content})

    return out


def merge_archives(archive_a: dict[str, Any], archive_b: dict[str, Any]) -> dict[str, Any]:
    messages_a = _validate_archive(archive_a)
    messages_b = _validate_archive(archive_b)
    return build_archive([*messages_a, *messages_b])


def merge_archives_from_files(input_a: Path, input_b: Path, output_path: Path) -> None:
    try:
        raw_a = input_a.read_text(encoding="utf-8")
    except OSError as e:
        raise ArchiveBuildError(f"Failed to read input file A: {e}") from e

    try:
        raw_b = input_b.read_text(encoding="utf-8")
    except OSError as e:
        raise ArchiveBuildError(f"Failed to read input file B: {e}") from e

    try:
        obj_a = json.loads(raw_a)
    except json.JSONDecodeError as e:
        raise ArchiveBuildError(f"Input file A is not valid JSON: {e}") from e

    try:
        obj_b = json.loads(raw_b)
    except json.JSONDecodeError as e:
        raise ArchiveBuildError(f"Input file B is not valid JSON: {e}") from e

    merged = merge_archives(obj_a, obj_b)

    try:
        output_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        raise ArchiveBuildError(f"Failed to write output file: {e}") from e


def build_archive_from_file(input_path: Path, output_path: Path) -> None:
    try:
        raw = input_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ArchiveBuildError(f"Failed to read input file: {e}") from e

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ArchiveBuildError(f"Input file is not valid JSON: {e}") from e

    messages = _validate_messages(obj)
    archive = build_archive(messages)

    try:
        output_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise ArchiveBuildError(f"Failed to write output file: {e}") from e
