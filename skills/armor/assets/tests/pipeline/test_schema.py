"""Tests for armor.pipeline.schema (9 tests)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from armor.pipeline import (
    conform as conform_mod,
    conform_audit as conform_audit_mod,
    load as load_mod,
    report as report_mod,
    schema as schema_mod,
    triage as triage_mod,
    triage_audit as triage_audit_mod,
)
from armor.pipeline.state import new_run
from ._helpers import make_project, write_mini_catalog


def _produce_full_report(tmp_path: Path) -> tuple[Path, dict]:
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
                        "reasoning": "Implemented in src/main.py.",
                        "citations": ["src/main.py:1-5"],
                    },
                    {
                        "sid": "GR-01.2",
                        "verdict": "gap",
                        "reasoning": "Missing risk register.",
                        "gap_summary": "No register.",
                        "remediation": "Add register check in src/main.py.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    conform_mod.finalize(proj, run)

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

    art = report_mod.run(proj, run_dir=run)
    return proj, art


def test_report_artifact_validates_as_posture_report(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    model = schema_mod.validate_artifact(art)
    assert model.coverage.overall_pct == 50.0


def test_schema_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    bad = copy.deepcopy(art)
    bad["unexpected_key"] = 123
    with pytest.raises(ValidationError):
        schema_mod.validate_artifact(bad)


def test_schema_rejects_unknown_row_key(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    bad = copy.deepcopy(art)
    bad["rows"][0]["extra_field"] = "nope"
    with pytest.raises(ValidationError):
        schema_mod.validate_artifact(bad)


def test_schema_rejects_invalid_verdict(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    bad = copy.deepcopy(art)
    bad["rows"][0]["verdict"] = "bogus_verdict"
    with pytest.raises(ValidationError):
        schema_mod.validate_artifact(bad)


def test_schema_rejects_bad_generated_at_pattern(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    bad = copy.deepcopy(art)
    bad["generated_at"] = "2026-05-14 12:00:00"
    with pytest.raises(ValidationError):
        schema_mod.validate_artifact(bad)


def test_schema_rejects_out_of_range_pct(tmp_path: Path) -> None:
    _, art = _produce_full_report(tmp_path)
    bad = copy.deepcopy(art)
    bad["coverage"]["overall_pct"] = 105.0
    with pytest.raises(ValidationError):
        schema_mod.validate_artifact(bad)


def test_persisted_artifact_validates_no_drift(tmp_path: Path) -> None:
    proj, _ = _produce_full_report(tmp_path)
    latest_path = proj / ".armor" / "reports" / "posture_latest.json"
    on_disk = json.loads(latest_path.read_text(encoding="utf-8"))
    model = schema_mod.validate_artifact(on_disk)
    assert model.phase == "report"


def test_schema_file_persisted_and_loadable_with_title(tmp_path: Path) -> None:
    out = tmp_path / "schema.json"
    schema_mod.write_schema(out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded.get("title") == "PostureReport"
    assert schema_mod.load_schema().get("title") == "PostureReport"


def test_packaged_schema_byte_equals_model_json_schema() -> None:
    assert schema_mod.SCHEMA_PATH.is_file()
    expected = (
        json.dumps(schema_mod.PostureReport.model_json_schema(), indent=2, sort_keys=True) + "\n"
    )
    actual = schema_mod.SCHEMA_PATH.read_text(encoding="utf-8")
    assert actual == expected
