"""Downloader for AI Incident Database (AIID) slim taxonomy and incident index via GraphQL."""

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

AIID_GRAPHQL_URL = "https://incidentdatabase.ai/api/graphql"
QUERY = """
query {
  incidents(limit: 500) {
    incident_id
    title
    date
  }
  classifications(limit: 500) {
    namespace
    incidents {
      incident_id
    }
    attributes {
      short_name
      value_json
    }
  }
}
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download AI Incident Database slim snapshot")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_STANDARDS_ROOT / "ai-incident-database"),
        help="Target source directory",
    )
    parser.add_argument("--check-only", action="store_true", help="Report drift without writing")
    args = parser.parse_args(argv)

    source_root = Path(args.source_root).resolve()
    staged = Path(tempfile.mkdtemp(prefix="aiid_stage_"))
    try:
        resp = requests.post(
            AIID_GRAPHQL_URL,
            json={"query": QUERY},
            headers={"User-Agent": "ARMOR-Catalog-Sync/6.0.0"},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        body_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        sha256 = hashlib.sha256(body_bytes).hexdigest()

        (staged / "aiid_slim.json").write_bytes(body_bytes)
        manifest = {
            "source": "ai-incident-database",
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "url": AIID_GRAPHQL_URL,
            "sha256": sha256,
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        if args.check_only:
            drift = check_drift(source_root, staged)
            return 1 if drift else 0

        version_dir, status = commit_version(source_root, staged, "ai-incident-database")
        print(f"[ai-incident-database] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
