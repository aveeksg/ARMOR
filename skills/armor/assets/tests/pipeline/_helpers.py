"""Shared test fixtures and helper builders for the ARMOR pipeline test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MINI_CATALOG: dict[str, Any] = {
    "count": 3,
    "source_sha": "deadbeef12345678",
    "by_category": {
        "Risk & impact assessment": 2,
        "Data governance": 1,
    },
    "sub_guardrails": [
        {
            "number": "GR-01.1",
            "category": "Risk & impact assessment",
            "description": "Classify AI system risk tier prior to deployment.",
            "implementation_hints": "Maintain a system risk card in config.",
            "verification_test": "Verify structured risk tier config exists.",
            "applicability": "any system",
            "standard_references": "EU AI Act Art 6, 9 | NIST GOVERN-1",
        },
        {
            "number": "GR-01.2",
            "category": "Risk & impact assessment",
            "description": "Maintain a continuous risk register across lifecycle changes.",
            "implementation_hints": "Enforce risk register checks in CI.",
            "verification_test": "Verify risk register validation logic.",
            "applicability": "any system",
            "standard_references": "EU AI Act Art 9 | NIST MANAGE-1",
        },
        {
            "number": "GR-02.1",
            "category": "Data governance",
            "description": "Track dataset and retrieval index provenance.",
            "implementation_hints": "Record SHA256 and URI on ingested docs.",
            "verification_test": "Verify ingestion records provenance metadata.",
            "applicability": "RAG or training systems",
            "standard_references": "EU AI Act Art 10 | OWASP LLM08",
        },
    ],
}


def write_mini_catalog(tmp_path: Path) -> Path:
    cat_root = tmp_path / "_catalog"
    v1_dir = cat_root / "versions" / "v1"
    v1_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = v1_dir / "guardrail_matrix.json"
    matrix_path.write_text(json.dumps(MINI_CATALOG, indent=2) + "\n", encoding="utf-8")
    latest_path = cat_root / "latest.json"
    latest_path.write_text(json.dumps({"version": "v1"}, indent=2) + "\n", encoding="utf-8")
    return matrix_path


def make_project(tmp_path: Path) -> Path:
    proj = tmp_path / "sample_project"
    src = proj / "src"
    src.mkdir(parents=True, exist_ok=True)
    lines = [f"# line {i}\ndef func_{i}():\n    return {i}\n" for i in range(1, 8)]
    # Ensure exactly 20 lines in src/main.py
    twenty_lines = "\n".join(f"line_{i} = {i}" for i in range(1, 21)) + "\n"
    (src / "main.py").write_text(twenty_lines, encoding="utf-8")
    (proj / "README.md").write_text("# Sample Project\n\nA sample AI service for testing ARMOR.\n", encoding="utf-8")
    return proj
