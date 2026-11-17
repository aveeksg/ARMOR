"""Shared red-team adversary request/delta helpers for Phases 3 and 5."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import MAX_AUDIT_REVISIONS, RunDir

VERDICT_CONFIRM = "CONFIRM"
VERDICT_REVISE = "REVISE"
VERDICT_INVESTIGATE = "INVESTIGATE"

ALLOWED_VERDICTS = {VERDICT_CONFIRM, VERDICT_REVISE, VERDICT_INVESTIGATE}

AUDIT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["verdicts"],
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["sid", "verdict"],
                "properties": {
                    "sid": {"type": "string"},
                    "verdict": {"type": "string", "enum": sorted(ALLOWED_VERDICTS)},
                    "critique": {"type": "string"},
                    "revised_row": {"type": "object"},
                },
            },
        },
        "overall_note": {"type": "string"},
    },
}

_ADVERSARY_INSTRUCTIONS = (
    "You are an independent red-team adversary auditing the target_artifact rows. "
    "For each row, assign verdict in {'CONFIRM', 'REVISE', 'INVESTIGATE'}. "
    "If 'REVISE', provide a critique and a revised_row of the exact same shape as the target row. "
    "You may NOT invent new sids or change scope. "
    "You may NOT read source files beyond the file:line citations already present in the target rows. "
    "Output ONLY strict JSON conforming to response_schema (no Markdown fences, no prose)."
)


def build_request(
    audit_kind: str,
    target_artifact: dict[str, Any],
    rows_key: str,
    revision: int,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "phase": audit_kind,
        "revision": revision,
        "max_revisions": MAX_AUDIT_REVISIONS,
        "instructions": _ADVERSARY_INSTRUCTIONS,
        "target_rows_key": rows_key,
        "target_artifact": target_artifact,
        "extra_context": extra_context or {},
        "response_schema": AUDIT_RESPONSE_SCHEMA,
    }


def write_request(run: RunDir, phase: str, payload: dict[str, Any]) -> Path:
    req_path = run.request(phase)
    req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return req_path


def read_response(run: RunDir, phase: str) -> dict[str, Any]:
    resp_path = run.response(phase)
    if not resp_path.is_file():
        raise SystemExit(f"{phase} response not found at {resp_path}")
    try:
        return json.loads(resp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{phase} response invalid JSON: {exc}") from exc


def apply_deltas(
    target_artifact: dict[str, Any],
    rows_key: str,
    audit_response: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    original_rows: list[dict[str, Any]] = list(target_artifact.get(rows_key, []))
    by_sid: dict[str, dict[str, Any]] = {str(r["sid"]): dict(r) for r in original_rows}
    order: list[str] = [str(r["sid"]) for r in original_rows]

    counts: dict[str, int] = {v: 0 for v in sorted(ALLOWED_VERDICTS)}
    revisions_applied: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []
    unknown_sids: list[str] = []

    for item in audit_response.get("verdicts", []):
        if not isinstance(item, dict):
            continue
        verdict = item.get("verdict")
        if verdict not in ALLOWED_VERDICTS:
            continue
        counts[verdict] += 1
        sid = str(item.get("sid") or "")
        if sid not in by_sid:
            unknown_sids.append(sid)
            continue

        critique = str(item.get("critique") or "")
        if verdict == VERDICT_REVISE:
            revised = item.get("revised_row")
            if isinstance(revised, dict):
                old_row = dict(by_sid[sid])
                new_row = {**old_row, **revised, "sid": sid}
                by_sid[sid] = new_row
                revisions_applied.append(
                    {
                        "sid": sid,
                        "critique": critique,
                        "before": old_row,
                        "after": new_row,
                    }
                )
        elif verdict == VERDICT_INVESTIGATE:
            open_questions.append({"sid": sid, "critique": critique})

    new_rows = [by_sid[sid] for sid in order]
    new_artifact = {**target_artifact, rows_key: new_rows}
    summary = {
        "verdict_counts": counts,
        "revisions_applied": revisions_applied,
        "open_questions": open_questions,
        "unknown_sids": unknown_sids,
        "overall_note": str(audit_response.get("overall_note") or ""),
    }
    return new_artifact, summary


def converged(summary: dict[str, Any], revision: int) -> bool:
    return revision >= MAX_AUDIT_REVISIONS or len(summary.get("revisions_applied", [])) == 0
