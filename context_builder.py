from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .llm_client import LLMClientError, generate_content
except ImportError:  # Allows running as a script
    from chat_distiller.llm_client import LLMClientError, generate_content


class ContextBuildError(RuntimeError):
    pass


_SCHEMA: dict[str, Any] = {
    "meta": {
        "conversation_topic": "",
        "primary_domain": "",
        "secondary_domains": [],
        "languages_mentioned": [],
        "tools_or_services": [],
        "llm_model": "",
        "api_used": "",
    },
    "user_objective": {
        "explicit_goal": "",
        "implicit_goal": "",
        "desired_output": "",
        "scope_boundaries": [],
    },
    "technical_context": {
        "architecture_style": "",
        "project_type": "",
        "execution_environment": "",
        "folder_structure_defined": True,
        "environment_variables": [],
        "constraints": [],
    },
    "key_decisions": [
        {
            "decision": "",
            "reason": "",
        }
    ],
    "task_structure": {
        "phases": [
            {
                "phase_name": "",
                "description": "",
                "expected_output": "",
            }
        ]
    },
    "explicit_risks": [],
    "important_entities": [],
}


def serialize_conversation(messages: list[dict[str, str]]) -> str:
    if not isinstance(messages, list):
        raise ContextBuildError("messages must be a list")

    blocks: list[str] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        if role == "user":
            tag = "[USER]"
        elif role == "assistant":
            tag = "[ASSISTANT]"
        else:
            tag = f"[{role.upper()}]"

        blocks.append(tag)
        blocks.append(content)
        blocks.append("")

    while blocks and blocks[-1] == "":
        blocks.pop()

    return "\n".join(blocks)


def _build_extraction_prompt(serialized_conversation: str) -> str:
    schema_json = json.dumps(_SCHEMA, ensure_ascii=False, indent=2)

    instruction = "\n".join(
        [
            "You are a deterministic JSON extractor.",
            "Extract ONLY information that is explicitly stated in the conversation.",
            "Do NOT hallucinate. Do NOT guess. Do NOT add assumptions.",
            "Do NOT interpret beyond explicit text.",
            "Return ONLY valid JSON. No markdown. No backticks. No extra text.",
            "Output MUST match the exact schema below.",
            "- Use empty string for unknown string fields.",
            "- Use empty array for unknown array fields.",
            "- Use true/false only for boolean fields.",
            "- Do NOT output null.",
            "- Do NOT add extra keys.",
            "Exact schema:",
            schema_json,
            "Conversation:",
            serialized_conversation,
        ]
    )

    return instruction


def _contains_markdown_markers(text: str) -> bool:
    s = text.strip()
    if "```" in s:
        return True
    if s.startswith("#"):
        return True
    return False


def _validate_no_extra_keys(obj: dict[str, Any], allowed_keys: set[str], where: str) -> None:
    extra = set(obj.keys()) - allowed_keys
    if extra:
        raise ContextBuildError(f"Invalid output: extra keys at {where}: {sorted(extra)}")


def _require_keys(obj: dict[str, Any], required_keys: set[str], where: str) -> None:
    missing = required_keys - set(obj.keys())
    if missing:
        raise ContextBuildError(f"Invalid output: missing keys at {where}: {sorted(missing)}")


def _require_str(v: Any, where: str) -> str:
    if v is None:
        raise ContextBuildError(f"Invalid output: null value at {where}")
    if not isinstance(v, str):
        raise ContextBuildError(f"Invalid output: expected string at {where}")
    return v


def _require_bool(v: Any, where: str) -> bool:
    if v is None:
        raise ContextBuildError(f"Invalid output: null value at {where}")
    if not isinstance(v, bool):
        raise ContextBuildError(f"Invalid output: expected boolean at {where}")
    return v


def _require_str_list(v: Any, where: str) -> list[str]:
    if v is None:
        raise ContextBuildError(f"Invalid output: null value at {where}")
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        raise ContextBuildError(f"Invalid output: expected array of strings at {where}")
    return v


