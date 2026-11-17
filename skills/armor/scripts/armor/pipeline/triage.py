"""Phase 2: System profiling and guardrail applicability triage (LLM exchange)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import RunDir, require_phase_done

ALLOWED_STATUS = {"applies", "partial_scope", "n_a"}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["system_profile", "applicability"],
    "properties": {
        "system_profile": {
            "type": "object",
            "required": ["one_liner", "languages", "deployment_model", "user_population"],
            "properties": {
                "one_liner": {"type": "string"},
                "languages": {"type": "array", "items": {"type": "string"}},
                "deployment_model": {"type": "string"},
                "user_population": {"type": "string"},
                "ai_modalities": {"type": "array", "items": {"type": "string"}},
                "data_sensitivity": {"type": "string"},
                "notes": {"type": "string"},
            },
        },
        "applicability": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["sid", "status", "reason"],
                "properties": {
                    "sid": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(ALLOWED_STATUS)},
                    "reason": {"type": "string", "minLength": 10},
                    "scope_notes": {"type": "string"},
                },
            },
        },
    },
}

_INSTRUCTIONS = (
    "Profile the codebase under project_root and tag each of the guardrails with "
    "status in {'applies', 'partial_scope', 'n_a'}. Be conservative — prefer 'applies' "
    "when uncertain. Give a concise, project-specific reason (>=10 chars) for each row. "
    "Do not score implementation here. Cover every sid in guardrails exactly once. "
    "Output ONLY strict JSON conforming to response_schema (no Markdown fences, no prose)."
)

_MANIFEST_CANDIDATES = (
    "README.md",
    "README.rst",
    "README.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "go.mod",
    "requirements.txt",
    "Dockerfile",
    "openspec/AGENTS.md",
    "AGENTS.md",
    "CLAUDE.md",
)


def _system_profile_inputs(project: Path) -> dict[str, Any]:
    project_resolved = project.resolve()
    manifests_and_docs: dict[str, str] = {}
    for rel in _MANIFEST_CANDIDATES:
        p = project_resolved / rel
        if p.is_file():
            try:
                manifests_and_docs[rel] = p.read_text(encoding="utf-8", errors="replace")[:6000]
            except OSError:
                continue

    top_level_layout: list[str] = []
    if project_resolved.is_dir():
        for entry in sorted(project_resolved.iterdir(), key=lambda e: e.name):
            name = entry.name
            if name.startswith(".") and name != ".github":
                continue
            if entry.is_dir():
                top_level_layout.append(f"{name}/")
            else:
                top_level_layout.append(name)

    return {
        "manifests_and_docs": manifests_and_docs,
        "top_level_layout": top_level_layout,
    }


def prepare(project: Path, run: RunDir) -> Path:
    loaded = require_phase_done(run, "load")
    payload = {
        "phase": "triage",
        "project_root": str(project.resolve()),
        "instructions": _INSTRUCTIONS,
        "system_profile_inputs": _system_profile_inputs(project),
        "guardrails": loaded["guardrails"],
        "response_schema": RESPONSE_SCHEMA,
    }
    req_path = run.request("triage")
    req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return req_path


def _render_md(artifact: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Phase 2 — Triage",
        "",
        "## System Profile",
        "",
        "```json",
        json.dumps(artifact.get("system_profile", {}), indent=2),
        "```",
        "",
        "## Applicability Summary",
        "",
    ]
    by_status = artifact.get("by_status", {})
    for st in ("applies", "partial_scope", "n_a"):
        lines.append(f"- **{st}**: {by_status.get(st, 0)}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "| SID | Status | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for row in artifact.get("applicability", []):
        reason = str(row.get("reason", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.get('sid', '')} | {row.get('status', '')} | {reason} |")
    lines.append("")
    return "\n".join(lines)


def finalize(project: Path, run: RunDir) -> dict[str, Any]:
    loaded = require_phase_done(run, "load")
    resp_path = run.response("triage")
    if not resp_path.is_file():
        raise SystemExit(f"triage response not found at {resp_path}")

    try:
        resp = json.loads(resp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"triage response invalid JSON: {exc}") from exc

    known = {row["sid"] for row in loaded["guardrails"]}
    seen: set[str] = set()
    errors: list[str] = []
    cleaned_rows: list[dict[str, Any]] = []

    raw_rows = resp.get("applicability")
    if not isinstance(raw_rows, list):
        raise SystemExit("triage response invalid:\n  - 'applicability' must be a list")

    for idx, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            errors.append(f"row {idx}: not an object")
            continue
        sid = row.get("sid")
        status = row.get("status")
        reason = str(row.get("reason") or "").strip()

        if sid not in known:
            errors.append(f"{sid}: unknown sid")
            continue
        if sid in seen:
            errors.append(f"{sid}: duplicate row")
            continue
        seen.add(sid)

        if status not in ALLOWED_STATUS:
            errors.append(f"{sid}: bad status {status!r} (allowed: {sorted(ALLOWED_STATUS)})")
            continue
        if not reason:
            errors.append(f"{sid}: empty reason")
            continue

        cleaned_rows.append(
            {
                "sid": sid,
                "status": status,
                "reason": reason,
                "scope_notes": str(row.get("scope_notes") or ""),
            }
        )

    missing = sorted(known - seen)
    for sid in missing:
        errors.append(f"{sid}: missing from response")

    if errors:
        msg = "\n  - ".join(errors[:20])
        raise SystemExit(f"triage response invalid:\n  - {msg}")

    by_status = {
        "applies": sum(1 for r in cleaned_rows if r["status"] == "applies"),
        "n_a": sum(1 for r in cleaned_rows if r["status"] == "n_a"),
        "partial_scope": sum(1 for r in cleaned_rows if r["status"] == "partial_scope"),
    }

    artifact: dict[str, Any] = {
        "phase": "triage",
        "revision": 0,
        "system_profile": resp.get("system_profile") or {},
        "by_status": by_status,
        "applicability": cleaned_rows,
    }

    art_path = run.artifact("triage")
    art_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    md_path = run.root / "02_triage.md"
    md_path.write_text(_render_md(artifact), encoding="utf-8")
    return artifact
