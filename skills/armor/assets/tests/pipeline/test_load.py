"""Tests for armor.pipeline.load (3 tests)."""

from __future__ import annotations

import json
from pathlib import Path

from armor.pipeline import load as load_mod
from armor.pipeline.state import new_run
from ._helpers import make_project, write_mini_catalog


def test_load_normalises_rows_with_sids_and_families(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    art = load_mod.run(proj, catalog_arg=cat_path, run_dir=run)
    assert art["count"] == 3
    sids = [g["sid"] for g in art["guardrails"]]
    assert sids == ["GR-01.1", "GR-01.2", "GR-02.1"]
    families = [g["family"] for g in art["guardrails"]]
    assert families == ["GR-01", "GR-01", "GR-02"]
    assert art["guardrails"][0]["family_name"] == "Risk & impact assessment"
    assert art["guardrails"][2]["family_name"] == "Data governance"


def test_load_artifact_persisted_and_equals_return_value(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    art = load_mod.run(proj, catalog_arg=cat_path, run_dir=run)
    on_disk = json.loads(run.artifact("load").read_text(encoding="utf-8"))
    assert on_disk == art


def test_load_resolves_explicit_catalog_path(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    cat_path = write_mini_catalog(tmp_path)
    run = new_run(proj)
    art = load_mod.run(proj, catalog_arg=str(cat_path), run_dir=run)
    assert Path(art["catalog_path"]) == cat_path.resolve()
    assert art["catalog_sha"] == "deadbeef12345678"