def _validate_schema(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ContextBuildError("Invalid output: top-level JSON must be an object")

    top_keys = set(_SCHEMA.keys())
    _validate_no_extra_keys(obj, top_keys, "$")
    _require_keys(obj, top_keys, "$")

    meta = obj.get("meta")
    if not isinstance(meta, dict):
        raise ContextBuildError("Invalid output: meta must be an object")
    meta_keys = set(_SCHEMA["meta"].keys())
    _validate_no_extra_keys(meta, meta_keys, "$.meta")
    _require_keys(meta, meta_keys, "$.meta")

    validated_meta = {
        "conversation_topic": _require_str(meta.get("conversation_topic"), "$.meta.conversation_topic"),
        "primary_domain": _require_str(meta.get("primary_domain"), "$.meta.primary_domain"),
        "secondary_domains": _require_str_list(meta.get("secondary_domains"), "$.meta.secondary_domains"),
        "languages_mentioned": _require_str_list(meta.get("languages_mentioned"), "$.meta.languages_mentioned"),
        "tools_or_services": _require_str_list(meta.get("tools_or_services"), "$.meta.tools_or_services"),
        "llm_model": _require_str(meta.get("llm_model"), "$.meta.llm_model"),
        "api_used": _require_str(meta.get("api_used"), "$.meta.api_used"),
    }

    user_objective = obj.get("user_objective")
    if not isinstance(user_objective, dict):
        raise ContextBuildError("Invalid output: user_objective must be an object")
    uo_keys = set(_SCHEMA["user_objective"].keys())
    _validate_no_extra_keys(user_objective, uo_keys, "$.user_objective")
    _require_keys(user_objective, uo_keys, "$.user_objective")

    validated_user_objective = {
        "explicit_goal": _require_str(user_objective.get("explicit_goal"), "$.user_objective.explicit_goal"),
        "implicit_goal": _require_str(user_objective.get("implicit_goal"), "$.user_objective.implicit_goal"),
        "desired_output": _require_str(user_objective.get("desired_output"), "$.user_objective.desired_output"),
        "scope_boundaries": _require_str_list(
            user_objective.get("scope_boundaries"), "$.user_objective.scope_boundaries"
        ),
    }

    technical_context = obj.get("technical_context")
    if not isinstance(technical_context, dict):
        raise ContextBuildError("Invalid output: technical_context must be an object")
    tc_keys = set(_SCHEMA["technical_context"].keys())
    _validate_no_extra_keys(technical_context, tc_keys, "$.technical_context")
    _require_keys(technical_context, tc_keys, "$.technical_context")

    validated_technical_context = {
        "architecture_style": _require_str(
            technical_context.get("architecture_style"), "$.technical_context.architecture_style"
        ),
        "project_type": _require_str(technical_context.get("project_type"), "$.technical_context.project_type"),
        "execution_environment": _require_str(
            technical_context.get("execution_environment"), "$.technical_context.execution_environment"
        ),
        "folder_structure_defined": _require_bool(
            technical_context.get("folder_structure_defined"),
            "$.technical_context.folder_structure_defined",
        ),
        "environment_variables": _require_str_list(
            technical_context.get("environment_variables"), "$.technical_context.environment_variables"
        ),
        "constraints": _require_str_list(
            technical_context.get("constraints"), "$.technical_context.constraints"
        ),
    }

    key_decisions = obj.get("key_decisions")
    if not isinstance(key_decisions, list):
        raise ContextBuildError("Invalid output: key_decisions must be an array")
    for i, item in enumerate(key_decisions):
        if not isinstance(item, dict):
            raise ContextBuildError(f"Invalid output: key_decisions[{i}] must be an object")
        allowed = {"decision", "reason"}
        _validate_no_extra_keys(item, allowed, f"$.key_decisions[{i}]")
        _require_keys(item, allowed, f"$.key_decisions[{i}]")
        _require_str(item.get("decision"), f"$.key_decisions[{i}].decision")
        _require_str(item.get("reason"), f"$.key_decisions[{i}].reason")

    task_structure = obj.get("task_structure")
    if not isinstance(task_structure, dict):
        raise ContextBuildError("Invalid output: task_structure must be an object")
    ts_keys = {"phases"}
    _validate_no_extra_keys(task_structure, ts_keys, "$.task_structure")
    _require_keys(task_structure, ts_keys, "$.task_structure")

    phases = task_structure.get("phases")
    if not isinstance(phases, list):
        raise ContextBuildError("Invalid output: task_structure.phases must be an array")
    for i, ph in enumerate(phases):
        if not isinstance(ph, dict):
            raise ContextBuildError(f"Invalid output: task_structure.phases[{i}] must be an object")
        allowed = {"phase_name", "description", "expected_output"}
        _validate_no_extra_keys(ph, allowed, f"$.task_structure.phases[{i}]")
        _require_keys(ph, allowed, f"$.task_structure.phases[{i}]")
        _require_str(ph.get("phase_name"), f"$.task_structure.phases[{i}].phase_name")
        _require_str(ph.get("description"), f"$.task_structure.phases[{i}].description")
        _require_str(ph.get("expected_output"), f"$.task_structure.phases[{i}].expected_output")

    explicit_risks = obj.get("explicit_risks")
    explicit_risks = _require_str_list(explicit_risks, "$.explicit_risks")

    important_entities = obj.get("important_entities")
    important_entities = _require_str_list(important_entities, "$.important_entities")

    validated = {
        "meta": validated_meta,
        "user_objective": validated_user_objective,
        "technical_context": validated_technical_context,
        "key_decisions": key_decisions,
        "task_structure": {"phases": phases},
        "explicit_risks": explicit_risks,
        "important_entities": important_entities,
    }

    return validated


def build_context(messages: list[dict[str, str]]) -> dict[str, Any]:
    serialized = serialize_conversation(messages)
    prompt = _build_extraction_prompt(serialized)

    try:
        raw = generate_content(prompt)
    except LLMClientError as e:
        raise ContextBuildError(str(e)) from e

    if not isinstance(raw, str) or not raw.strip():
        raise ContextBuildError("Gemini returned empty response")

    if _contains_markdown_markers(raw):
        raise ContextBuildError("Invalid output: markdown markers detected")

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ContextBuildError(f"Gemini returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    return _validate_schema(obj)


def build_context_from_file(input_path: Path, output_path: Path) -> None:
    try:
        raw = input_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ContextBuildError(f"Failed to read input JSON: {e}") from e

    try:
        messages = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ContextBuildError(f"Input file is not valid JSON: {e}") from e

    ctx = build_context(messages)

    try:
        output_path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise ContextBuildError(f"Failed to write context.json: {e}") from e
