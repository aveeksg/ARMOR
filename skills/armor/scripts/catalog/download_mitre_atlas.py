"""Downloader for MITRE ATLAS (dist/ATLAS.yaml + normalised JSON splits)."""

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
import yaml

from ai_standards_versioning import check_drift, commit_version

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STANDARDS_ROOT = Path(
    os.environ.get("ARMOR_STANDARDS_ROOT", str(SCRIPT_DIR.parents[1] / "references" / "ai_standards"))
)

ATLAS_YAML_URL = "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download MITRE ATLAS data")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_STANDARDS_ROOT / "mitre-atlas"),
        help="Target source directory",
    )
    parser.add_argument("--check-only", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    staged = Path(tempfile.mkdtemp(prefix="mitre_atlas_stage_"))
    try:
        resp = requests.get(
            ATLAS_YAML_URL,
            headers={"User-Agent": "ARMOR-Catalog-Sync/6.0.0"},
            timeout=60,
        )
        resp.raise_for_status()
        raw_bytes = resp.content
        (staged / "ATLAS.yaml").write_bytes(raw_bytes)

        parsed = yaml.safe_load(raw_bytes.decode("utf-8")) or {}
        for split_key in ("tactics", "techniques", "mitigations", "case-studies"):
            items = parsed.get(split_key, [])
            out_name = f"{split_key.replace('-', '_')}.json"
            (staged / out_name).write_text(
                json.dumps(items, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

        manifest = {
            "source": "mitre-atlas",
            "url": ATLAS_YAML_URL,
            "atlas_version": str(parsed.get("version", "")),
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if args.check_only:
            drift = check_drift(source_root, staged)
            return 1 if drift else 0

        version_dir, status = commit_version(source_root, staged, "mitre-atlas")
        print(f"[mitre-atlas] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
