"""Tests for armor.pipeline.state (10 tests)."""

from __future__ import annotations

import os
from pathlib import Path
import time

import pytest

from armor.pipeline.state import (
    PHASES,
     current_run,
    new_run,
    project_fingerprint,
    require_phase_done,
    verify_citation,
)
from ._helpers import make_project


def test_phases_tuple_is_canonical() -> None:
    assert PHASES == ("load", "triage", "triage-audit", "conform", "conform-audit", "report")


def test_new_run_and_current_run_round_trip(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    r1 = new_run(proj)
    r2 = current_run(proj, create_if_missing=False)
    assert r1.root == r2.root
    assert r1.project == proj.resolve()


def test_fresh_run_reports_all_pending(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    run = new_run(proj)
    st = run.status()
    assert set(st.keys()) == set(PHASES)
    assert all(v == "pending" for v in st.values())


def test_require_phase_done_raises_before_load(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    run = new_run(proj)
    with pytest.raises(SystemExit) as exc:
        require_phase_done(run, "load")
    assert "--phase load" in str(exc.value)


def test_verify_citation_ok_file_and_single_line(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    ok_file, reason_file = verify_citation(proj, "src/main.py")
    assert ok_file is True and reason_file == "ok"
    ok_line, reason_line = verify_citation(proj, "src/main.py:10")
    assert ok_line is True and reason_line == "ok"


def test_verify_citation_range_ok(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    ok, reason = verify_citation(proj, "src/main.py:1-20")
    assert ok is True
    assert reason == "ok"


def test_verify_citation_out_of_bounds(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    ok, reason = verify_citation(proj, "src/main.py:25")
    assert ok is False
    assert "line out of bounds (file has 20 lines)" in reason


def test_verify_citation_missing_file(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    ok, reason = verify_citation(proj, "src/does_not_exist.py:1")
    assert ok is False
    assert reason == "file not found"


def test_verify_citation_traversal_blocked(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    outside = tmp_path / "secret.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    ok, reason = verify_citation(proj, "../secret.py:1")
    assert ok is False
    assert reason == "citation escapes project_root"


def test_project_fingerprint_changes_on_edit(tmp_path: Path) -> None:
    proj = make_project(tmp_path)
    fp1 = project_fingerprint(proj)
    target = proj / "src" / "main.py"
    target.write_text(target.read_text(encoding="utf-8") + "line_21 = 21\n", encoding="utf-8")
    st = target.stat()
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    fp2 = project_fingerprint(proj)
    assert fp1 != fp2
