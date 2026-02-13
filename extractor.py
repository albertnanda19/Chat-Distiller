from __future__ import annotations

import json
import re
from typing import Any


class ExtractError(RuntimeError):
    pass


_NEXT_DATA_RE = re.compile(
    r"<script[^>]+id=(?:\"__NEXT_DATA__\"|'__NEXT_DATA__')[^>]*>(?P<json>.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)

_RR_ENQUEUE_RE = re.compile(
    r"streamController\.enqueue\(\"(?P<data>(?:\\.|[^\\\"])*?)\"\)",
    flags=re.DOTALL,
)


def extract_next_data(html: str) -> dict[str, Any]:
    """Extract and parse Next.js `__NEXT_DATA__` JSON."""

    if not isinstance(html, str) or not html.strip():
        raise ExtractError("Empty HTML; cannot extract embedded JSON")

    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ExtractError("Could not find __NEXT_DATA__ JSON in HTML")

    raw = m.group("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ExtractError(f"Failed to parse __NEXT_DATA__ JSON: {e}") from e


def _unescape_js_string_literal(s: str) -> str:
    """Unescape the content of a JS double-quoted string literal."""

    try:
        # Interpret escapes using JSON string rules (compatible enough here).
        return json.loads('"' + s + '"')
    except json.JSONDecodeError as e:
        raise ExtractError(f"Failed to unescape embedded JS string: {e}") from e


def _is_packed_key(k: str) -> bool:
    return isinstance(k, str) and len(k) > 1 and k[0] == "_" and k[1:].isdigit()


def _decode_packed_value(table: list[Any], v: Any, *, _depth: int = 0) -> Any:
    if _depth > 50:
        return v

    if isinstance(v, dict):
        out: dict[str, Any] = {}
        for k2, v2 in v.items():
            if _is_packed_key(k2):
                key_name = table[int(k2[1:])] if int(k2[1:]) < len(table) else k2
            else:
                key_name = k2
            if not isinstance(key_name, str):
                key_name = str(key_name)
            out[key_name] = _decode_packed_value(table, v2, _depth=_depth + 1)
        return out

    if isinstance(v, list):
        return [_decode_packed_value(table, x, _depth=_depth + 1) for x in v]

    if isinstance(v, int) and v >= 0 and v < len(table):
        target = table[v]
        # Heuristic: in this format, ints usually reference into the table.
        if isinstance(target, (dict, list)):
            return _decode_packed_value(table, target, _depth=_depth + 1)
        return target

    return v


def _decode_packed_mapping(table: list[Any], packed_mapping: dict[str, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for raw_id_key, raw_node_ref in packed_mapping.items():
        node_id = (
            table[int(raw_id_key[1:])]
            if _is_packed_key(raw_id_key) and int(raw_id_key[1:]) < len(table)
            else raw_id_key
        )
        if not isinstance(node_id, str):
            continue

        node_obj = raw_node_ref
        if isinstance(raw_node_ref, int) and 0 <= raw_node_ref < len(table):
            node_obj = table[raw_node_ref]

        decoded[node_id] = _decode_packed_value(table, node_obj)

    return decoded


def extract_react_router_stream_data(html: str) -> Any:
    """Extract and parse dehydrated data from React Router stream enqueue chunks."""

    decoder = json.JSONDecoder()

    matches = list(_RR_ENQUEUE_RE.finditer(html))
    if not matches:
        raise ExtractError("Could not find embedded React Router stream data in HTML")

    for m in matches:
        raw_literal = m.group("data")
        if "mapping\"" not in raw_literal and "mapping" not in raw_literal:
            continue
        if "current_node\"" not in raw_literal and "current_node" not in raw_literal:
            continue

        payload = _unescape_js_string_literal(raw_literal)
        payload = payload.strip()

        # Some chunks are prefixed like "P21:..."; we want the JSON part.
        if payload and payload[0] != "[" and ":" in payload:
            payload = payload.split(":", 1)[1].lstrip()

        try:
            arr = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if not isinstance(arr, list):
            continue

        try:
            mi = arr.index("mapping")
            ci = arr.index("current_node")
        except ValueError:
            continue

        mapping_value = arr[mi + 1] if mi + 1 < len(arr) else None
        current_node_value = arr[ci + 1] if ci + 1 < len(arr) else None

        if not isinstance(mapping_value, dict):
            continue

        mapping_decoded = (
            _decode_packed_mapping(arr, mapping_value)
            if any(_is_packed_key(k) for k in mapping_value.keys())
            else mapping_value
        )

        current_node = current_node_value if isinstance(current_node_value, str) else ""

        # In current share payloads, current_node may be a sentinel like "conversation_id".
        # Prefer the last element of linear_conversation if present.
        if current_node not in mapping_decoded:
            try:
                li = arr.index("linear_conversation")
            except ValueError:
                li = -1

            if li != -1 and li + 1 < len(arr) and isinstance(arr[li + 1], list):
                linear_raw = arr[li + 1]
                linear_decoded = _decode_packed_value(arr, linear_raw)
                if isinstance(linear_decoded, list):
                    linear_ids = [x for x in linear_decoded if isinstance(x, str)]
                    if linear_ids:
                        tail = linear_ids[-1]
                        if tail in mapping_decoded:
                            current_node = tail

        if isinstance(mapping_decoded, dict) and isinstance(current_node, str) and current_node:
            return {"mapping": mapping_decoded, "current_node": current_node}

    raise ExtractError(
        "Found React Router stream chunks, but could not parse conversation state from them"
    )


def _deep_find_conversation_state(obj: Any) -> tuple[dict[str, Any], str] | None:
    """Find a dict containing `mapping` and `current_node` anywhere in a JSON object."""

    if isinstance(obj, dict):
        if "mapping" in obj and "current_node" in obj:
            mapping = obj.get("mapping")
            current_node = obj.get("current_node")
            if isinstance(mapping, dict) and isinstance(current_node, str):
                return obj, current_node
        for v in obj.values():
            found = _deep_find_conversation_state(v)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _deep_find_conversation_state(v)
            if found is not None:
                return found
    return None


def extract_conversation_state(html: str) -> tuple[dict[str, Any], str]:
    """Return (mapping, current_node) from a share page HTML."""

    data_obj: Any
    try:
        data_obj = extract_next_data(html)
    except ExtractError:
        data_obj = extract_react_router_stream_data(html)

    found = _deep_find_conversation_state(data_obj)
    if found is None:
        raise ExtractError(
            "Could not locate conversation state (mapping/current_node) in embedded page data"
        )

    state, current_node = found
    mapping = state.get("mapping")
    if not isinstance(mapping, dict):
        raise ExtractError("Conversation mapping missing or invalid")

    return mapping, current_node