"""Pydantic v2 contract for the Phase 6 PostureReport artifact and JSON Schema helper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["implemented", "partial", "weak", "gap", "inconclusive", "n/a"]
Applicability = Literal["applies", "partial_scope", "n_a", "unknown"]

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "posture_report.schema.json"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GuardrailRow(_Strict):
    sid: str
    family: str
    family_name: str
    description: str
    applicability: Applicability
    applicability_reason: str = ""
    verdict: Verdict
    reasoning: str = ""
    citations: list[str] = Field(default_factory=list)
    gap_summary: str = ""
    remediation: str = ""
    demoted_due_to_hallucination: bool = False


class FamilyCoverage(_Strict):
    family: str
    family_name: str
    in_scope: int = Field(ge=0)
    earned: float = Field(ge=0.0)
    max: float = Field(ge=0.0)
    score_pct: float = Field(ge=0.0, le=100.0)


class Coverage(_Strict):
    overall_pct: float = Field(ge=0.0, le=100.0)
    applicable_only_pct: float = Field(ge=0.0, le=100.0)
    in_scope_count: int = Field(ge=0)
    max_possible_points: float = Field(ge=0.0)
    earned_points: float = Field(ge=0.0)
    by_verdict_in_scope: dict[str, int]
    by_family: list[FamilyCoverage]


class Suggestion(_Strict):
    sid: str
    family: str
    family_name: str
    current_verdict: Literal["gap", "inconclusive", "weak", "partial"]
    points_unlocked: float = Field(ge=0.0, le=1.0)
    family_score_pct: float = Field(ge=0.0, le=100.0)
    action: str
    gap_summary: str = ""
    remediation: str = ""
    reasoning: str = ""


class Totals(_Strict):
    guardrails: int = Field(ge=0)
    by_applicability: dict[str, int]
    by_verdict: dict[str, int]
    gaps: int = Field(ge=0)
    weak_or_partial: int = Field(ge=0)
    inconclusive: int = Field(ge=0)
    open_questions: int = Field(ge=0)


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    sid: str
    critique: str = ""


class PostureReport(_Strict):
    phase: Literal["report"]
    generated_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
    project: str
    run_dir: str
    system_profile: dict[str, Any]
    totals: Totals
    coverage: Coverage
    suggestions: list[Suggestion]
    open_questions: list[OpenQuestion]
    rows: list[GuardrailRow]


def validate_artifact(artifact: dict[str, Any]) -> PostureReport:
    return PostureReport.model_validate(artifact)


def write_schema(path: Path | None = None) -> Path:
    target = Path(path) if path is not None else SCHEMA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = PostureReport.model_json_schema()
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_schema() -> dict[str, Any]:
    if not SCHEMA_PATH.is_file():
        write_schema(SCHEMA_PATH)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
