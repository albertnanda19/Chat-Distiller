from __future__ import annotations

from typing import Any


class RebuildError(RuntimeError):
    pass


def _choose_terminal_node_id(mapping: dict[str, Any]) -> str | None:
    best_id: str | None = None
    best_t: float = float("-inf")

    for nid, node in mapping.items():
        if not isinstance(node, dict):
            continue
        children = node.get("children")
        if isinstance(children, list) and len(children) > 0:
            continue

        msg = node.get("message")
        if not isinstance(msg, dict):
            continue

        # Prefer assistant/user leaves; ignore system/tool.
        author = msg.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        if role not in {"user", "assistant"}:
            continue

        t = msg.get("create_time")
        if isinstance(t, (int, float)) and float(t) >= best_t:
            best_t = float(t)
            best_id = nid

    return best_id


def _flatten_content(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            text_parts: list[str] = []
            for p in parts:
                if p is None:
                    continue
                if isinstance(p, str):
                    text_parts.append(p)
                else:
                    text_parts.append(str(p))
            return "".join(text_parts)

        if "text" in content and isinstance(content.get("text"), str):
            return content["text"]

    if isinstance(content, list):
        text_parts: list[str] = []
        for p in content:
            if p is None:
                continue
            if isinstance(p, str):
                text_parts.append(p)
            else:
                text_parts.append(str(p))
        return "".join(text_parts)

    return str(content)


def _node_to_message(node: dict[str, Any]) -> dict[str, str] | None:
    message = node.get("message")
    if not isinstance(message, dict):
        return None

    author = message.get("author")
    if not isinstance(author, dict):
        return None

    role = author.get("role")
    if not isinstance(role, str) or not role:
        return None

    if role in {"system", "tool"}:
        return None

    content = message.get("content")
    if isinstance(content, dict):
        content_type = content.get("content_type")
        if content_type in {"model_editable_context", "code", "execution_output"}:
            return None
    text = _flatten_content(content).strip()
    if not text:
        return None

    return {"role": role, "content": text}


def rebuild_messages(mapping: dict[str, Any], current_node: str) -> list[dict[str, str]]:
    if not isinstance(mapping, dict) or not mapping:
        raise RebuildError("Conversation mapping is empty or invalid")
    if not isinstance(current_node, str) or not current_node:
        raise RebuildError("Current node is empty or invalid")

    if current_node not in mapping:
        inferred = _choose_terminal_node_id(mapping)
        if inferred is None:
            raise RebuildError("Current node not found in mapping, and no terminal node could be inferred")
        current_node = inferred

    path_ids: list[str] = []
    seen: set[str] = set()
    node_id: str | None = current_node

    while node_id:
        if node_id in seen:
            raise RebuildError("Cycle detected while rebuilding conversation")
        seen.add(node_id)
        path_ids.append(node_id)

        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        parent = node.get("parent")
        node_id = parent if isinstance(parent, str) and parent else None

    path_ids.reverse()

    out: list[dict[str, str]] = []
    for nid in path_ids:
        node = mapping.get(nid)
        if not isinstance(node, dict):
            continue
        msg = _node_to_message(node)
        if msg is None:
            continue
        out.append(msg)

    return out