"""Downloader for NIST AI RMF 1.0 (NIST.AI.100-1) and Generative AI Profile (NIST.AI.600-1) PDFs."""

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

NIST_DOCS = {
    "NIST.AI.100-1.pdf": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
    "NIST.AI.600-1.pdf": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download NIST AI RMF PDFs")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_STANDARDS_ROOT / "nist-ai-rmf"),
        help="Target source directory",
    )
    parser.add_argument("--check-only", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    staged = Path(tempfile.mkdtemp(prefix="nist_ai_rmf_stage_"))
    try:
        files_meta: dict[str, dict[str, str]] = {}
        for fname, url in NIST_DOCS.items():
            resp = requests.get(
                url,
                headers={"User-Agent": "ARMOR-Catalog-Sync/6.0.0"},
                timeout=90,
            )
            resp.raise_for_status()
            body = resp.content
            (staged / fname).write_bytes(body)
            files_meta[fname] = {
                "url": url,
                "last_modified": resp.headers.get("Last-Modified", ""),
                "sha256": hashlib.sha256(body).hexdigest(),
            }

        manifest = {
            "source": "nist-ai-rmf",
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": files_meta,
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if args.check_only:
            drift = check_drift(source_root, staged)
            return 1 if drift else 0

        version_dir, status = commit_version(source_root, staged, "nist-ai-rmf")
        print(f"[nist-ai-rmf] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
