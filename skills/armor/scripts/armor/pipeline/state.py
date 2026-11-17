"""Run directory management, phase state, project fingerprinting, and citation cross-verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

PHASES = ("load", "triage", "triage-audit", "conform", "conform-audit", "report")

PHASE_ARTIFACT = {
    "load": "01_guardrails.json",
    "triage": "02_triage.json",
    "triage-audit": "03_triage_audit.json",
    "conform": "04_conformance.json",
    "conform-audit": "05_conformance_audit.json",
    "report": "06_report.json",
}

MAX_AUDIT_REVISIONS = 3

_CITATION_RE = re.compile(r"^([^:]+?)(?::(\d+))?(?:-(\d+))?$")

_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs", ".kt", ".cs", ".rb"}
_SKIP_DIRS = {".git", ".armor", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".pytest_cache"}


@dataclass
class RunDir:
    project: Path
    root: Path

    @property
    def queue(self) -> Path:
        q = self.root / "queue"
        q.mkdir(parents=True, exist_ok=True)
        return q

    def artifact(self, phase: str) -> Path:
        return self.root / PHASE_ARTIFACT[phase]

    def request(self, phase: str) -> Path:
        return self.queue / f"{phase}.request.json"

    def response(self, phase: str) -> Path:
        return self.queue / f"{phase}.response.json"

    def status(self) -> dict[str, str]:
        result: dict[str, str] = {}
        q = self.root / "queue"
        for phase in PHASES:
            art = self.root / PHASE_ARTIFACT[phase]
            resp = q / f"{phase}.response.json"
            req = q / f"{phase}.request.json"
            if art.exists():
                result[phase] = "done"
            elif resp.exists():
                result[phase] = "response-ready (needs --finalize)"
            elif req.exists():
                result[phase] = "awaiting-llm"
            else:
                result[phase] = "pending"
        return result


def _armor_dir(project: Path) -> Path:
    d = project.resolve() / ".armor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _runs_dir(project: Path) -> Path:
    d = _armor_dir(project) / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_run(project: Path) -> RunDir:
    project_resolved = project.resolve()
    runs = _runs_dir(project_resolved)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    root = runs / ts
    suffix = 1
    while root.exists():
        root = runs / f"{ts}_{suffix}"
        suffix += 1
    root.mkdir(parents=True, exist_ok=True)
    return RunDir(project=project_resolved, root=root)


def current_run(project: Path, create_if_missing: bool = True) -> RunDir:
    project_resolved = project.resolve()
    runs = _runs_dir(project_resolved)
    entries = sorted([p for p in runs.iterdir() if p.is_dir()], key=lambda p: p.name)
    if entries:
        return RunDir(project=project_resolved, root=entries[-1])
    if create_if_missing:
        return new_run(project_resolved)
    raise SystemExit(f"no run directory under {runs} \u2014 start with --phase load")


def require_phase_done(run: RunDir, phase: str) -> dict[str, Any]:
    art = run.artifact(phase)
    if not art.exists():
        raise SystemExit(
            f"phase '{phase}' has not completed in {run.root}; run: "
            f"python skills/armor/scripts/armor_run.py pipeline {run.project} --phase {phase}"
        )
    return json.loads(art.read_text(encoding="utf-8"))


def project_fingerprint(project: Path, limit: int = 200) -> str:
    project_resolved = project.resolve()
    rows: list[str] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(project_resolved):
        dirnames[:] = sorted([d for d in dirnames if d not in _SKIP_DIRS])
        for fname in sorted(filenames):
            if count >= limit:
                break
            p = Path(dirpath) / fname
            if p.suffix in _SOURCE_EXTS:
                try:
                    st = p.stat()
                    rel = p.relative_to(project_resolved).as_posix()
                    rows.append(f"{rel}|{st.st_mtime_ns}")
                    count += 1
                except OSError:
                    continue
        if count >= limit:
            break
    rows.sort()
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()[:16]


def verify_citation(project: Path, citation: str) -> tuple[bool, str]:
    if not isinstance(citation, str):
        return (False, "unparseable citation")
    s = citation.strip()
    if not s:
        return (False, "unparseable citation")
    m = _CITATION_RE.match(s)
    if not m:
        return (False, "unparseable citation")
    rel, start_s, end_s = m.group(1), m.group(2), m.group(3)
    if end_s is not None and start_s is None:
        return (False, "unparseable citation")

    project_resolved = project.resolve()
    try:
        p = (project_resolved / rel).resolve()
        p.relative_to(project_resolved)
    except (ValueError, OSError):
        return (False, "citation escapes project_root")

    if not p.is_file():
        return (False, "file not found")

    if start_s is None:
        return (True, "ok")

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        total = len(text.splitlines())
    except OSError:
        return (False, "unreadable")

    lo = int(start_s)
    hi = int(end_s) if end_s is not None else lo
    if lo < 1 or hi < lo or hi > total:
        return (False, f"line out of bounds (file has {total} lines)")

    return (True, "ok")


def hallucination_log(project: Path) -> Path:
    return _armor_dir(project) / "hallucination_log.jsonl"
