"""Tests for armor.pipeline.triage (5 tests)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from armor.pipeline import load as load_mod, triage as triage_mod
from armor.pipeline.state import new_run
from ._helpers import make_project, write_mini_catalog


def _setup_loaded_run(tmp_path: Path):
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    load_mod.run(proj, catalog_arg=cat_path, run_dir=run)
    return proj, run


def test_triage_prepare_writes_request_with_all_sids_and_inputs(tmp_path: Path) -> None:
    proj, run = _setup_loaded_run(tmp_path)
    req_path = triage_mod.prepare(proj, run)
    req = json.loads(req_path.read_text(encoding="utf-8"))
    assert req["phase"] == "triage"
    assert [g["sid"] for g in req["guardrails"]] == ["GR-01.1", "GR-01.2", "GR-02.1"]
    assert "README.md" in req["system_profile_inputs"]["manifests_and_docs"]
    assert "response_schema" in req


def test_triage_finalize_happy_path_writes_json_and_md(tmp_path: Path) -> None:
    proj, run = _setup_loaded_run(tmp_path)
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
    art = triage_mod.finalize(proj, run)
    assert art["by_status"] == {"applies": 2, "partial_scope": 0, "n_a": 1}
    assert run.artifact("triage").is_file()
    assert (run.root / "02_triage.md").is_file()


def test_triage_finalize_rejects_unknown_sid(tmp_path: Path) -> None:
    proj, run = _setup_loaded_run(tmp_path)
    triage_mod.prepare(proj, run)
    resp = {
        "system_profile": {"one_liner": "x", "languages": ["py"], "deployment_model": "cli", "user_population": "dev"},
        "applicability": [
            {"sid": "GR-01.1", "status": "applies", "reason": "Valid reason string."},
            {"sid": "GR-01.2", "status": "applies", "reason": "Valid reason string."},
            {"sid": "GR-02.1", "status": "n_a", "reason": "Valid reason string."},
            {"sid": "GR-99.9", "status": "applies", "reason": "Unknown sid injected."},
        ],
    }
    run.response("triage").write_text(json.dumps(resp), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        triage_mod.finalize(proj, run)
    assert "unknown sid" in str(exc.value)


def test_triage_finalize_rejects_missing_sid(tmp_path: Path) -> None:
    proj, run = _setup_loaded_run(tmp_path)
    triage_mod.prepare(proj, run)
    resp = {
        "system_profile": {"one_liner": "x", "languages": ["py"], "deployment_model": "cli", "user_population": "dev"},
        "applicability": [
            {"sid": "GR-01.1", "status": "applies", "reason": "Valid reason string."},
            {"sid": "GR-01.2", "status": "applies", "reason": "Valid reason string."},
        ],
    }
    run.response("triage").write_text(json.dumps(resp), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        triage_mod.finalize(proj, run)
    assert "missing from response" in str(exc.value)


def test_triage_finalize_rejects_bad_status(tmp_path: Path) -> None:
    proj, run = _setup_loaded_run(tmp_path)
    triage_mod.prepare(proj, run)
    resp = {
        "system_profile": {"one_liner": "x", "languages": ["py"], "deployment_model": "cli", "user_population": "dev"},
        "applicability": [
            {"sid": "GR-01.1", "status": "invalid_status", "reason": "Valid reason string."},
            {"sid": "GR-01.2", "status": "applies", "reason": "Valid reason string."},
            {"sid": "GR-02.1", "status": "n_a", "reason": "Valid reason string."},
        ],
    }
    run.response("triage").write_text(json.dumps(resp), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        triage_mod.finalize(proj, run)
    assert "bad status" in str(exc.value)
