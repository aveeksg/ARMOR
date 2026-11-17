"""Phase 1: Load and normalise the AI/agentic standards guardrail catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import RunDir


def _find_default_catalog() -> Path:
    # 1. Bundled inside the installed `armor` package (PyPI wheel / sdist)
    pkg_cand = Path(__file__).resolve().parents[1] / "data" / "ai_standards" / "_catalog" / "latest.json"
    if pkg_cand.is_file():
        data = json.loads(pkg_cand.read_text(encoding="utf-8"))
        return pkg_cand.parent / "versions" / data["version"] / "guardrail_matrix.json"

    # 2. Marketplace plugin layout (<skill_root>/references/ai_standards/_catalog/latest.json)
    parents = Path(__file__).resolve().parents
    if len(parents) > 3:
        skill_root = parents[3]
        cand = skill_root / "references" / "ai_standards" / "_catalog" / "latest.json"
        if cand.is_file():
            data = json.loads(cand.read_text(encoding="utf-8"))
            return cand.parent / "versions" / data["version"] / "guardrail_matrix.json"

    # 3. Walk parents looking for ai_standards/_catalog/latest.json
    for parent in parents:
        for rel in (
            Path("references") / "ai_standards" / "_catalog" / "latest.json",
            Path("ai_standards") / "_catalog" / "latest.json",
        ):
            p = parent / rel
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                return p.parent / "versions" / data["version"] / "guardrail_matrix.json"

    raise SystemExit("default catalog not found; pass --catalog PATH")


def _resolve_catalog(catalog_arg: str | Path | None) -> Path:
    if catalog_arg is not None:
        p = Path(catalog_arg).resolve()
        if not p.is_file():
            raise SystemExit(f"catalog file not found: {p}")
        if p.name == "latest.json":
            data = json.loads(p.read_text(encoding="utf-8"))
            return (p.parent / "versions" / data["version"] / "guardrail_matrix.json").resolve()
        return p
    return _find_default_catalog().resolve()


def run(
    project: Path,
    catalog_arg: str | Path | None = None,
    run_dir: RunDir | None = None,
) -> dict[str, Any]:
    if run_dir is None:
        from .state import current_run
        run_dir = current_run(project)

    catalog_path = _resolve_catalog(catalog_arg)
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))

    guardrails: list[dict[str, Any]] = []
    for row in raw.get("sub_guardrails", []):
        num = str(row["number"])
        family = num.split(".", 1)[0] if "." in num else num
        guardrails.append(
            {
                "sid": num,
                "family": family,
                "family_name": row.get("category", ""),
                "description": row.get("description", ""),
                "verification_test": row.get("verification_test", ""),
                "applicability_hint": row.get("applicability", ""),
                "implementation_hints": row.get("implementation_hints", ""),
                "standard_refs": row.get("standard_references", ""),
            }
        )

    catalog_sha = str(raw.get("source_sha") or raw.get("sha") or "")
    artifact: dict[str, Any] = {
        "phase": "load",
        "catalog_path": str(catalog_path),
        "catalog_sha": catalog_sha,
        "count": len(guardrails),
        "guardrails": guardrails,
    }

    art_path = run_dir.artifact("load")
    art_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact
