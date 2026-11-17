"""Tests for armor.pipeline.conform_audit and armor.pipeline.report (6 tests)."""

from __future__ import annotations

import json
from pathlib import Path

from armor.pipeline import (
    conform as conform_mod,
    conform_audit as conform_audit_mod,
    load as load_mod,
    report as report_mod,
    triage as triage_mod,
    triage_audit as triage_audit_mod,
)
from armor.pipeline.state import new_run
from ._helpers import make_project, write_mini_catalog


def _setup_conformed_run(tmp_path: Path):
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    load_mod.run(proj, catalog_arg=cat_path, run_dir=run)

    triage_mod.prepare(proj, run)
    run.response("triage").write_text(
        json.dumps(
            {
                "system_profile": {
                    "one_liner": "Sample service",
                    "languages": ["python"],
                    "deployment_model": "service",
                    "user_population": "internal",
                },
                "applicability": [
                    {"sid": "GR-01.1", "status": "applies", "reason": "Core risk tiering applies."},
                    {"sid": "GR-01.2", "status": "applies", "reason": "Risk register applies."},
                    {"sid": "GR-02.1", "status": "n_a", "reason": "No training or RAG corpus."},
                ],
            }
        ),
        encoding="utf-8",
    )
    triage_mod.finalize(proj, run)

    triage_audit_mod.prepare(proj, run)
    run.response("triage-audit").write_text(
        json.dumps(
            {
                "verdicts": [
                    {"sid": "GR-01.1", "verdict": "CONFIRM"},
                    {"sid": "GR-01.2", "verdict": "CONFIRM"},
                    {"sid": "GR-02.1", "verdict": "CONFIRM"},
                ]
            }
        ),
        encoding="utf-8",
    )
    triage_audit_mod.finalize(proj, run)

    conform_mod.prepare(proj, run)
    run.response("conform").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "sid": "GR-01.1",
                        "verdict": "implemented",
                        "reasoning": "Risk tier check in src/main.py.",
                        "citations": ["src/main.py:1-5"],
                    },
                    {
                        "sid": "GR-01.2",
                        "verdict": "gap",
                        "reasoning": "No risk register found.",
                        "gap_summary": "Missing risk register.",
                        "remediation": "Add risk register check in src/main.py.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    conform_mod.finalize(proj, run)
    return proj, run


def test_conform_audit_revise_downgrade_implemented_to_weak(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    r1 = {
        "verdicts": [
            {
                "sid": "GR-01.1",
                "verdict": "REVISE",
                "critique": "Only a stub check exists; downgrade to weak.",
                "revised_row": {
                    "sid": "GR-01.1",
                    "verdict": "weak",
                    "reasoning": "Only a stub check exists in src/main.py.",
                    "citations": ["src/main.py:1-3"],
                    "remediation": "Enforce full risk tier validation in src/main.py.",
                },
            },
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r1), encoding="utf-8")
    res1 = conform_audit_mod.finalize(proj, run)
    assert res1["status"] == "another-round-required"

    r2 = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r2), encoding="utf-8")
    art = conform_audit_mod.finalize(proj, run)
    by_sid = {r["sid"]: r for r in art["rows"]}
    assert by_sid["GR-01.1"]["verdict"] == "weak"


def test_conform_audit_revise_with_bad_citation_demotes_to_inconclusive(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    r1 = {
        "verdicts": [
            {
                "sid": "GR-01.1",
                "verdict": "REVISE",
                "critique": "Re-citing bogus file.",
                "revised_row": {
                    "sid": "GR-01.1",
                    "verdict": "implemented",
                    "reasoning": "Fabricated citation during audit.",
                    "citations": ["src/nonexistent.py:1"],
                },
            },
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r1), encoding="utf-8")
    conform_audit_mod.finalize(proj, run)

    r2 = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r2), encoding="utf-8")
    art = conform_audit_mod.finalize(proj, run)
    by_sid = {r["sid"]: r for r in art["rows"]}
    assert by_sid["GR-01.1"]["verdict"] == "inconclusive"
    assert by_sid["GR-01.1"]["demoted_due_to_hallucination"] is True
    assert art["audit_trail"][0]["post_audit_hallucinations"] == 1


