"""Phase 5: Adversarial red-team audit of conformance rows + citation re-verification (LLM loop <= 3 rounds)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import adversary
from .conform import ALLOWED_VERDICTS, NON_GAP, _append_hallucinations, _verify
from .state import MAX_AUDIT_REVISIONS, RunDir, require_phase_done

PHASE = "conform-audit"
ROWS_KEY = "rows"

_AUDIT_DIRECTIONS = (
    "(a) DOWNGRADE rows whose evidence is weak or fabricated; "
    "(b) UPGRADE rows you can defend with additional citations."
)


def _trail_path(run: RunDir) -> Path:
    return run.root / ".conform_audit_trail.json"


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


def _extra_context(previous_revisions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "allowed_verdicts": sorted(ALLOWED_VERDICTS),
        "non_gap_verdicts_require_citation": sorted(NON_GAP),
        "audit_directions": _AUDIT_DIRECTIONS,
    }
    if previous_revisions is not None:
        ctx["previous_revisions"] = previous_revisions
    return ctx


def prepare(project: Path, run: RunDir) -> Path:
    req_path = run.request(PHASE)
    if req_path.is_file():
        return req_path
    conform_art = require_phase_done(run, "conform")
    payload = adversary.build_request(
        audit_kind=PHASE,
        target_artifact=conform_art,
        rows_key=ROWS_KEY,
        revision=1,
        extra_context=_extra_context(),
    )
    return adversary.write_request(run, PHASE, payload)


def _render_md(artifact: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Phase 5 — Conformance Audit",
        "",
        f"- **Final revision**: {artifact.get('final_revision')}/{MAX_AUDIT_REVISIONS}",
        f"- **Converged**: {artifact.get('converged')}",
        "",
        "## Verdict Counts",
        "",
    ]
    by_verdict = artifact.get("by_verdict", {})
    for v in sorted(by_verdict):
        lines.append(f"- **{v}**: {by_verdict[v]}")

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
        hal = rec.get("post_audit_hallucinations", 0)
        lines.append(
            f"- **Round {rev}**: verdicts={vc}, revisions_applied={revs}, post_audit_hallucinations={hal}"
        )
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

    post_audit_hallucinations = 0
    reverified_rows: list[dict[str, Any]] = []
    for row in new_target.get(ROWS_KEY, []):
        r = dict(row)
        sid = str(r.get("sid", ""))
        verdict = str(r.get("verdict", "inconclusive"))
        raw_cits = r.get("citations") or []

        if not raw_cits and verdict in NON_GAP:
            r["verdict"] = "inconclusive"
            r["demoted_due_to_hallucination"] = True
            r["citations"] = []
        else:
            verified, rejected = _verify(project, raw_cits)
            r["citations"] = verified
            existing_rej = list(r.get("rejected_citations") or [])
            if rejected:
                post_audit_hallucinations += len(rejected)
                _append_hallucinations(project, PHASE, sid, rejected)
                r["rejected_citations"] = existing_rej + rejected
            if verdict in NON_GAP and not verified:
                r["verdict"] = "inconclusive"
                r["demoted_due_to_hallucination"] = True

        reverified_rows.append(r)

    new_target = {**new_target, ROWS_KEY: reverified_rows}

    audit_record: dict[str, Any] = {
        "revision": revision,
        "verdict_counts": summary["verdict_counts"],
        "revisions_applied": summary["revisions_applied"],
        "open_questions": summary["open_questions"],
        "unknown_sids": summary["unknown_sids"],
        "overall_note": summary["overall_note"],
        "post_audit_hallucinations": post_audit_hallucinations,
    }
    trail = _load_trail(run)
    trail.append(audit_record)

    if adversary.converged(summary, revision):
        by_verdict: dict[str, int] = {}
        for r in reverified_rows:
            v = str(r.get("verdict", "inconclusive"))
            by_verdict[v] = by_verdict.get(v, 0) + 1

        all_open_questions: list[dict[str, Any]] = []
        for r_rec in trail:
            all_open_questions.extend(r_rec.get("open_questions", []))

        is_converged = len(summary["revisions_applied"]) == 0
        artifact: dict[str, Any] = {
            "phase": PHASE,
            "final_revision": revision,
            "converged": is_converged,
            "by_verdict": by_verdict,
            "rows": reverified_rows,
            "audit_trail": trail,
            "open_questions": all_open_questions,
        }
        art_path = run.artifact(PHASE)
        art_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        (run.root / "05_conformance_audit.md").write_text(_render_md(artifact), encoding="utf-8")

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
        extra_context=_extra_context(previous_revisions=trail),
    )
    adversary.write_request(run, PHASE, next_payload)
    run.response(PHASE).unlink(missing_ok=True)
    return {"status": "another-round-required", "next_revision": next_rev}
