"""Downloader for EU AI Act (Regulation (EU) 2024/1689) via EUR-Lex CELLAR."""

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

CELEX_ID = "32024R1689"
CELLAR_BASE = f"https://publications.europa.eu/resource/celex/{CELEX_ID}"


def _fetch(url: str, accept: str) -> bytes:
    resp = requests.get(
        url,
        headers={
            "Accept": accept,
            "Accept-Language": "eng",
            "User-Agent": "ARMOR-Catalog-Sync/6.0.0",
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download EU AI Act via CELLAR")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_STANDARDS_ROOT / "eu-ai-act"),
        help="Target source directory",
    )
    parser.add_argument("--check-only", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    staged = Path(tempfile.mkdtemp(prefix="eu_ai_act_stage_"))
    try:
        xhtml_bytes = _fetch(CELLAR_BASE, "application/xhtml+xml, text/html")
        pdf_bytes = _fetch(CELLAR_BASE, "application/pdf")
        meta_bytes = _fetch(CELLAR_BASE, "application/xml;notice=branch")

        (staged / "eu_ai_act.xhtml").write_bytes(xhtml_bytes)
        (staged / "eu_ai_act.pdf").write_bytes(pdf_bytes)
        (staged / "meta.xml").write_bytes(meta_bytes)

        manifest = {
            "source": "eu-ai-act",
            "celex": CELEX_ID,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": {
                "eu_ai_act.xhtml": hashlib.sha256(xhtml_bytes).hexdigest(),
                "eu_ai_act.pdf": hashlib.sha256(pdf_bytes).hexdigest(),
                "meta.xml": hashlib.sha256(meta_bytes).hexdigest(),
            },
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if args.check_only:
            drift = check_drift(source_root, staged)
            return 1 if drift else 0

        version_dir, status = commit_version(source_root, staged, "eu-ai-act")
        print(f"[eu-ai-act] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
