"""Umbrella orchestrator: run all 5 AI standard downloaders then generate_guardrail_catalog.py."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parents[1]
STANDARDS_ROOT = SKILL_ROOT / "references" / "ai_standards"

DOWNLOADERS: list[tuple[str, str]] = [
    ("download_aiid_slim.py", "ai-incident-database"),
    ("download_eu_ai_act_cellar.py", "eu-ai-act"),
    ("download_mitre_atlas.py", "mitre-atlas"),
    ("download_nist_ai_rmf.py", "nist-ai-rmf"),
    ("download_owasp_llm_top10.py", "owasp-llm-top10"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh AI standards sources and regenerate guardrail catalog")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report drift (rc 1=drift, 0=unchanged) without writing",
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Skip downloaders and run only generate_guardrail_catalog.py",
    )
    parser.add_argument(
        "--standards-root",
        default=os.environ.get("ARMOR_STANDARDS_ROOT", str(STANDARDS_ROOT)),
        help="Root directory for ai_standards",
    )
    args = parser.parse_args(argv)

    standards_root = Path(args.standards_root).resolve()
    env = dict(os.environ)
    env["ARMOR_STANDARDS_ROOT"] = str(standards_root)

    drift_detected = False

    if not args.skip_downloads:
        for script_name, subdir in DOWNLOADERS:
            script_path = SCRIPT_DIR / script_name
            source_root = standards_root / subdir
            cmd = [sys.executable, str(script_path), "--source-root", str(source_root)]
            if args.check_only:
                cmd.append("--check-only")
            res = subprocess.run(cmd, env=env)
            if args.check_only:
                if res.returncode == 1:
                    drift_detected = True
                elif res.returncode != 0:
                    return res.returncode
            else:
                if res.returncode != 0:
                    print(f"error: downloader {script_name} failed with exit code {res.returncode}", file=sys.stderr)
                    return res.returncode

    if args.check_only:
        return 1 if drift_detected else 0

    gen_script = SCRIPT_DIR / "generate_guardrail_catalog.py"
    gen_cmd = [sys.executable, str(gen_script), "--standards-root", str(standards_root)]
    res = subprocess.run(gen_cmd, env=env)
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
