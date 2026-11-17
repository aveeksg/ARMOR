"""Tests for armor.pipeline.triage_audit (3 tests)."""

from __future__ import annotations

import json
from pathlib import Path

from armor.pipeline import (
    load as load_mod,
    triage as triage_mod,
    triage_audit as triage_audit_mod,
)
from armor.pipeline.state import MAX_AUDIT_REVISIONS, new_run
from ._helpers import make_project, write_mini_catalog


def _setup_triaged_run(tmp_path: Path):
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    load_mod.run(proj, catalog_arg=cat_path, run_dir=run)
    triage_mod.prepare(proj, run)
    resp = {
        "system_profile": {
            "one_liner": "Sample service",
            "languages": ["python"],
            "deployment_model": "service",
            "user_population": "internal",
        },
        "applicability": [
            {"sid": "GR-01.1", "status": "applies", "reason": "Core risk tiering applies here."},
            {"sid": "GR-01.2", "status": "applies", "reason": "Continuous risk register applies."},
            {"sid": "GR-02.1", "status": "n_a", "reason": "No training or RAG corpus used."},
        ],
    }
    run.response("triage").write_text(json.dumps(resp), encoding="utf-8")
    triage_mod.finalize(proj, run)
    return proj, run


def test_triage_audit_converges_when_all_confirm(tmp_path: Path) -> None:
    proj, run = _setup_triaged_run(tmp_path)
    triage_audit_mod.prepare(proj, run)
    audit_resp = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
            {"sid": "GR-02.1", "verdict": "CONFIRM"},
        ]
    }
    run.response("triage-audit").write_text(json.dumps(audit_resp), encoding="utf-8")
    res = triage_audit_mod.finalize(proj, run)
    assert res["final_revision"] == 1
    assert res["converged"] is True
    assert len(res["audit_trail"]) == 1
    assert not run.request("triage-audit").exists()
    assert not run.response("triage-audit").exists()


def test_triage_audit_revise_triggers_second_round_then_converges(tmp_path: Path) -> None:
    proj, run = _setup_triaged_run(tmp_path)
    triage_audit_mod.prepare(proj, run)
    round1 = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {
                "sid": "GR-01.2",
                "verdict": "REVISE",
                "critique": "Only partially in scope for internal prototype.",
                "revised_row": {
                    "sid": "GR-01.2",
                    "status": "partial_scope",
                    "reason": "Only partially in scope for internal prototype.",
                },
            },
            {"sid": "GR-02.1", "verdict": "CONFIRM"},
        ]
    }
    run.response("triage-audit").write_text(json.dumps(round1), encoding="utf-8")
    res1 = triage_audit_mod.finalize(proj, run)
    assert res1 == {"status": "another-round-required", "next_revision": 2}

    round2 = {
        "verdicts": [
            {"sid": "GR-01.1", "verdict": "CONFIRM"},
            {"sid": "GR-01.2", "verdict": "CONFIRM"},
            {"sid": "GR-02.1", "verdict": "CONFIRM"},
        ]
    }
    run.response("triage-audit").write_text(json.dumps(round2), encoding="utf-8")
    res2 = triage_audit_mod.finalize(proj, run)
    assert res2["final_revision"] == 2
    assert res2["converged"] is True
    assert len(res2["audit_trail"]) == 2
    assert res2["by_status"] == {"applies": 1, "partial_scope": 1, "n_a": 1}


def test_triage_audit_revise_every_round_force_terminates_at_max(tmp_path: Path) -> None:
    proj, run = _setup_triaged_run(tmp_path)
    triage_audit_mod.prepare(proj, run)
    for r in range(1, MAX_AUDIT_REVISIONS + 1):
        resp = {
            "verdicts": [
                {
                    "sid": "GR-01.1",
                    "verdict": "REVISE",
                    "critique": f"Round {r} critique",
                    "revised_row": {
                        "sid": "GR-01.1",
                        "status": "partial_scope",
                        "reason": f"Updated in round {r}",
                    },
                },
                {"sid": "GR-01.2", "verdict": "CONFIRM"},
                {"sid": "GR-02.1", "verdict": "CONFIRM"},
            ]
        }
        run.response("triage-audit").write_text(json.dumps(resp), encoding="utf-8")
        res = triage_audit_mod.finalize(proj, run)
        if r < MAX_AUDIT_REVISIONS:
            assert res["status"] == "another-round-required"
        else:
            assert res["final_revision"] == MAX_AUDIT_REVISIONS
            assert res["converged"] is False
            assert len(res["audit_trail"]) == MAX_AUDIT_REVISIONS