def test_report_joins_everything_and_writes_latest_pointers(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    run.response("conform-audit").write_text(
        json.dumps(
            {
                "verdicts": [
                    {"sid": "GR-01.1", "verdict": "CONFIRM"},
                    {"sid": "GR-01.2", "verdict": "CONFIRM"},
                ]
            }
        ),
        encoding="utf-8",
    )
    conform_audit_mod.finalize(proj, run)

    rep = report_mod.run(proj, run_dir=run)
    assert rep["totals"]["guardrails"] == 3
    assert rep["totals"]["by_verdict"] == {"implemented": 1, "gap": 1, "n/a": 1}
    by_sid = {r["sid"]: r for r in rep["rows"]}
    assert by_sid["GR-02.1"]["verdict"] == "n/a"
    assert (proj / ".armor" / "reports" / "posture_latest.json").is_file()
    assert (proj / ".armor" / "reports" / "posture_latest.md").is_file()


def test_report_coverage_metrics_50_percent_and_na_family_absent(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    run.response("conform-audit").write_text(
        json.dumps(
            {
                "verdicts": [
                    {"sid": "GR-01.1", "verdict": "CONFIRM"},
                    {"sid": "GR-01.2", "verdict": "CONFIRM"},
                ]
            }
        ),
        encoding="utf-8",
    )
    conform_audit_mod.finalize(proj, run)

    rep = report_mod.run(proj, run_dir=run)
    cov = rep["coverage"]
    assert cov["in_scope_count"] == 2
    assert cov["earned_points"] == 1.0
    assert cov["max_possible_points"] == 2.0
    assert cov["overall_pct"] == 50.0
    assert cov["applicable_only_pct"] == 50.0
    families_in_cov = [f["family"] for f in cov["by_family"]]
    assert families_in_cov == ["GR-01"]
    assert "GR-02" not in families_in_cov


def test_report_suggestions_ranked_by_points_unlocked_and_mixed_coverage(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    # Downgrade GR-01.1 to weak (0.3) and keep GR-01.2 as gap (0.0) -> earned 0.3 / 2.0 = 15.0%
    r1 = {
        "verdicts": [
            {
                "sid": "GR-01.1",
                "verdict": "REVISE",
                "critique": "Downgrade to weak",
                "revised_row": {
                    "sid": "GR-01.1",
                    "verdict": "weak",
                    "reasoning": "Stub check in src/main.py.",
                    "citations": ["src/main.py:1"],
                    "remediation": "Harden risk tier validation in src/main.py.",
                },
            },
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r1), encoding="utf-8")
    conform_audit_mod.finalize(proj, run)
    r2 = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
        ]
    }
    run.response("conform-audit").write_text(json.dumps(r2), encoding="utf-8")
    conform_audit_mod.finalize(proj, run)

    rep = report_mod.run(proj, run_dir=run)
    assert rep["coverage"]["overall_pct"] == 15.0
    suggs = rep["suggestions"]
    assert len(suggs) == 2
    assert suggs[0]["sid"] == "GR-01.2"
    assert suggs[0]["points_unlocked"] == 1.0
    assert suggs[1]["sid"] == "GR-01.1"
    assert suggs[1]["points_unlocked"] == 0.7


def test_report_collects_open_questions_from_both_audits(tmp_path: Path) -> None:
    proj, run = _setup_conformed_run(tmp_path)
    conform_audit_mod.prepare(proj, run)
    run.response("conform-audit").write_text(
        json.dumps(
            {
                "verdicts": [
                    {"sid": "GR-01.1", "verdict": "INVESTIGATE", "critique": "Verify runtime config binding."},
                    {"sid": "GR-01.2", "verdict": "CONFIRM"},
                ]
            }
        ),
        encoding="utf-8",
    )
    conform_audit_mod.finalize(proj, run)
    rep = report_mod.run(proj, run_dir=run)
    assert rep["totals"]["open_questions"] == 1
    assert rep["open_questions"][0]["sid"] == "GR-01.1"
