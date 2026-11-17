"""CLI dispatcher for the ARMOR v6 posture pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from . import __version__
from .pipeline import (
    PHASES,
    RunDir,
    conform as conform_mod,
    conform_audit as conform_audit_mod,
    current_run,
    load as load_mod,
    new_run,
    report as report_mod,
    schema as schema_mod,
    triage as triage_mod,
    triage_audit as triage_audit_mod,
)

_PHASE_KIND: dict[str, str] = {
    "load": "one_shot",
    "report": "one_shot",
    "triage": "two_step",
    "triage-audit": "two_step",
    "conform": "two_step",
    "conform-audit": "two_step",
}

_MODULES: dict[str, Any] = {
    "triage": triage_mod,
    "triage-audit": triage_audit_mod,
    "conform": conform_mod,
    "conform-audit": conform_audit_mod,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="armor", description="ARMOR v6 AI-guardrail posture pipeline")
    parser.add_argument("--version", action="version", version=f"armor {__version__}")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    p_pipe = subparsers.add_parser("pipeline", help="Run or inspect the 6-phase posture pipeline")
    p_pipe.add_argument("project", help="Path to the project under assessment")
    p_pipe.add_argument(
        "--phase",
        choices=list(PHASES),
        help="Run one phase",
    )
    p_pipe.add_argument(
        "--finalize",
        action="store_true",
        help="For two-step phases: consume queue/<phase>.response.json and write the artifact",
    )
    p_pipe.add_argument(
        "--status",
        action="store_true",
        help="Print phase status of the latest run",
    )
    p_pipe.add_argument(
        "--all",
        action="store_true",
        help="Advance every phase runnable without an LLM, then stop at the first request awaiting a response",
    )
    p_pipe.add_argument(
        "--catalog",
        metavar="PATH",
        help="Override the guardrail_matrix.json path (Phase 1)",
    )
    p_pipe.add_argument(
        "--audit-model",
        metavar="NAME",
        help="Reserved, unused (model hint for adversary phases)",
    )
    p_pipe.add_argument(
        "--validate-report",
        action="store_true",
        help="Validate posture_latest.json against the PostureReport schema; exit",
    )
    p_pipe.add_argument(
        "--write-schema",
        action="store_true",
        help="Regenerate armor/pipeline/schemas/posture_report.schema.json from the pydantic models; exit",
    )
    return parser


def _run_phase(
    project: Path,
    run: RunDir,
    phase: str,
    finalize: bool = False,
    catalog: str | None = None,
) -> dict[str, Any]:
    if phase == "load":
        art = load_mod.run(project, catalog_arg=catalog, run_dir=run)
        art_path = run.artifact("load")
        print(f"[load] wrote {art_path} ({art['count']} guardrails)")
        return art

    if phase == "report":
        art = report_mod.run(project, run_dir=run)
        art_path = run.artifact("report")
        latest_md = project / ".armor" / "reports" / "posture_latest.md"
        print(f"[report] wrote {art_path} and {latest_md}")
        return art

    mod = _MODULES[phase]
    if not finalize:
        req_path = mod.prepare(project, run)
        resp_path = run.response(phase)
        print(
            f"[{phase}] request written: {req_path}\n"
            f"LLM must write response to: {resp_path}\n"
            f"then run: python skills/armor/scripts/armor_run.py pipeline {project} --phase {phase} --finalize"
        )
        return {"status": "request-written", "request": str(req_path)}

    res = mod.finalize(project, run)
    if isinstance(res, dict) and res.get("status") == "another-round-required":
        resp_path = run.response(phase)
        print(
            f"[{phase}] auditor requested revisions; new request written. "
            f"Drop a fresh response at {resp_path} and re-run with --finalize."
        )
        return res

    art_path = run.artifact(phase)
    print(f"[{phase}] wrote {art_path}")
    return res


def _cmd_pipeline(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    if not project.exists():
        print(f"error: project path not found: {project}", file=sys.stderr)
        return 2

    if args.write_schema:
        out_path = schema_mod.write_schema()
        print(f"wrote schema: {out_path}")
        return 0

    if args.validate_report:
        report_path = project / ".armor" / "reports" / "posture_latest.json"
        if not report_path.is_file():
            print(f"error: report not found: {report_path}", file=sys.stderr)
            return 2
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            schema_mod.validate_artifact(data)
        except Exception as exc:
            print(f"error: invalid PostureReport at {report_path}: {exc}", file=sys.stderr)
            return 1
        print(f"ok: {report_path} conforms to PostureReport schema")
        return 0

    if args.status:
        run = current_run(project, create_if_missing=False)
        print(f"run: {run.root}")
        st = run.status()
        for ph in PHASES:
            print(f"  {ph:14s} {st[ph]}")
        return 0

    if args.phase == "load" and not args.finalize:
        run = new_run(project)
    else:
        run = current_run(project)

    if args.all:
        for ph in PHASES:
            if run.artifact(ph).exists():
                continue
            kind = _PHASE_KIND[ph]
            if kind == "one_shot":
                _run_phase(project, run, ph, finalize=False, catalog=args.catalog)
            else:
                _run_phase(project, run, ph, finalize=False, catalog=args.catalog)
                while True:
                    if run.response(ph).exists():
                        res = _run_phase(project, run, ph, finalize=True, catalog=args.catalog)
                        if isinstance(res, dict) and res.get("status") == "another-round-required":
                            continue
                        break
                    else:
                        print(f"[--all] stopped at {ph}: awaiting LLM response at {run.response(ph)}")
                        return 0
        return 0

    if not args.phase:
        print("error: specify --phase <name>, --status, or --all", file=sys.stderr)
        return 2

    _run_phase(project, run, args.phase, finalize=args.finalize, catalog=args.catalog)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "pipeline":
        return _cmd_pipeline(args)
    return 2
