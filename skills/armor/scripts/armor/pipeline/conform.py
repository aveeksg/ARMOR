"""Phase 4: Guardrail conformance assessment and citation cross-verification (LLM exchange)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .state import RunDir, hallucination_log, require_phase_done, verify_citation

ALLOWED_VERDICTS = {"implemented", "partial", "weak", "gap", "inconclusive", "n/a"}
NON_GAP = {"implemented", "partial", "weak"}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["rows"],
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["sid", "verdict", "reasoning"],
                "properties": {
                    "sid": {"type": "string"},
                    "verdict": {"type": "string", "enum": sorted(ALLOWED_VERDICTS)},
                    "reasoning": {"type": "string", "minLength": 10},
                    "citations": {"type": "array", "items": {"type": "string"}},
                    "gap_summary": {"type": "string"},
                    "remediation": {"type": "string"},
                },
            },
        }
    },
}

_INSTRUCTIONS = """Assess the codebase under project_root against each in-scope guardrail in in_scope.

Requirements:
1. Assign a verdict from {'implemented', 'partial', 'weak', 'gap', 'inconclusive', 'n/a'}.
2. Verdicts in {'implemented', 'partial', 'weak'} MUST carry >= 1 citation in the format
   relative/path.ext:line or relative/path.ext:start-end. The Python runner cross-verifies every
   citation against project_root; invalid or out-of-bounds citations auto-demote the row to
   'inconclusive' and are logged to hallucination_log.jsonl.
3. 'remediation' is MANDATORY for verdicts in {'gap', 'weak', 'partial', 'inconclusive'} and must be:
   (1) codebase-specific (name real files/dirs; give exact target paths for new artefacts),
   (2) action-leading (start with an imperative verb; not "Implement the guardrail"),
   (3) concrete (reference real entry points + exact data/config),
   (4) anchored to the guardrail's verification_test,
   (5) free of banned phrases ("Implement the guardrail", "Add CI enforcement + persistent audit trail",
       "as appropriate", "follow best practices").
