"""Downloader for OWASP Top 10 for LLM Applications 2025 PDF."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import requests

from ai_standards_versioning import check_drift, commit_version

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STANDARDS_ROOT = Path(
    os.environ.get("ARMOR_STANDARDS_ROOT", str(SCRIPT_DIR.parents[1] / "references" / "ai_standards"))
)

OWASP_PDF_URL = (
    "https://genai.owasp.org/wp-content/uploads/2024/11/OWASP-Top-10-for-LLMs-v2025.pdf"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download OWASP LLM Top 10 2025 PDF")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_STANDARDS_ROOT / "owasp-llm-top10"),
        help="Target source directory",
    )
    parser.add_argument("--check-only", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    staged = Path(tempfile.mkdtemp(prefix="owasp_llm_stage_"))
    try:
        resp = requests.get(
            OWASP_PDF_URL,
            headers={"User-Agent": "ARMOR-Catalog-Sync/6.0.0"},
            timeout=90,
        )
        resp.raise_for_status()
        body = resp.content
        fname = "OWASP-Top-10-for-LLMs-v2025.pdf"
        (staged / fname).write_bytes(body)

        manifest = {
            "source": "owasp-llm-top10",
            "url": OWASP_PDF_URL,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if args.check_only:
            drift = check_drift(source_root, staged)
            return 1 if drift else 0

        version_dir, status = commit_version(source_root, staged, "owasp-llm-top10")
        print(f"[owasp-llm-top10] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
