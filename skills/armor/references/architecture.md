# ARMOR v6 — Module-by-Module Architecture Notes

## 1. Overview

ARMOR v6 separates **deterministic verification and state management** (Python) from **codebase reasoning and adversarial critique** (the host IDE agent acting via a disk-queue protocol).

## 2. Runtime Package (`skills/armor/scripts/armor/`)

- **`armor_run.py`**: 4-line `runpy` shim placing `scripts/` on `sys.path` and dispatching `armor.__main__`.
- **`cli.py`**: Implements the `armor pipeline <project>` CLI (`--phase`, `--finalize`, `--status`, `--all`, `--catalog`, `--audit-model`, `--validate-report`, `--write-schema`).
- **`file_lock.py`**: Cross-platform stdlib-only exclusive lock combining an in-process `threading.Lock` registry with OS file locking (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) and atomic temp-file replacement (`locked_write`, `locked_append`).

## 3. Pipeline Modules (`skills/armor/scripts/armor/pipeline/`)

- **`state.py`**:
  - Defines `PHASES`, `PHASE_ARTIFACT`, `MAX_AUDIT_REVISIONS = 3`, and `_CITATION_RE`.
  - `RunDir` dataclass manages `.armor/runs/<iso>/`, `queue/`, phase artifacts, and status derivation (`done` > `response-ready (needs --finalize)` > `awaiting-llm` > `pending`).
  - `project_fingerprint()` hashes up to 200 tracked source files (`relpath|st_mtime_ns`).
  - `verify_citation()` enforces path confinement beneath `project_root`, file existence, and line range bounds (`1 <= lo <= hi <= total_lines`).
- **`load.py` (Phase 1)**: Resolves `guardrail_matrix.json` via `_catalog/latest.json` (or `--catalog`) and normalises the 53 sub-guardrails into `01_guardrails.json`.
- **`triage.py` (Phase 2)**: Collects bounded manifest/doc previews (`<= 6000` chars) and top-level directory layout into `triage.request.json`; validates the LLM's applicability tags (`applies`, `partial_scope`, `n_a`) and writes `02_triage.{json,md}`.
- **`adversary.py` (Shared Helper)**: Builds red-team requests (`CONFIRM`, `REVISE`, `INVESTIGATE`), applies row deltas without allowing invented SIDs or order changes, and checks loop convergence (`revision >= MAX_AUDIT_REVISIONS` or zero revisions applied).
- **`triage_audit.py` (Phase 3)**: Multi-round adversary loop (`<= 3` revisions) over Phase 2 applicability rows, persisting intermediate state in `.triage_audit_trail.json` and final output in `03_triage_audit.{json,md}`.
- **`conform.py` (Phase 4)**: Prompts the agent for conformance verdicts over in-scope guardrails (`applies` / `partial_scope`), enforces remediation quality rules, cross-verifies every citation, demotes unverified `NON_GAP` rows to `inconclusive`, logs rejected citations to `.armor/hallucination_log.jsonl`, and writes `04_conformance.{json,md}`.
- **`conform_audit.py` (Phase 5)**: Multi-round adversary loop (`<= 3` revisions) over conformance rows with post-delta citation re-verification on every round, writing `05_conformance_audit.{json,md}`.
- **`report.py` (Phase 6)**: Joins catalog metadata, `triage-audit` applicability, and `conform-audit` verdicts; computes weighted coverage (`implemented=1.0`, `partial=0.6`, `weak=0.3`, `gap=0.0`, `inconclusive=0.0`, `n/a` excluded) and ranked remediation suggestions; validates against `schema.PostureReport` before writing `06_report.json` and `.armor/reports/posture_latest.{json,md}`.
- **`schema.py`**: Single source of truth Pydantic v2 models (`_Strict` with `extra="forbid"`) and JSON Schema synchronization (`schemas/posture_report.schema.json`).

## 4. Catalog Subsystem (`skills/armor/scripts/catalog/`)

- **`ai_standards_versioning.py`**: Content-addressed SHA256 directory hashing (excluding `manifest.json`) that commits new/changed snapshots to `versions/<date>__<sha8>/`, updates `latest.json`, and appends to `history.jsonl`.
- **`refresh_catalog.py`**: Orchestrates the 5 standard downloaders (`download_aiid_slim.py`, `download_eu_ai_act_cellar.py`, `download_mitre_atlas.py`, `download_nist_ai_rmf.py`, `download_owasp_llm_top10.py`) followed by `generate_guardrail_catalog.py`.
