from __future__ import annotations

import json
import re
from typing import Any


_SCHEMA_TEMPLATE: dict[str, Any] = {
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


_VALIDATION_OUTPUT_TEMPLATE: dict[str, Any] = {
    "structural_validation": {
        "all_required_fields_present": True,
        "no_extra_fields": True,
        "valid_json_format": True,
        "data_type_consistent": True,
    },
    "semantic_validation": {
        "hallucination_detected": False,
        "distortion_detected": False,
        "critical_omissions": [],
    },
    "determinism_assessment": {
        "risk_level": "LOW",
        "unstable_fields": [],
    },
    "stability_score": 100,
    "final_verdict": "STABLE",
}


class ValidationError(RuntimeError):
    pass


def _new_report() -> dict[str, Any]:
    return json.loads(json.dumps(_VALIDATION_OUTPUT_TEMPLATE))


def _contains_markdown_markers(text: str) -> bool:
    s = text.strip()
    if "```" in s:
        return True
    if s.startswith("#"):
        return True
    return False


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _extract_terms(value: str) -> list[str]:
    # Extract “tech looking” tokens for conservative hallucination checks.
    # Keep it deterministic and simple.
    return re.findall(r"[A-Za-z][A-Za-z0-9_.+#\-/]{1,}", value or "")


def _validate_schema_types_and_keys(ctx: Any) -> tuple[bool, bool, bool, list[str]]:
    """Return (all_required_present, no_extra, types_ok, errors)."""

    errors: list[str] = []

    if not isinstance(ctx, dict):
        return False, False, False, ["Top-level context must be an object"]

    required_top = set(_SCHEMA_TEMPLATE.keys())
    ctx_keys = set(ctx.keys())

    missing_top = required_top - ctx_keys
    extra_top = ctx_keys - required_top

    all_required = not missing_top
    no_extra = not extra_top

    if missing_top:
        errors.append(f"Missing top-level keys: {sorted(missing_top)}")
    if extra_top:
        errors.append(f"Extra top-level keys: {sorted(extra_top)}")

    def require_obj(path: str) -> dict[str, Any] | None:
        v = ctx.get(path)
        if isinstance(v, dict):
            return v
        errors.append(f"{path} must be an object")
        return None

    def require_list(path: str) -> list[Any] | None:
        v = ctx.get(path)
        if isinstance(v, list):
            return v
        errors.append(f"{path} must be an array")
        return None

    types_ok = True

    meta = ctx.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        types_ok = False
    else:
        allowed = set(_SCHEMA_TEMPLATE["meta"].keys())
        missing = allowed - set(meta.keys())
        extra = set(meta.keys()) - allowed
        if missing:
            errors.append(f"meta missing keys: {sorted(missing)}")
            types_ok = False
        if extra:
            errors.append(f"meta extra keys: {sorted(extra)}")
            types_ok = False

        for k in ("conversation_topic", "primary_domain", "llm_model", "api_used"):
            if k in meta and meta[k] is None:
                errors.append(f"meta.{k} must not be null")
                types_ok = False
            if k in meta and not isinstance(meta[k], str):
                errors.append(f"meta.{k} must be a string")
                types_ok = False

        for k in ("secondary_domains", "languages_mentioned", "tools_or_services"):
            if k in meta and meta[k] is None:
                errors.append(f"meta.{k} must not be null")
                types_ok = False
            if k in meta and (
                not isinstance(meta[k], list) or any(not isinstance(x, str) for x in meta[k])
            ):
                errors.append(f"meta.{k} must be an array of strings")
                types_ok = False

    user_objective = ctx.get("user_objective")
    if not isinstance(user_objective, dict):
        errors.append("user_objective must be an object")
        types_ok = False
    else:
        allowed = set(_SCHEMA_TEMPLATE["user_objective"].keys())
        missing = allowed - set(user_objective.keys())
        extra = set(user_objective.keys()) - allowed
        if missing:
            errors.append(f"user_objective missing keys: {sorted(missing)}")
            types_ok = False
        if extra:
            errors.append(f"user_objective extra keys: {sorted(extra)}")
            types_ok = False

        for k in ("explicit_goal", "implicit_goal", "desired_output"):
            if k in user_objective and user_objective[k] is None:
                errors.append(f"user_objective.{k} must not be null")
                types_ok = False
            if k in user_objective and not isinstance(user_objective[k], str):
                errors.append(f"user_objective.{k} must be a string")
                types_ok = False

        k = "scope_boundaries"
        if k in user_objective and user_objective[k] is None:
            errors.append("user_objective.scope_boundaries must not be null")
            types_ok = False
        if k in user_objective and (
            not isinstance(user_objective[k], list)
            or any(not isinstance(x, str) for x in user_objective[k])
        ):
            errors.append("user_objective.scope_boundaries must be an array of strings")
            types_ok = False

    technical_context = ctx.get("technical_context")
    if not isinstance(technical_context, dict):
        errors.append("technical_context must be an object")
        types_ok = False
    else:
        allowed = set(_SCHEMA_TEMPLATE["technical_context"].keys())
        missing = allowed - set(technical_context.keys())
        extra = set(technical_context.keys()) - allowed
        if missing:
            errors.append(f"technical_context missing keys: {sorted(missing)}")
            types_ok = False
        if extra:
            errors.append(f"technical_context extra keys: {sorted(extra)}")
            types_ok = False

        for k in ("architecture_style", "project_type", "execution_environment"):
            if k in technical_context and technical_context[k] is None:
                errors.append(f"technical_context.{k} must not be null")
                types_ok = False
            if k in technical_context and not isinstance(technical_context[k], str):
                errors.append(f"technical_context.{k} must be a string")
                types_ok = False

        k = "folder_structure_defined"
        if k in technical_context and technical_context[k] is None:
            errors.append("technical_context.folder_structure_defined must not be null")
            types_ok = False
        if k in technical_context and not isinstance(technical_context[k], bool):
            errors.append("technical_context.folder_structure_defined must be boolean")
            types_ok = False

        for k in ("environment_variables", "constraints"):
            if k in technical_context and technical_context[k] is None:
                errors.append(f"technical_context.{k} must not be null")
                types_ok = False
            if k in technical_context and (
                not isinstance(technical_context[k], list)
                or any(not isinstance(x, str) for x in technical_context[k])
            ):
                errors.append(f"technical_context.{k} must be an array of strings")
                types_ok = False

    key_decisions = ctx.get("key_decisions")
    if not isinstance(key_decisions, list):
        errors.append("key_decisions must be an array")
        types_ok = False
    else:
        for i, it in enumerate(key_decisions):
            if not isinstance(it, dict):
                errors.append(f"key_decisions[{i}] must be an object")
                types_ok = False
                continue
            allowed = {"decision", "reason"}
            missing = allowed - set(it.keys())
            extra = set(it.keys()) - allowed
            if missing:
                errors.append(f"key_decisions[{i}] missing keys: {sorted(missing)}")
                types_ok = False
            if extra:
                errors.append(f"key_decisions[{i}] extra keys: {sorted(extra)}")
                types_ok = False
            for k in ("decision", "reason"):
                if it.get(k) is None:
                    errors.append(f"key_decisions[{i}].{k} must not be null")
                    types_ok = False
                if not isinstance(it.get(k), str):
                    errors.append(f"key_decisions[{i}].{k} must be a string")
                    types_ok = False

    task_structure = ctx.get("task_structure")
    if not isinstance(task_structure, dict):
        errors.append("task_structure must be an object")
        types_ok = False
    else:
        allowed = {"phases"}
        missing = allowed - set(task_structure.keys())
        extra = set(task_structure.keys()) - allowed
        if missing:
            errors.append(f"task_structure missing keys: {sorted(missing)}")
            types_ok = False
        if extra:
            errors.append(f"task_structure extra keys: {sorted(extra)}")
            types_ok = False

        phases = task_structure.get("phases")
        if not isinstance(phases, list):
            errors.append("task_structure.phases must be an array")
            types_ok = False
        else:
            for i, ph in enumerate(phases):
                if not isinstance(ph, dict):
                    errors.append(f"task_structure.phases[{i}] must be an object")
                    types_ok = False
                    continue
                allowed2 = {"phase_name", "description", "expected_output"}
                missing2 = allowed2 - set(ph.keys())
                extra2 = set(ph.keys()) - allowed2
                if missing2:
                    errors.append(f"task_structure.phases[{i}] missing keys: {sorted(missing2)}")
                    types_ok = False
                if extra2:
                    errors.append(f"task_structure.phases[{i}] extra keys: {sorted(extra2)}")
                    types_ok = False
                for k in ("phase_name", "description", "expected_output"):
                    if ph.get(k) is None:
                        errors.append(f"task_structure.phases[{i}].{k} must not be null")
                        types_ok = False
                    if not isinstance(ph.get(k), str):
                        errors.append(f"task_structure.phases[{i}].{k} must be a string")
                        types_ok = False

    for k in ("explicit_risks", "important_entities"):
        v = ctx.get(k)
        if v is None:
            errors.append(f"{k} must not be null")
            types_ok = False
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            errors.append(f"{k} must be an array of strings")
            types_ok = False

    if errors:
        # Keys presence vs types are different dimensions in output.
        pass

    if missing_top:
        all_required = False
    if extra_top:
        no_extra = False

    if not types_ok:
        pass

    return all_required, no_extra, types_ok, errors


def _flatten_context_values(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(path: str, v: Any) -> None:
        if v is None:
            return
        if isinstance(v, str):
            if v.strip():
                out.append((path, v))
            return
        if isinstance(v, bool):
            return
        if isinstance(v, list):
            for i, it in enumerate(v):
                walk(f"{path}[{i}]", it)
            return
        if isinstance(v, dict):
            for k, it in v.items():
                walk(f"{path}.{k}" if path else k, it)
            return

    walk("", ctx)
    return out


def _semantic_audit(conversation_text: str, ctx: dict[str, Any]) -> tuple[bool, bool, list[str], str, list[str]]:
    """Return (hallucination, distortion, omissions, risk_level, unstable_fields)."""

    convo_norm = _normalize_text(conversation_text)

    hallucination = False
    distortion = False
    omissions: list[str] = []
    unstable_fields: list[str] = []

    # Hallucination heuristic:
    # - If context contains non-empty strings (or string list entries)
    #   whose normalized form is not found in the conversation, flag.
    # - Additionally, check “tech-looking” terms inside those values.
    # This is conservative and deterministic; it may over-report, which is acceptable
    # for a strict validator.
    for path, value in _flatten_context_values(ctx):
        if not isinstance(value, str) or not value.strip():
            continue

        if _contains_markdown_markers(value):
            distortion = True

        v_norm = _normalize_text(value)
        if v_norm and v_norm not in convo_norm:
            # If it’s not verbatim present, check if it looks like a summary.
            # For summaries, raise determinism risk instead of immediate hallucination
            # unless it contains new "term" tokens.
            terms = _extract_terms(value)
            new_terms = [t for t in terms if _normalize_text(t) not in convo_norm]
            if new_terms:
                hallucination = True
            else:
                unstable_fields.append(path)

    # Omission heuristic: if conversation contains explicit constants, ensure they appear.
    explicit_markers: list[tuple[str, str, str]] = [
        ("GEMINI_API_KEY", "$.technical_context.environment_variables", "Missing explicit env var GEMINI_API_KEY"),
        ("gemini-3-flash-preview", "$.meta.llm_model", "Missing explicit model gemini-3-flash-preview"),
        ("google.genai", "$.meta.api_used", "Missing explicit api_used/google.genai reference"),
    ]

    flat = {p: v for p, v in _flatten_context_values(ctx)}
    flat_values_norm = _normalize_text("\n".join(v for _, v in flat.items()))

    for marker, _expected_path, msg in explicit_markers:
        if _normalize_text(marker) in convo_norm and _normalize_text(marker) not in flat_values_norm:
            omissions.append(msg)

    # Distortion heuristic: if scope boundaries mention forbidden actions, ensure they are not contradicted.
    # We cannot prove meaning changes deterministically without an LLM, so we only flag if context
    # introduces strong modality (must/always/never) not present in conversation.
    strong_modal = re.compile(r"\b(must|always|never|required)\b", re.IGNORECASE)
    convo_has_modal = bool(strong_modal.search(conversation_text))

    for path, value in _flatten_context_values(ctx):
        if strong_modal.search(value) and not convo_has_modal:
            distortion = True

    # Determinism risk assessment: interpretative fields are inherently unstable.
    interpretative_paths = [
        "meta.conversation_topic",
        "meta.primary_domain",
        "user_objective.implicit_goal",
        "technical_context.architecture_style",
        "technical_context.project_type",
        "technical_context.execution_environment",
    ]
    for p in interpretative_paths:
        unstable_fields.append(p)

    unstable_fields = sorted(set(unstable_fields))

    risk_level = "LOW"
    if unstable_fields:
        risk_level = "MEDIUM"
    if hallucination or distortion or len(unstable_fields) > 12:
        risk_level = "HIGH" if unstable_fields else "MEDIUM"

    return hallucination, distortion, omissions, risk_level, unstable_fields


def _score_and_verdict(
    *,
    schema_broken: bool,
    hallucinations: int,
    major_omissions: int,
    distortions: int,
    risk_level: str,
) -> tuple[int, str]:
    score = 100

    if schema_broken:
        score -= 40

    score -= 30 * hallucinations
    score -= 20 * major_omissions
    score -= 15 * distortions

    if risk_level == "HIGH":
        score -= 10
    elif risk_level == "MEDIUM":
        score -= 5

    if score < 0:
        score = 0

    if hallucinations > 0 and score > 60:
        score = 60

    if score >= 90:
        verdict = "STABLE"
    elif score >= 75:
        verdict = "NEEDS_REFINEMENT"
    else:
        verdict = "UNSTABLE"

    if score < 50:
        verdict = "UNSTABLE"

    return score, verdict


def validate(conversation_text: str, context_json_text: str) -> dict[str, Any]:
    report = _new_report()

    # Parse JSON
    try:
        ctx_obj = json.loads(context_json_text)
    except json.JSONDecodeError:
        report["structural_validation"]["valid_json_format"] = False
        report["structural_validation"]["all_required_fields_present"] = False
        report["structural_validation"]["no_extra_fields"] = False
        report["structural_validation"]["data_type_consistent"] = False

        score, verdict = _score_and_verdict(
            schema_broken=True,
            hallucinations=0,
            major_omissions=0,
            distortions=0,
            risk_level="LOW",
        )
        report["stability_score"] = score
        report["final_verdict"] = "UNSTABLE"
        return report

    all_required, no_extra, types_ok, _errors = _validate_schema_types_and_keys(ctx_obj)
    report["structural_validation"]["all_required_fields_present"] = bool(all_required)
    report["structural_validation"]["no_extra_fields"] = bool(no_extra)
    report["structural_validation"]["valid_json_format"] = True
    report["structural_validation"]["data_type_consistent"] = bool(types_ok)

    schema_broken = (not all_required) or (not no_extra) or (not types_ok)

    hallucination, distortion, omissions, risk_level, unstable_fields = _semantic_audit(
        conversation_text, ctx_obj
    )

    report["semantic_validation"]["hallucination_detected"] = bool(hallucination)
    report["semantic_validation"]["distortion_detected"] = bool(distortion)
    report["semantic_validation"]["critical_omissions"] = omissions

    report["determinism_assessment"]["risk_level"] = risk_level
    report["determinism_assessment"]["unstable_fields"] = unstable_fields

    hallucination_count = 1 if hallucination else 0
    distortion_count = 1 if distortion else 0
    omission_count = len(omissions)

    score, verdict = _score_and_verdict(
        schema_broken=schema_broken,
        hallucinations=hallucination_count,
        major_omissions=omission_count,
        distortions=distortion_count,
        risk_level=risk_level,
    )

    if not all_required:
        verdict = "UNSTABLE"
    if not report["structural_validation"]["valid_json_format"]:
        verdict = "UNSTABLE"

    report["stability_score"] = score
    report["final_verdict"] = verdict

    return report
