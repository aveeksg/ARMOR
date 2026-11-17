"""Phase 6: Deterministic posture report rollup, coverage calculation, and schema validation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from .schema import validate_artifact
from .state import RunDir, _armor_dir, require_phase_done

VERDICT_WEIGHT: dict[str, float] = {
    "implemented": 1.0,
    "partial": 0.6,
    "weak": 0.3,
    "gap": 0.0,
    "inconclusive": 0.0,
}

_SUGGESTION_KIND_ORDER: dict[str, int] = {
    "gap": 0,
    "inconclusive": 1,
    "weak": 2,
    "partial": 3,
}


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    in_scope = [r for r in rows if r["verdict"] != "n/a"]
    max_pts = float(len(in_scope))
    earned = round(sum(VERDICT_WEIGHT.get(r["verdict"], 0.0) for r in in_scope), 4)
    overall_pct = round(100.0 * earned / max_pts, 1) if max_pts > 0 else 0.0

    by_verdict_in_scope: dict[str, int] = {}
    for r in in_scope:
        v = r["verdict"]
        by_verdict_in_scope[v] = by_verdict_in_scope.get(v, 0) + 1

    fam_groups: dict[str, list[dict[str, Any]]] = {}
    fam_names: dict[str, str] = {}
    for r in in_scope:
        fam = r["family"]
        fam_names[fam] = r.get("family_name", "")
        fam_groups.setdefault(fam, []).append(r)

    by_family: list[dict[str, Any]] = []
    for fam, frows in fam_groups.items():
        f_max = float(len(frows))
        f_earned = round(sum(VERDICT_WEIGHT.get(r["verdict"], 0.0) for r in frows), 4)
        f_pct = round(100.0 * f_earned / f_max, 1) if f_max > 0 else 0.0
        by_family.append(
            {
                "family": fam,
                "family_name": fam_names.get(fam, ""),
                "in_scope": len(frows),
                "earned": f_earned,
                "max": f_max,
                "score_pct": f_pct,
            }
        )

    by_family.sort(key=lambda item: (item["score_pct"], item["family"]))

    return {
        "overall_pct": overall_pct,
        "applicable_only_pct": overall_pct,
        "in_scope_count": len(in_scope),
        "max_possible_points": max_pts,
        "earned_points": earned,
        "by_verdict_in_scope": by_verdict_in_scope,
        "by_family": by_family,
    }


def _suggestions(rows: list[dict[str, Any]], coverage: dict[str, Any]) -> list[dict[str, Any]]:
    fam_score_map = {f["family"]: f["score_pct"] for f in coverage.get("by_family", [])}
    actionable: list[dict[str, Any]] = []

    for r in rows:
        verdict = r["verdict"]
        if verdict not in _SUGGESTION_KIND_ORDER:
            continue
        pts_unlocked = round(1.0 - VERDICT_WEIGHT[verdict], 2)
        rem = str(r.get("remediation") or "").strip()
        if rem:
            action = rem
        elif verdict == "inconclusive":
            action = (
                f"Re-assess {r['sid']} and attach valid relative/path.ext:line citations "
                "under project_root."
            )
        else:
            action = f"No remediation supplied for {r['sid']}; implement controls satisfying the guardrail."

        fam = r["family"]
        fam_pct = fam_score_map.get(fam, 0.0)
        actionable.append(
            {
                "sid": r["sid"],
                "family": fam,
                "family_name": r.get("family_name", ""),
                "current_verdict": verdict,
                "points_unlocked": pts_unlocked,
                "family_score_pct": fam_pct,
                "action": action,
                "gap_summary": str(r.get("gap_summary") or ""),
                "remediation": rem,
                "reasoning": str(r.get("reasoning") or ""),
            }
        )

    actionable.sort(
        key=lambda s: (
            -s["points_unlocked"],
            s["family_score_pct"],
            _SUGGESTION_KIND_ORDER[s["current_verdict"]],
            s["sid"],
        )
    )
    return actionable


def _render_md(artifact: dict[str, Any]) -> str:
    cov = artifact["coverage"]
    totals = artifact["totals"]
    lines: list[str] = [
        "# ARMOR v6 — AI Guardrail Posture Report",
        "",
        f"- **Generated at**: {artifact['generated_at']}",
        f"- **Project**: `{artifact['project']}`",
        f"- **Run dir**: `{artifact['run_dir']}`",
        "",
        "## Coverage",
        "",
        f"- **Overall score**: **{cov['overall_pct']}%** ({cov['earned_points']} / {cov['max_possible_points']} points across {cov['in_scope_count']} in-scope guardrails)",
        "- _Weighting_: `implemented=1.0`, `partial=0.6`, `weak=0.3`, `gap=0.0`, `inconclusive=0.0` (`n/a` excluded from denominator).",
        "",
        "### Coverage by Family (weakest first)",
        "",
        "| Family | Name | In-Scope | Earned | Max | Score % |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for fam in cov.get("by_family", []):
        lines.append(
            f"| {fam['family']} | {fam['family_name']} | {fam['in_scope']} | {fam['earned']} | {fam['max']} | {fam['score_pct']}% |"
        )

    lines.extend(
        [
            "",
            "## Ranked Remediation Suggestions",
            "",
            "| SID | Family | Verdict | Points Unlocked | Action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for s in artifact.get("suggestions", []):
        act = str(s["action"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {s['sid']} | {s['family']} | {s['current_verdict']} | +{s['points_unlocked']} | {act} |"
        )

    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- **Total guardrails**: {totals['guardrails']}",
            f"- **By applicability**: `{json.dumps(totals['by_applicability'], sort_keys=True)}`",
            f"- **By verdict**: `{json.dumps(totals['by_verdict'], sort_keys=True)}`",
            f"- **Gaps**: {totals['gaps']}",
            f"- **Weak or partial**: {totals['weak_or_partial']}",
            f"- **Inconclusive**: {totals['inconclusive']}",
            f"- **Open questions**: {totals['open_questions']}",
            "",
            "## System Profile",
            "",
            "```json",
            json.dumps(artifact.get("system_profile", {}), indent=2),
            "```",
            "",
            "## Findings by Category",
            "",
            "### Gaps",
            "",
        ]
    )
    rows = artifact.get("rows", [])
    gaps = [r for r in rows if r["verdict"] == "gap"]
    if gaps:
        for r in gaps:
            lines.append(f"- **{r['sid']}** ({r['family_name']}): {r.get('gap_summary') or r.get('reasoning')}")
    else:
        lines.append("_None._")

    lines.extend(["", "### Partial / Weak", ""])
    pw = [r for r in rows if r["verdict"] in ("partial", "weak")]
    if pw:
        for r in pw:
            lines.append(f"- **{r['sid']}** [{r['verdict']}]: {r.get('reasoning')}")
    else:
        lines.append("_None._")

    lines.extend(["", "### Inconclusive", ""])
    inc = [r for r in rows if r["verdict"] == "inconclusive"]
    if inc:
        for r in inc:
            marker = " *(demoted)*" if r.get("demoted_due_to_hallucination") else ""
            lines.append(f"- **{r['sid']}**{marker}: {r.get('reasoning')}")
    else:
        lines.append("_None._")

    lines.extend(["", "### Open Questions", ""])
    open_q = artifact.get("open_questions", [])
    if open_q:
        for q in open_q:
            lines.append(f"- **{q.get('sid', '')}**: {q.get('critique', '')}")
    else:
        lines.append("_None._")

    lines.extend(
        [
            "",
            "## All Guardrails",
            "",
            "| SID | Family | Applicability | Verdict | Citations |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for r in rows:
        v = r["verdict"]
        if r.get("demoted_due_to_hallucination"):
            v = f"{v} *(demoted)*"
        cits = ", ".join(r.get("citations", []))
        lines.append(f"| {r['sid']} | {r['family']} | {r['applicability']} | {v} | {cits} |")
    lines.append("")
    return "\n".join(lines)


def run(project: Path, run_dir: RunDir | None = None) -> dict[str, Any]:
    if run_dir is None:
        from .state import current_run
        run_dir = current_run(project)

    loaded = require_phase_done(run_dir, "load")
    triage_audit = require_phase_done(run_dir, "triage-audit")
    conform_audit = require_phase_done(run_dir, "conform-audit")

    triage_by_sid = {r["sid"]: r for r in triage_audit.get("applicability", [])}
    conform_by_sid = {r["sid"]: r for r in conform_audit.get("rows", [])}

    rows: list[dict[str, Any]] = []
    by_applicability: dict[str, int] = {}
    by_verdict: dict[str, int] = {}

    for cat in loaded.get("guardrails", []):
        sid = cat["sid"]
        t_row = triage_by_sid.get(sid, {})
        app_status = t_row.get("status", "unknown")
        if app_status not in ("applies", "partial_scope", "n_a", "unknown"):
            app_status = "unknown"
        app_reason = str(t_row.get("reason") or "")

        c_row = conform_by_sid.get(sid, {})
        if app_status == "n_a":
            verdict = "n/a"
            reasoning = app_reason
            citations: list[str] = []
            gap_summary = ""
            remediation = ""
            demoted = False
        else:
            verdict = str(c_row.get("verdict") or "inconclusive")
            if verdict not in ("implemented", "partial", "weak", "gap", "inconclusive", "n/a"):
                verdict = "inconclusive"
            reasoning = str(c_row.get("reasoning") or "")
            citations = list(c_row.get("citations") or [])
            gap_summary = str(c_row.get("gap_summary") or "")
            remediation = str(c_row.get("remediation") or "")
            demoted = bool(c_row.get("demoted_due_to_hallucination", False))

        by_applicability[app_status] = by_applicability.get(app_status, 0) + 1
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1

        rows.append(
            {
                "sid": sid,
                "family": cat.get("family", ""),
                "family_name": cat.get("family_name", ""),
                "description": cat.get("description", ""),
                "applicability": app_status,
                "applicability_reason": app_reason,
                "verdict": verdict,
                "reasoning": reasoning,
                "citations": citations,
                "gap_summary": gap_summary,
                "remediation": remediation,
                "demoted_due_to_hallucination": demoted,
            }
        )

    open_questions: list[dict[str, Any]] = list(triage_audit.get("open_questions", [])) + list(
        conform_audit.get("open_questions", [])
    )

    coverage = _coverage(rows)
    suggestions = _suggestions(rows, coverage)

    totals = {
        "guardrails": len(rows),
        "by_applicability": by_applicability,
        "by_verdict": by_verdict,
        "gaps": by_verdict.get("gap", 0),
        "weak_or_partial": by_verdict.get("weak", 0) + by_verdict.get("partial", 0),
        "inconclusive": by_verdict.get("inconclusive", 0),
        "open_questions": len(open_questions),
    }

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    artifact: dict[str, Any] = {
        "phase": "report",
        "generated_at": ts,
        "project": str(project.resolve()),
        "run_dir": str(run_dir.root.resolve()),
        "system_profile": triage_audit.get("system_profile", {}),
        "totals": totals,
        "coverage": coverage,
        "suggestions": suggestions,
        "open_questions": open_questions,
        "rows": rows,
    }

    # Validate against Pydantic PostureReport contract before writing to disk
    validate_artifact(artifact)

    art_json_text = json.dumps(artifact, indent=2) + "\n"
    md_text = _render_md(artifact)

    art_path = run_dir.artifact("report")
    art_path.write_text(art_json_text, encoding="utf-8")

    reports_dir = _armor_dir(project) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    iso_json = reports_dir / f"posture_{ts}.json"
    iso_md = reports_dir / f"posture_{ts}.md"
    latest_json = reports_dir / "posture_latest.json"
    latest_md = reports_dir / "posture_latest.md"

    iso_json.write_text(art_json_text, encoding="utf-8")
    iso_md.write_text(md_text, encoding="utf-8")
    shutil.copyfile(iso_json, latest_json)
    shutil.copyfile(iso_md, latest_md)

    return artifact
