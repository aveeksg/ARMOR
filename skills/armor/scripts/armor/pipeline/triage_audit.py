"""Phase 3: Adversarial red-team audit of triage applicability (LLM loop <= 3 rounds)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import adversary
from .state import MAX_AUDIT_REVISIONS, RunDir, require_phase_done
from .triage import ALLOWED_STATUS

PHASE = "triage-audit"
ROWS_KEY = "applicability"


def _trail_path(run: RunDir) -> Path:
    return run.root / ".triage_audit_trail.json"


def _load_trail(run: RunDir) -> list[dict[str, Any]]:
    p = _trail_path(run)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save_trail(run: RunDir, trail: list[dict[str, Any]]) -> None:
    _trail_path(run).write_text(json.dumps(trail, indent=2) + "\n", encoding="utf-8")


def prepare(project: Path, run: RunDir) -> Path:
    req_path = run.request(PHASE)
    if req_path.is_file():
        return req_path
    triage_art = require_phase_done(run, "triage")
    payload = adversary.build_request(
        audit_kind=PHASE,
        target_artifact=triage_art,
        rows_key=ROWS_KEY,
        revision=1,
        extra_context={
            "system_profile": triage_art.get("system_profile", {}),
            "allowed_statuses": sorted(ALLOWED_STATUS),
        },
    )
    return adversary.write_request(run, PHASE, payload)


def _render_md(artifact: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Phase 3 — Triage Audit",
        "",
        f"- **Final revision**: {artifact.get('final_revision')}/{MAX_AUDIT_REVISIONS}",
        f"- **Converged**: {artifact.get('converged')}",
        "",
        "## Status Counts",
        "",
    ]
    by_status = artifact.get("by_status", {})
    for st in ("applies", "partial_scope", "n_a"):
        lines.append(f"- **{st}**: {by_status.get(st, 0)}")

    open_q = artifact.get("open_questions", [])
    lines.extend(["", f"## Open Questions ({len(open_q)})", ""])
    if open_q:
        for q in open_q:
            lines.append(f"- **{q.get('sid', '')}**: {q.get('critique', '')}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Audit Trail", ""])
    for rec in artifact.get("audit_trail", []):
        rev = rec.get("revision")
        vc = rec.get("verdict_counts", {})
        revs = len(rec.get("revisions_applied", []))
        lines.append(f"- **Round {rev}**: verdicts={vc}, revisions_applied={revs}")
    lines.append("")
    return "\n".join(lines)


def finalize(project: Path, run: RunDir) -> dict[str, Any]:
    req_path = run.request(PHASE)
    if not req_path.is_file():
        raise SystemExit(f"{PHASE} request not found at {req_path}")
    req = json.loads(req_path.read_text(encoding="utf-8"))
    resp = adversary.read_response(run, PHASE)

    revision = int(req.get("revision", 1))
    target = req["target_artifact"]
    new_target, summary = adversary.apply_deltas(target, ROWS_KEY, resp)

    audit_record: dict[str, Any] = {
        "revision": revision,
        "verdict_counts": summary["verdict_counts"],
        "revisions_applied": summary["revisions_applied"],
        "open_questions": summary["open_questions"],
        "unknown_sids": summary["unknown_sids"],
        "overall_note": summary["overall_note"],
    }
    trail = _load_trail(run)
    trail.append(audit_record)

    if adversary.converged(summary, revision):
        rows = new_target.get(ROWS_KEY, [])
        by_status = {
            "applies": sum(1 for r in rows if r.get("status") == "applies"),
            "n_a": sum(1 for r in rows if r.get("status") == "n_a"),
            "partial_scope": sum(1 for r in rows if r.get("status") == "partial_scope"),
        }
        all_open_questions: list[dict[str, Any]] = []
        for r_rec in trail:
            all_open_questions.extend(r_rec.get("open_questions", []))

        is_converged = len(summary["revisions_applied"]) == 0
        artifact: dict[str, Any] = {
            "phase": PHASE,
            "final_revision": revision,
            "converged": is_converged,
            "by_status": by_status,
            "system_profile": new_target.get("system_profile", {}),
            "applicability": rows,
            "audit_trail": trail,
            "open_questions": all_open_questions,
        }
        art_path = run.artifact(PHASE)
        art_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        (run.root / "03_triage_audit.md").write_text(_render_md(artifact), encoding="utf-8")

        req_path.unlink(missing_ok=True)
        run.response(PHASE).unlink(missing_ok=True)
        _trail_path(run).unlink(missing_ok=True)
        return artifact

    next_rev = revision + 1
    _save_trail(run, trail)
    next_payload = adversary.build_request(
        audit_kind=PHASE,
        target_artifact=new_target,
        rows_key=ROWS_KEY,
        revision=next_rev,
        extra_context={
            "system_profile": new_target.get("system_profile", {}),
            "allowed_statuses": sorted(ALLOWED_STATUS),
            "previous_revisions": trail,
        },
    )
    adversary.write_request(run, PHASE, next_payload)
    run.response(PHASE).unlink(missing_ok=True)
    return {"status": "another-round-required", "next_revision": next_rev}
