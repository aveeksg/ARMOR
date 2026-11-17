"""Tests for armor.pipeline.conform (4 tests)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from armor.pipeline import (
    conform as conform_mod,
    load as load_mod,
    triage as triage_mod,
    triage_audit as triage_audit_mod,
)
from armor.pipeline.state import hallucination_log, new_run
from ._helpers import make_project, write_mini_catalog


def _setup_triage_audited_run(tmp_path: Path):
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
    return proj, run


def test_conform_prepare_includes_only_applicable_rows(tmp_path: Path) -> None:
    proj, run = _setup_triage_audited_run(tmp_path)
    req_path = conform_mod.prepare(proj, run)
    req = json.loads(req_path.read_text(encoding="utf-8"))
    in_scope_sids = [r["sid"] for r in req["in_scope"]]
    assert in_scope_sids == ["GR-01.1", "GR-01.2"]
    assert "GR-02.1" not in in_scope_sids


def test_conform_finalize_valid_citation_keeps_verdict(tmp_path: Path) -> None:
    proj, run = _setup_triage_audited_run(tmp_path)
    conform_mod.prepare(proj, run)
    resp = {
        "rows": [
            {
                "sid": "GR-01.1",
                "verdict": "implemented",
                "reasoning": "Risk tier check is implemented in src/main.py.",
                "citations": ["src/main.py:1-5"],
            },
            {
                "sid": "GR-01.2",
                "verdict": "gap",
                "reasoning": "No risk register found in the repository.",
                "gap_summary": "Missing risk register.",
                "remediation": "Add a risk register schema check in src/main.py.",
            },
        ]
    }
    run.response("conform").write_text(json.dumps(resp), encoding="utf-8")
    art = conform_mod.finalize(proj, run)
    by_sid = {r["sid"]: r for r in art["rows"]}
    assert by_sid["GR-01.1"]["verdict"] == "implemented"
    assert by_sid["GR-01.1"]["demoted_due_to_hallucination"] is False
    assert art["hallucination_count"] == 0


def test_conform_finalize_bogus_citations_demote_and_log(tmp_path: Path) -> None:
    proj, run = _setup_triage_audited_run(tmp_path)
    conform_mod.prepare(proj, run)
    resp = {
        "rows": [
            {
                "sid": "GR-01.1",
                "verdict": "implemented",
                "reasoning": "Claiming implementation in nonexistent file.",
                "citations": ["src/ghost.py:10"],
            },
            {
                "sid": "GR-01.2",
                "verdict": "partial",
                "reasoning": "Claiming implementation at out-of-bounds line.",
                "citations": ["src/main.py:999"],
                "remediation": "Extend src/main.py to validate risk entries.",
            },
        ]
    }
    run.response("conform").write_text(json.dumps(resp), encoding="utf-8")
    art = conform_mod.finalize(proj, run)
    for r in art["rows"]:
        assert r["verdict"] == "inconclusive"
        assert r["demoted_due_to_hallucination"] is True
    assert art["hallucination_count"] == 2
    log_lines = hallucination_log(proj).read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 2


def test_conform_finalize_rejects_extra_out_of_scope_sid(tmp_path: Path) -> None:
    proj, run = _setup_triage_audited_run(tmp_path)
    conform_mod.prepare(proj, run)
    resp = {
        "rows": [
            {
                "sid": "GR-01.1",
                "verdict": "implemented",
                "reasoning": "Implemented in main.",
                "citations": ["src/main.py:1"],
            },
            {
                "sid": "GR-01.2",
                "verdict": "gap",
                "reasoning": "Missing register.",
                "gap_summary": "Gap.",
                "remediation": "Add register in src/main.py.",
            },
            {
                "sid": "GR-02.1",
                "verdict": "n/a",
                "reasoning": "Was marked n_a in triage so out of scope.",
            },
        ]
    }
    run.response("conform").write_text(json.dumps(resp), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        conform_mod.finalize(proj, run)
    assert "out-of-scope" in str(exc.value)
