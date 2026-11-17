"""Content-addressed versioning helper for AI standards sources and the generated catalog."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any


def _content_sha(directory: Path) -> str:
    h = hashlib.sha256()
    files: list[Path] = []
    for root, _, filenames in os.walk(directory):
        for fname in filenames:
            if fname == "manifest.json":
                continue
            files.append(Path(root) / fname)
    files.sort(key=lambda p: p.relative_to(directory).as_posix())
    for p in files:
        rel = p.relative_to(directory).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
    return h.hexdigest()


def read_latest(source_root: Path) -> dict[str, Any] | None:
    latest_path = Path(source_root) / "latest.json"
    if not latest_path.is_file():
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def check_drift(source_root: Path, staged_dir: Path) -> bool:
    sha = _content_sha(Path(staged_dir))
    latest = read_latest(Path(source_root))
    if latest is None:
        return True
    return latest.get("sha") != sha


def commit_version(
    source_root: Path | str,
    staged_dir: Path | str,
    source_label: str,
) -> tuple[Path, str]:
    root = Path(source_root).resolve()
    staged = Path(staged_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    versions_dir = root / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    sha = _content_sha(staged)
    sha8 = sha[:8]
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    iso_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    latest = read_latest(root)
    history_path = root / "history.jsonl"

    if latest is not None and latest.get("sha") == sha:
        shutil.rmtree(staged, ignore_errors=True)
        existing_version = str(latest["version"])
        version_dir = versions_dir / existing_version
        rec = {
            "ts": iso_str,
            "source": source_label,
            "version": existing_version,
            "sha": sha,
            "status": "unchanged",
            "previous": latest.get("version"),
        }
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return version_dir, "unchanged"

    version_name = f"{date_str}__{sha8}"
    version_dir = versions_dir / version_name
    if version_dir.exists():
        shutil.rmtree(version_dir)
    shutil.move(str(staged), str(version_dir))

    prev_version = latest.get("version") if latest is not None else None
    status = "new" if prev_version is None else "changed"

    latest_payload = {
        "version": version_name,
        "sha": sha,
        "committed_at": iso_str,
        "source": source_label,
        "previous": prev_version,
    }
    (root / "latest.json").write_text(json.dumps(latest_payload, indent=2) + "\n", encoding="utf-8")

    rec = {
        "ts": iso_str,
        "source": source_label,
        "version": version_name,
        "sha": sha,
        "status": status,
        "previous": prev_version,
    }
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    return version_dir, status
