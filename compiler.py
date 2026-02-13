from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CompileError(RuntimeError):
    pass


_SCHEMA_KEYS: tuple[str, ...] = (
    "project_summary",
    "core_objective",
    "architecture_overview",
    "tech_stack",
    "key_decisions",
    "constraints",
    "assumptions",
    "open_problems",
    "risks",
    "todos",
    "current_focus",
    "next_steps",
)


def _empty_context() -> dict[str, Any]:
    return {
        "project_summary": "",
        "core_objective": "",
        "architecture_overview": "",
        "tech_stack": [],
        "key_decisions": [],
        "constraints": [],
        "assumptions": [],
        "open_problems": [],
        "risks": [],
        "todos": [],
        "current_focus": "",
        "next_steps": [],
    }


def _validate_context(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise CompileError("Gemini output is not a JSON object")

    extra = set(obj.keys()) - set(_SCHEMA_KEYS)
    missing = set(_SCHEMA_KEYS) - set(obj.keys())
    if extra:
        raise CompileError(f"Gemini output contains extra fields: {sorted(extra)}")
    if missing:
        raise CompileError(f"Gemini output missing fields: {sorted(missing)}")

    def _require_str(key: str) -> str:
        v = obj.get(key)
        if isinstance(v, str):
            return v
        if v is None:
            return ""
        raise CompileError(f"Field {key!r} must be a string")

    def _require_str_list(key: str) -> list[str]:
        v = obj.get(key)
        if v is None:
            return []
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            raise CompileError(f"Field {key!r} must be an array of strings")
        return v

    validated = {
        "project_summary": _require_str("project_summary"),
        "core_objective": _require_str("core_objective"),
        "architecture_overview": _require_str("architecture_overview"),
        "tech_stack": _require_str_list("tech_stack"),
        "key_decisions": _require_str_list("key_decisions"),
        "constraints": _require_str_list("constraints"),
        "assumptions": _require_str_list("assumptions"),
        "open_problems": _require_str_list("open_problems"),
        "risks": _require_str_list("risks"),
        "todos": _require_str_list("todos"),
        "current_focus": _require_str("current_focus"),
        "next_steps": _require_str_list("next_steps"),
    }

    return validated


def _format_messages(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        label = "User" if role == "user" else "Assistant" if role == "assistant" else role
        lines.append(f"{label}: {content}")
    return "\n\n".join(lines)


def _build_prompt(messages: list[dict[str, str]]) -> str:
    schema = "\n".join(
        [
            "{",
            '  "project_summary": string,',
            '  "core_objective": string,',
            '  "architecture_overview": string,',
            '  "tech_stack": string[],',
            '  "key_decisions": string[],',
            '  "constraints": string[],',
            '  "assumptions": string[],',
            '  "open_problems": string[],',
            '  "risks": string[],',
            '  "todos": string[],',
            '  "current_focus": string,',
            '  "next_steps": string[]',
            "}",
        ]
    )

    instruction = "\n".join(
        [
            "You are a strict information extraction system.",
            "Given a chronological chat conversation, extract ONLY what is explicitly present.",
            "Do NOT hallucinate. Do NOT infer unstated facts.",
            "Return ONLY valid JSON and nothing else.",
            "No markdown. No backticks. No commentary.",
            "Output must match this exact schema (no extra keys):",
            schema,
            "Rules:",
            "- Use empty string for missing string values.",
            "- Use empty array for missing list values.",
            "- Arrays must contain strings only.",
        ]
    )

    convo = _format_messages(messages)
    return instruction + "\n\nConversation:\n" + convo


def _call_gemini(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            # Optional dependency; fall back to manual parsing below.
            pass

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            for env_path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
                try:
                    if not env_path.exists():
                        continue
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        s = line.strip()
                        if not s or s.startswith("#"):
                            continue
                        if not s.startswith("GEMINI_API_KEY="):
                            continue
                        value = s.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            os.environ.setdefault("GEMINI_API_KEY", value)
                            api_key = value
                            break
                except OSError:
                    continue
                if api_key:
                    break
        if not api_key:
            raise CompileError(
                "GEMINI_API_KEY environment variable is missing (set it or provide a .env file)"
            )

    model = "gemini-3-flash-preview"
    base = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    url = base + "?" + urlencode({"key": api_key})

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
    }

    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            status_code = int(getattr(resp, "status", 200) or 200)
    except HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = ""
        raise CompileError(f"Gemini request failed (HTTP {e.code}): {detail}".strip()) from e
    except URLError as e:
        raise CompileError(f"Gemini request failed: {e}") from e

    _ = time.perf_counter() - t0
    if status_code < 200 or status_code >= 300:
        raise CompileError(f"Gemini request failed (HTTP {status_code})")

    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        raise CompileError(f"Gemini returned non-JSON response: {e}") from e

    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content") or {}
        parts = content.get("parts")
        if isinstance(parts, list) and parts:
            text = parts[0].get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    raise CompileError("Gemini response did not contain candidates/content/parts text")


def _parse_json_strict(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise CompileError(f"Gemini returned invalid JSON: {e}") from e

    return _validate_context(obj)


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _merge_contexts(contexts: list[dict[str, Any]]) -> dict[str, Any]:
    if not contexts:
        return _empty_context()

    merged = _empty_context()

    list_keys = {
        "tech_stack",
        "key_decisions",
        "constraints",
        "assumptions",
        "open_problems",
        "risks",
        "todos",
        "next_steps",
    }

    for ctx in contexts:
        for k in list_keys:
            merged[k] = _dedupe([*merged[k], *ctx.get(k, [])])

    for k in ("project_summary", "core_objective", "architecture_overview", "current_focus"):
        for ctx in contexts:
            v = ctx.get(k)
            if isinstance(v, str) and v.strip():
                merged[k] = v

    return merged


def compile_context(
    messages: list[dict[str, str]],
    *,
    chunk_message_threshold: int = 120,
) -> dict[str, Any]:
    if not isinstance(messages, list):
        raise CompileError("messages must be a list")

    chunks: list[list[dict[str, str]]]
    if len(messages) <= chunk_message_threshold:
        chunks = [messages]
    else:
        chunks = []
        for i in range(0, len(messages), chunk_message_threshold):
            chunks.append(messages[i : i + chunk_message_threshold])

    results: list[dict[str, Any]] = []

    for chunk in chunks:
        prompt = _build_prompt(chunk)

        last_err: Exception | None = None
        for attempt in range(2):
            try:
                text = _call_gemini(prompt)
                results.append(_parse_json_strict(text))
                last_err = None
                break
            except CompileError as e:
                last_err = e
                if attempt == 0:
                    # Retry once with a stronger reminder.
                    prompt = (
                        prompt
                        + "\n\nIMPORTANT: Output MUST be strict JSON matching the schema exactly. No extra text."
                    )
                    continue
                raise

        if last_err is not None:
            raise last_err

    return _merge_contexts(results)