4. For verdict == 'gap', also populate 'gap_summary'.
5. Cover every input sid in in_scope exactly once.
6. Output ONLY strict JSON conforming to response_schema (no Markdown fences, no prose)."""


def _verify(project: Path, citations: Any) -> tuple[list[str], list[dict[str, str]]]:
    verified: list[str] = []
    rejected: list[dict[str, str]] = []
    if not isinstance(citations, list):
        return verified, rejected
    for raw_cit in citations:
        if not isinstance(raw_cit, str) or not raw_cit.strip():
            rejected.append({"citation": str(raw_cit), "reason": "non-string or empty citation"})
            continue
        cit = raw_cit.strip()
        ok, reason = verify_citation(project, cit)
        if ok:
            verified.append(cit)
        else:
            rejected.append({"citation": cit, "reason": reason})
    return verified, rejected


def _append_hallucinations(project: Path, phase: str, sid: str, rejected: list[dict[str, str]]) -> None:
    if not rejected:
        return
    log_path = hallucination_log(project)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    with open(log_path, "a", encoding="utf-8") as f:
        for item in rejected:
            rec = {
                "ts": ts,
                "phase": phase,
                "sid": sid,
                "citation": item["citation"],
                "reason": item["reason"],
            }
            f.write(json.dumps(rec) + "\n")


def prepare(project: Path, run: RunDir) -> Path:
    loaded = require_phase_done(run, "load")
    triage_audit = require_phase_done(run, "triage-audit")

    catalog_by_sid = {row["sid"]: row for row in loaded["guardrails"]}
    in_scope: list[dict[str, Any]] = []
    for row in triage_audit.get("applicability", []):
        if row.get("status") in ("applies", "partial_scope"):
            sid = row["sid"]
            cat = catalog_by_sid.get(sid, {})
            in_scope.append(
                {
                    "sid": sid,
                    "status": row["status"],
                    "reason": row.get("reason", ""),
                    "scope_notes": row.get("scope_notes", ""),
                    "family": cat.get("family", ""),
                    "family_name": cat.get("family_name", ""),
                    "description": cat.get("description", ""),
                    "verification_test": cat.get("verification_test", ""),
                    "implementation_hints": cat.get("implementation_hints", ""),
                }
            )

    payload = {
        "phase": "conform",
        "project_root": str(project.resolve()),
        "instructions": _INSTRUCTIONS,
        "system_profile": triage_audit.get("system_profile", {}),
        "in_scope": in_scope,
        "response_schema": RESPONSE_SCHEMA,
    }
    req_path = run.request("conform")
    req_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return req_path


def _render_md(artifact: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Phase 4 — Conformance",
        "",
        f"- **Rejected citations (hallucinations)**: {artifact.get('hallucination_count', 0)}",
        "",
        "## Verdict Summary",
        "",
    ]
    by_verdict = artifact.get("by_verdict", {})
    for v in sorted(by_verdict):
        lines.append(f"- **{v}**: {by_verdict[v]}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "| SID | Verdict | Citations | Reasoning |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in artifact.get("rows", []):
        v = str(row.get("verdict", ""))
        if row.get("demoted_due_to_hallucination"):
            v = f"{v} *(demoted)*"
        cits = ", ".join(row.get("citations", []))
        reasoning = str(row.get("reasoning", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.get('sid', '')} | {v} | {cits} | {reasoning} |")
    lines.append("")
    return "\n".join(lines)


def finalize(project: Path, run: RunDir) -> dict[str, Any]:
    require_phase_done(run, "load")
    triage_audit = require_phase_done(run, "triage-audit")

    resp_path = run.response("conform")
    if not resp_path.is_file():
        raise SystemExit(f"conform response not found at {resp_path}")
    try:
        resp = json.loads(resp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"conform response invalid JSON: {exc}") from exc

    expected_sids = {
        row["sid"]
        for row in triage_audit.get("applicability", [])
        if row.get("status") in ("applies", "partial_scope")
    }

    raw_rows = resp.get("rows")
    if not isinstance(raw_rows, list):
        raise SystemExit("conform response invalid:\n  - 'rows' must be a list")

    seen: set[str] = set()
    errors: list[str] = []
    cleaned_rows: list[dict[str, Any]] = []
    hallucination_count = 0

    for idx, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            errors.append(f"row {idx}: not an object")
            continue
        sid = row.get("sid")
        verdict = row.get("verdict")
        reasoning = str(row.get("reasoning") or "").strip()

        if sid not in expected_sids:
            errors.append(f"{sid}: out-of-scope or unknown sid")
            continue
        if sid in seen:
            errors.append(f"{sid}: duplicate row")
            continue
        seen.add(sid)

        if verdict not in ALLOWED_VERDICTS:
            errors.append(f"{sid}: bad verdict {verdict!r} (allowed: {sorted(ALLOWED_VERDICTS)})")
            continue
        if not reasoning:
            errors.append(f"{sid}: empty reasoning")
            continue

        verified, rejected = _verify(project, row.get("citations") or [])
        if rejected:
            hallucination_count += len(rejected)
            _append_hallucinations(project, "conform", sid, rejected)

        original_verdict = verdict
        demoted = False
        if verdict in NON_GAP and not verified:
            verdict = "inconclusive"
            demoted = True

        cleaned_rows.append(
            {
                "sid": sid,
                "verdict": verdict,
                "original_verdict": original_verdict,
                "demoted_due_to_hallucination": demoted,
                "reasoning": reasoning,
                "citations": verified,
                "rejected_citations": rejected,
                "gap_summary": str(row.get("gap_summary") or ""),
                "remediation": str(row.get("remediation") or ""),
            }
        )

    missing = sorted(expected_sids - seen)
    for sid in missing:
        errors.append(f"{sid}: missing from response")

    if errors:
        msg = "\n  - ".join(errors[:20])
        raise SystemExit(f"conform response invalid:\n  - {msg}")

    by_verdict: dict[str, int] = {}
    for r in cleaned_rows:
        v = r["verdict"]
        by_verdict[v] = by_verdict.get(v, 0) + 1

    artifact: dict[str, Any] = {
        "phase": "conform",
        "by_verdict": by_verdict,
        "hallucination_count": hallucination_count,
        "rows": cleaned_rows,
    }

    art_path = run.artifact("conform")
    art_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    (run.root / "04_conformance.md").write_text(_render_md(artifact), encoding="utf-8")
    return artifact
