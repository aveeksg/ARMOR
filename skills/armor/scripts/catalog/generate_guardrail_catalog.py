"""Normalise ingested AI/agentic standards into the 12-family, 53-sub-guardrail catalog."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from ai_standards_versioning import commit_version, read_latest

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STANDARDS_ROOT = Path(
    os.environ.get("ARMOR_STANDARDS_ROOT", str(SCRIPT_DIR.parents[1] / "references" / "ai_standards"))
)

FAMILIES: list[tuple[str, str]] = [
    ("GR-01", "Risk & impact assessment"),
    ("GR-02", "Data governance"),
    ("GR-03", "Transparency & disclosure"),
    ("GR-04", "Human oversight"),
    ("GR-05", "Robustness & accuracy"),
    ("GR-06", "Adversarial security"),
    ("GR-07", "Privacy & data protection"),
    ("GR-08", "Fairness & non-discrimination"),
    ("GR-09", "Content safety"),
    ("GR-10", "Logging, monitoring & incident response"),
    ("GR-11", "Supply-chain & component integrity"),
    ("GR-12", "Agentic autonomy & action safety"),
]

# Authoritative 53 sub-guardrail definitions normalised across EU AI Act, NIST AI RMF,
# MITRE ATLAS, OWASP LLM Top 10 (2025), and the AI Incident Database (MIT AI Risk Repository).
SUB_GUARDRAILS_SPEC: list[dict[str, Any]] = [
    # GR-01: Risk & impact assessment (5)
    {
        "number": "GR-01.1",
        "category": "Risk & impact assessment",
        "description": "Classify AI system risk tier and intended purpose prior to deployment, documenting reasonably foreseeable misuse and affected populations.",
        "implementation_hints": "Maintain a machine-readable system risk card or manifest in repo config specifying risk tier, intended purpose, and out-of-scope uses.",
        "verification_test": "Verify that a structured risk classification configuration or manifest exists and is validated before model or agent execution.",
        "applicability": "any system; pre-deployment",
        "eu": [6, 9, 27],
        "nist": ["GOVERN-1", "MAP-1", "MAP-3", "MAP-5"],
        "owasp": [],
        "atlas": ["AML.M0017"],
        "mit": ["7.3. Lack of capability or robustness", "5.1. Overreliance and unsafe use"],
    },
    {
        "number": "GR-01.2",
        "category": "Risk & impact assessment",
        "description": "Maintain a continuous risk register and iterative risk management lifecycle across design, development, and post-deployment changes.",
        "implementation_hints": "Enforce risk register schema checks in CI or policy-as-code gates when prompts, models, or tools change.",
        "verification_test": "Verify automated validation of risk register entries or policy checks tied to model/agent configuration updates.",
        "applicability": "any AI system",
        "eu": [9],
        "nist": ["GOVERN-1", "MANAGE-1", "MANAGE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["7.1. AI pursuing its own goals in conflict with human goals or values"],
    },
    {
        "number": "GR-01.3",
        "category": "Risk & impact assessment",
        "description": "Perform fundamental rights, safety, and downstream impact assessments for high-impact or customer-facing AI deployments.",
        "implementation_hints": "Include impact assessment assertions and threshold gates in deployment readiness checks.",
        "verification_test": "Check for impact assessment gate logic or pre-flight validation prior to enabling high-impact workflows.",
        "applicability": "high-risk or customer-facing AI systems",
        "eu": [9, 27],
        "nist": ["MAP-2", "MAP-5", "MEASURE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["6.1. Power centralization and unfair distribution of benefits"],
    },
    {
        "number": "GR-01.4",
        "category": "Risk & impact assessment",
        "description": "Define explicit operational boundaries, capability limits, and refusal conditions for out-of-domain requests.",
        "implementation_hints": "Implement domain/topic classifiers or boundary guards in the request intake pipeline before invoking the model.",
        "verification_test": "Verify input routing or domain boundary enforcement that rejects or deflects out-of-scope queries.",
        "applicability": "all LLM and generative AI systems",
        "eu": [9, 13],
        "nist": ["MAP-3", "MANAGE-3"],
        "owasp": ["LLM01", "LLM09"],
        "atlas": ["AML.M0015"],
        "mit": ["5.1. Overreliance and unsafe use"],
    },
    {
        "number": "GR-01.5",
        "category": "Risk & impact assessment",
        "description": "Gate release and runtime activation on quantitative risk acceptance thresholds and sign-off controls.",
        "implementation_hints": "Enforce automated evaluation score thresholds before promoting models, prompts, or agent workflows.",
        "verification_test": "Verify threshold-check functions that block execution or deployment when evaluation metrics fall below required bounds.",
        "applicability": "any production AI system",
        "eu": [9, 43],
        "nist": ["GOVERN-4", "MEASURE-4", "MANAGE-4"],
        "owasp": [],
        "atlas": [],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    # GR-02: Data governance (5)
    {
        "number": "GR-02.1",
        "category": "Data governance",
        "description": "Track dataset, corpus, and retrieval index provenance, lineage, and licensing metadata across ingestion pipelines.",
        "implementation_hints": "Attach source URI, content SHA256 hash, timestamp, and license fields to ingested documents and vector store records.",
        "verification_test": "Verify that ingestion and indexing functions record cryptographic hashes and provenance metadata per document.",
        "applicability": "systems ingesting training, fine-tuning, or RAG data",
        "eu": [10, 53],
        "nist": ["MAP-2", "MEASURE-2"],
        "owasp": ["LLM04", "LLM08"],
        "atlas": ["AML.M0007"],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-02.2",
        "category": "Data governance",
        "description": "Validate data quality, schema conformance, and completeness prior to indexing, embedding, or model consumption.",
        "implementation_hints": "Use strict schema validation (e.g., Pydantic) and null/corruption checks on all ingested records.",
        "verification_test": "Confirm presence of schema validation and rejection handling in data loading and RAG ingestion paths.",
        "applicability": "systems ingesting external or structured data",
        "eu": [10],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM04", "LLM08"],
        "atlas": ["AML.M0007", "AML.M0014"],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-02.3",
        "category": "Data governance",
        "description": "Scan training, fine-tuning, and RAG corpora for data poisoning, backdoor triggers, and anomalous payloads.",
        "implementation_hints": "Run anomaly detection, sanitization filters, and integrity verification over documents before embedding.",
        "verification_test": "Verify sanitization and poisoning detection filters execute on untrusted corpus inputs prior to storage.",
        "applicability": "RAG, fine-tuning, and knowledge-grounded systems",
        "eu": [10, 15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM04", "LLM08"],
        "atlas": ["AML.M0006", "AML.M0007", "AML.M0014"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-02.4",
        "category": "Data governance",
        "description": "Enforce tenant isolation and access-control filtering on vector stores, embeddings, and retrieved context chunks.",
        "implementation_hints": "Bind caller principal/ACL attributes to retrieval queries so cross-tenant chunks are never injected into prompts.",
        "verification_test": "Verify that vector/document retrieval functions require and filter by caller authorization scope or tenant ID.",
        "applicability": "multi-tenant or access-controlled RAG systems",
        "eu": [10],
        "nist": ["GOVERN-6", "MANAGE-3"],
        "owasp": ["LLM02", "LLM08"],
        "atlas": ["AML.M0018"],
        "mit": ["1.2. Privacy violations"],
    },
    {
        "number": "GR-02.5",
        "category": "Data governance",
        "description": "Implement retention schedules, right-to-erasure purge routines, and versioned snapshots for datasets and embeddings.",
        "implementation_hints": "Provide deterministic delete-by-source-ID and TTL expiration jobs across document stores and caches.",
        "verification_test": "Verify existence of TTL/retention enforcement or document deletion routines in storage modules.",
        "applicability": "systems persisting user or enterprise data",
        "eu": [10],
        "nist": ["GOVERN-1", "MANAGE-4"],
        "owasp": ["LLM02"],
        "atlas": [],
        "mit": ["1.2. Privacy violations"],
    },
    # GR-03: Transparency & disclosure (4)
    {
        "number": "GR-03.1",
        "category": "Transparency & disclosure",
        "description": "Disclose clearly to users and downstream consumers when they are interacting with an AI system or reading AI-generated content.",
        "implementation_hints": "Attach explicit AI disclosure headers, metadata flags, or UI notices to all generated responses.",
        "verification_test": "Verify response envelopes or UI rendering templates include an explicit AI-generated disclosure indicator.",
        "applicability": "user-facing AI and content generation systems",
        "eu": [13, 50],
        "nist": ["GOVERN-4", "MAP-1", "MEASURE-2"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["4.3. Lack of transparency or interpretability", "3.1. Pollution of information ecosystem and loss of shared reality"],
    },
    {
        "number": "GR-03.2",
        "category": "Transparency & disclosure",
        "description": "Ground generated claims in verifiable source citations and cross-check citations against the underlying corpus or files.",
        "implementation_hints": "Require structured citations on model outputs and deterministically verify file/document existence and line/span bounds.",
        "verification_test": "Verify post-generation citation validation logic that checks cited sources exist and demotes or flags unverified claims.",
        "applicability": "RAG, coding, compliance, and analytical AI systems",
        "eu": [13],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["3.2. False or misleading information", "4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-03.3",
        "category": "Transparency & disclosure",
        "description": "Provide model/system cards documenting model architecture, version, known limitations, and evaluation benchmarks.",
        "implementation_hints": "Ship structured system/model metadata alongside code and expose version/capability descriptors via CLI or API.",
        "verification_test": "Verify presence of structured system metadata, version identifiers, and documented limitations.",
        "applicability": "any AI system",
        "eu": [11, 13, 53],
        "nist": ["GOVERN-1", "MAP-1", "MEASURE-4"],
        "owasp": [],
        "atlas": [],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-03.4",
        "category": "Transparency & disclosure",
        "description": "Expose interpretable reasoning traces, confidence indicators, or uncertainty warnings on automated assessments.",
        "implementation_hints": "Include structured reasoning fields, uncertainty/inconclusive states, and audit trails in assessment outputs.",
        "verification_test": "Verify output schemas require explicit reasoning and support inconclusive/uncertainty states rather than forced binary verdicts.",
        "applicability": "decision-support and analytical AI systems",
        "eu": [13, 14],
        "nist": ["MEASURE-2", "MANAGE-1"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["4.3. Lack of transparency or interpretability", "5.1. Overreliance and unsafe use"],
    },
    # GR-04: Human oversight (4)
    {
        "number": "GR-04.1",
        "category": "Human oversight",
        "description": "Require human-in-the-loop (HITL) approval before executing high-impact, irreversible, or state-mutating actions.",
        "implementation_hints": "Gate destructive, financial, or external write tool calls behind an explicit confirmation token or approval queue.",
        "verification_test": "Verify that state-mutating or high-risk actions check for explicit user/operator approval before execution.",
        "applicability": "agentic and tool-using AI systems",
        "eu": [14],
        "nist": ["GOVERN-3", "MAP-3", "MANAGE-2"],
        "owasp": ["LLM06"],
        "atlas": ["AML.M0018"],
        "mit": ["5.2. Loss of human agency and autonomy", "7.2. AI possessing dangerous capabilities"],
    },
    {
        "number": "GR-04.2",
        "category": "Human oversight",
        "description": "Provide an immediate stop, cancellation, or kill-switch mechanism to halt autonomous loops and background tasks.",
        "implementation_hints": "Enforce hard iteration caps, timeouts, and signal/cancellation checks inside agent and audit loops.",
        "verification_test": "Verify bounded loop counters (e.g., max revisions/steps) and clean abort handling in execution drivers.",
        "applicability": "autonomous and multi-step AI pipelines",
        "eu": [14],
        "nist": ["GOVERN-3", "MANAGE-3"],
        "owasp": ["LLM06", "LLM10"],
        "atlas": [],
        "mit": ["7.4. Lack of capability to control AI", "5.2. Loss of human agency and autonomy"],
    },
    {
        "number": "GR-04.3",
        "category": "Human oversight",
        "description": "Support human override, correction, and escalation queues for contested or ambiguous model verdicts.",
        "implementation_hints": "Surface unresolved disputes as explicit open_questions for human review rather than silently masking disagreements.",
        "verification_test": "Verify that unconverged or contested items are collected into an explicit open_questions or escalation structure.",
        "applicability": "decision-support and auditing AI systems",
        "eu": [14],
        "nist": ["GOVERN-3", "MANAGE-1", "MANAGE-4"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["5.1. Overreliance and unsafe use"],
    },
    {
        "number": "GR-04.4",
        "category": "Human oversight",
        "description": "Prevent automation bias by presenting counter-evidence, adversarial critiques, and verification status alongside conclusions.",
        "implementation_hints": "Run an independent adversarial critique pass and highlight demoted or weakly supported claims in reports.",
        "verification_test": "Verify presence of adversarial review/critique stages and explicit demotion markers in user-facing reports.",
        "applicability": "analytical, compliance, and recommendation AI systems",
        "eu": [14],
        "nist": ["MAP-3", "MEASURE-2"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["5.1. Overreliance and unsafe use"],
    },
    # GR-05: Robustness & accuracy (5)
    {
        "number": "GR-05.1",
        "category": "Robustness & accuracy",
        "description": "Validate all LLM outputs against strict structural and type schemas before downstream consumption or persistence.",
        "implementation_hints": "Parse and validate every LLM response against JSON Schema or Pydantic models with extra='forbid'; reject malformed payloads.",
        "verification_test": "Verify strict schema validation on LLM responses and final report artifacts prior to writing or acting on them.",
        "applicability": "all structured-output LLM and agentic systems",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM05", "LLM09"],
        "atlas": ["AML.M0015"],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-05.2",
        "category": "Robustness & accuracy",
        "description": "Detect and mitigate hallucinations by cross-verifying model assertions against deterministic ground-truth sources.",
        "implementation_hints": "Resolve file paths, line numbers, or database keys cited by the LLM and automatically demote unverified claims.",
        "verification_test": "Verify deterministic cross-verification of model citations/facts and automatic demotion + logging on failure.",
        "applicability": "all generative AI systems making factual or code assertions",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["3.2. False or misleading information", "7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-05.3",
        "category": "Robustness & accuracy",
        "description": "Handle malformed inputs, transient failures, and partial responses gracefully with deterministic error codes and recovery paths.",
        "implementation_hints": "Wrap file/JSON parsing and phase transitions in explicit error handlers that emit actionable error messages and non-zero exit codes.",
        "verification_test": "Verify deterministic validation error handling and non-zero exit codes when inputs or responses are missing or invalid.",
        "applicability": "all AI systems",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM05", "LLM10"],
        "atlas": [],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-05.4",
        "category": "Robustness & accuracy",
        "description": "Maintain an automated regression and unit test suite covering pipeline invariants, edge cases, and failure modes.",
        "implementation_hints": "Ship automated pytest tests verifying happy paths, invalid inputs, hallucination demotions, and schema drift.",
        "verification_test": "Verify existence of automated tests covering schema validation, citation verification, and pipeline phase transitions.",
        "applicability": "all AI systems",
        "eu": [15, 43],
        "nist": ["MEASURE-1", "MEASURE-2", "MEASURE-4"],
        "owasp": [],
        "atlas": [],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-05.5",
        "category": "Robustness & accuracy",
        "description": "Enforce multi-agent or adversarial cross-checking to reduce single-pass model blind spots and drift.",
        "implementation_hints": "Pair primary assessment phases with bounded adversarial red-team audit phases that can CONFIRM, REVISE, or INVESTIGATE.",
        "verification_test": "Verify implementation of adversarial audit phases that critique and apply deltas to primary LLM outputs.",
        "applicability": "high-assurance analytical and agentic systems",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM09"],
        "atlas": ["AML.M0003"],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    # GR-06: Adversarial security (5)
    {
        "number": "GR-06.1",
        "category": "Adversarial security",
        "description": "Defend against direct and indirect prompt injection by separating untrusted data from system instructions and constraining model outputs.",
        "implementation_hints": "Isolate untrusted repository content into structured data fields, forbid prose execution, and require strict JSON schema adherence.",
        "verification_test": "Verify that untrusted inputs are structured separately from instructions and responses are strictly validated as data.",
        "applicability": "all LLM and agentic systems processing untrusted inputs",
        "eu": [15],
        "nist": ["MAP-3", "MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM01", "LLM08"],
        "atlas": ["AML.M0015", "AML.M0019"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-06.2",
        "category": "Adversarial security",
        "description": "Sanitize and validate all model-generated strings, paths, and parameters before passing them to OS, filesystem, shell, or database APIs.",
        "implementation_hints": "Resolve paths against project_root, reject '..' traversal, avoid shell=True, and validate identifiers against strict regexes.",
        "verification_test": "Verify path traversal checks (relative_to project_root) and absence of unsanitized shell interpolation.",
        "applicability": "all AI systems interacting with filesystems, shells, or APIs",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM05", "LLM06"],
        "atlas": ["AML.M0015", "AML.M0018"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-06.3",
        "category": "Adversarial security",
        "description": "Enforce resource bounds, input size limits, and loop caps to prevent denial-of-service or unbounded token consumption.",
        "implementation_hints": "Truncate ingested manifest/doc previews (e.g., 6000 chars), cap file walks (e.g., 200 files), and bound audit revisions.",
        "verification_test": "Verify explicit character/file limits on context gathering and hard upper bounds on retry/revision loops.",
        "applicability": "all LLM and agentic systems",
        "eu": [15],
        "nist": ["MANAGE-3"],
        "owasp": ["LLM10"],
        "atlas": ["AML.M0004"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-06.4",
        "category": "Adversarial security",
        "description": "Prevent system prompt leakage and sensitive internal context exposure in user-facing or downstream outputs.",
        "implementation_hints": "Emit only validated contract fields in final reports and agent wrappers; strip internal prompts and raw source excerpts.",
        "verification_test": "Verify that external output contracts exclude raw system prompts, credentials, and unrestricted source dumps.",
        "applicability": "all LLM systems",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM02", "LLM07"],
        "atlas": ["AML.M0002", "AML.M0015"],
        "mit": ["2.2. AI system security vulnerabilities and attacks", "1.2. Privacy violations"],
    },
    {
        "number": "GR-06.5",
        "category": "Adversarial security",
        "description": "Conduct regular adversarial red-teaming against model verdicts and evidence claims under strict read-scope constraints.",
        "implementation_hints": "Run dedicated adversary phases constrained to auditing existing citations without inventing new scope.",
        "verification_test": "Verify adversary instructions and delta application forbid inventing new IDs or expanding scope.",
        "applicability": "all high-assurance AI systems",
        "eu": [15, 55],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM01", "LLM09"],
        "atlas": ["AML.M0003"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    # GR-07: Privacy & data protection (4)
    {
        "number": "GR-07.1",
        "category": "Privacy & data protection",
        "description": "Minimize sensitive and personal data exposure by restricting context collection to necessary manifests and bounded file excerpts.",
        "implementation_hints": "Read only curated manifest filenames with character caps and skip hidden/credential directories during project walks.",
        "verification_test": "Verify that context collection skips dotfiles/environments and enforces strict character and file count limits.",
        "applicability": "all AI systems accessing user or repository data",
        "eu": [10, 15],
        "nist": ["GOVERN-1", "MAP-2", "MANAGE-3"],
        "owasp": ["LLM02"],
        "atlas": ["AML.M0012"],
        "mit": ["1.2. Privacy violations"],
    },
    {
        "number": "GR-07.2",
        "category": "Privacy & data protection",
        "description": "Prevent unauthorized outbound network exfiltration of codebase or user data during inference and pipeline execution.",
        "implementation_hints": "Execute assessment pipelines purely locally via disk-queue exchanges without opening outbound network sockets.",
        "verification_test": "Verify that runtime pipeline modules make zero network requests and never import or invoke external HTTP/LLM clients.",
        "applicability": "all enterprise and local-first AI tools",
        "eu": [15],
        "nist": ["GOVERN-6", "MANAGE-3"],
        "owasp": ["LLM02", "LLM06"],
        "atlas": ["AML.M0018"],
        "mit": ["1.2. Privacy violations", "2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-07.3",
        "category": "Privacy & data protection",
        "description": "Scrub or exclude secrets, API keys, and credentials from logs, artifacts, and model context windows.",
        "implementation_hints": "Never read .env or credential files into prompts and avoid hardcoding or logging tokens in pipeline state.",
        "verification_test": "Verify that .env and secret files are excluded from manifest candidate lists and no credentials appear in artifacts.",
        "applicability": "all AI systems",
        "eu": [10, 15],
        "nist": ["MANAGE-3"],
        "owasp": ["LLM02"],
        "atlas": [],
        "mit": ["1.2. Privacy violations"],
    },
    {
        "number": "GR-07.4",
        "category": "Privacy & data protection",
        "description": "Confine all runtime state, temporary files, and reports to a designated, git-ignorable workspace directory.",
        "implementation_hints": "Write all run artifacts, queues, logs, and reports exclusively beneath <project_root>/.armor/.",
        "verification_test": "Verify that all runtime file writes target <project_root>/.armor/ (or atomic temp files in the same directory).",
        "applicability": "all local and repository-auditing AI tools",
        "eu": [10, 12],
        "nist": ["GOVERN-1", "MANAGE-3"],
        "owasp": ["LLM02"],
        "atlas": [],
        "mit": ["1.2. Privacy violations"],
    },
    # GR-08: Fairness & non-discrimination (4)
    {
        "number": "GR-08.1",
        "category": "Fairness & non-discrimination",
        "description": "Evaluate and document affected user populations and potential disparate impacts during system profiling.",
        "implementation_hints": "Require user_population and data_sensitivity fields in the Phase 2 system_profile schema.",
        "verification_test": "Verify that the triage system_profile schema requires explicit user_population profiling.",
        "applicability": "all AI systems",
        "eu": [10, 13, 27],
        "nist": ["MAP-1", "MAP-2", "MEASURE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["1.1. Unfair discrimination and misrepresentation"],
    },
    {
        "number": "GR-08.2",
        "category": "Fairness & non-discrimination",
        "description": "Apply consistent, deterministic scoring weights and evaluation criteria across all assessed components or subjects.",
        "implementation_hints": "Compute posture scores using a fixed, transparent weight table (VERDICT_WEIGHT) and deterministic sorting.",
        "verification_test": "Verify that coverage and suggestion rankings are computed deterministically from a fixed weight map.",
        "applicability": "scoring, ranking, and auditing AI systems",
        "eu": [10, 15],
        "nist": ["MEASURE-1", "MEASURE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["1.1. Unfair discrimination and misrepresentation"],
    },
    {
        "number": "GR-08.3",
        "category": "Fairness & non-discrimination",
        "description": "Exclude inapplicable criteria from scoring denominators so specialized systems are not unfairly penalized.",
        "implementation_hints": "Exclude rows with verdict == 'n/a' from in_scope_count and max_possible_points when computing coverage percentages.",
        "verification_test": "Verify that 'n/a' verdicts are excluded from the coverage denominator in report rollup calculations.",
        "applicability": "evaluation and compliance scoring systems",
        "eu": [9, 15],
        "nist": ["MEASURE-1", "MEASURE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["1.1. Unfair discrimination and misrepresentation"],
    },
    {
        "number": "GR-08.4",
        "category": "Fairness & non-discrimination",
        "description": "Audit subjective classifications through an independent review pass to detect biased or unsubstantiated scoping decisions.",
        "implementation_hints": "Subject all Phase 2 applicability tags (applies/partial_scope/n_a) to the Phase 3 triage-audit red-team loop.",
        "verification_test": "Verify that triage applicability decisions are audited by triage-audit before conformance scoring proceeds.",
        "applicability": "classification and triage AI systems",
        "eu": [10, 14],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": [],
        "atlas": [],
        "mit": ["1.1. Unfair discrimination and misrepresentation"],
    },
    # GR-09: Content safety (4)
    {
        "number": "GR-09.1",
        "category": "Content safety",
        "description": "Enforce output content quality and forbid vague, boilerplate, or non-actionable safety/remediation advice.",
        "implementation_hints": "Instruct the model with explicit remediation quality rules and a list of banned boilerplate phrases.",
        "verification_test": "Verify that conformance instructions mandate codebase-specific, action-leading remediations and list banned phrases.",
        "applicability": "advisory, code-review, and remediation-generating AI systems",
        "eu": [13, 15],
        "nist": ["MEASURE-2", "MANAGE-2"],
        "owasp": ["LLM05", "LLM09"],
        "atlas": [],
        "mit": ["5.1. Overreliance and unsafe use"],
    },
    {
        "number": "GR-09.2",
        "category": "Content safety",
        "description": "Escape and sanitize untrusted or model-generated strings before rendering them into Markdown tables or reports.",
        "implementation_hints": "Escape pipe characters ('|') and normalize newlines when rendering model reasoning and actions into Markdown tables.",
        "verification_test": "Verify Markdown rendering functions escape '|' and newlines in table cells.",
        "applicability": "systems generating Markdown or HTML reports from LLM outputs",
        "eu": [15],
        "nist": ["MANAGE-3"],
        "owasp": ["LLM05"],
        "atlas": [],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-09.3",
        "category": "Content safety",
        "description": "Provide safe, deterministic fallback guidance whenever model-generated remediation text is missing or inconclusive.",
        "implementation_hints": "Supply deterministic fallback action strings for inconclusive or empty-remediation rows during report generation.",
        "verification_test": "Verify report suggestion builder provides explicit fallback action strings when remediation is empty.",
        "applicability": "advisory and reporting AI systems",
        "eu": [13, 15],
        "nist": ["MANAGE-2", "MANAGE-3"],
        "owasp": ["LLM09"],
        "atlas": [],
        "mit": ["5.1. Overreliance and unsafe use"],
    },
    {
        "number": "GR-09.4",
        "category": "Content safety",
        "description": "Constrain agent wrapper summaries to concise, bounded notes free of raw source code, citations, or prompt instructions.",
        "implementation_hints": "Enforce a strict <200 character single-line summary note in the agent YAML verdict contract.",
        "verification_test": "Verify agent wrapper specification enforces bounded notes (<200 chars) with no source excerpts or prompts.",
        "applicability": "agent wrappers and automated CI/CD gates",
        "eu": [13, 15],
        "nist": ["GOVERN-4", "MANAGE-3"],
        "owasp": ["LLM02", "LLM05"],
        "atlas": [],
        "mit": ["1.2. Privacy violations"],
    },
    # GR-10: Logging, monitoring & incident response (5)
    {
        "number": "GR-10.1",
        "category": "Logging, monitoring & incident response",
        "description": "Maintain an immutable, timestamped run directory recording the input/output artifact of every pipeline phase.",
        "implementation_hints": "Create UTC-timestamped directories under .armor/runs/<iso>/ and persist numbered JSON/MD artifacts for Phases 1–6.",
        "verification_test": "Verify that new_run creates UTC-timestamped run directories and each phase persists its numbered artifact.",
        "applicability": "all production and auditing AI pipelines",
        "eu": [12, 19],
        "nist": ["GOVERN-1", "MEASURE-2", "MANAGE-4"],
        "owasp": [],
        "atlas": ["AML.M0016"],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-10.2",
        "category": "Logging, monitoring & incident response",
        "description": "Log every detected model hallucination or rejected citation to an append-only structured incident log.",
        "implementation_hints": "Append JSONL records with UTC timestamp, phase, sid, citation, and rejection reason to .armor/hallucination_log.jsonl.",
        "verification_test": "Verify that rejected citations in conform and conform-audit are appended to hallucination_log.jsonl.",
        "applicability": "all citation-backed generative AI systems",
        "eu": [12, 73],
        "nist": ["MEASURE-2", "MANAGE-4"],
        "owasp": ["LLM09"],
        "atlas": ["AML.M0016"],
        "mit": ["3.2. False or misleading information", "4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-10.3",
        "category": "Logging, monitoring & incident response",
        "description": "Record full multi-round adversarial audit trails capturing per-round verdict counts, critiques, and before/after row diffs.",
        "implementation_hints": "Persist audit_trail arrays in 03_triage_audit.json and 05_conformance_audit.json with before/after revision records.",
        "verification_test": "Verify that audit phases record per-round verdict_counts and before/after diffs in audit_trail.",
        "applicability": "systems with multi-step or adversarial review loops",
        "eu": [12],
        "nist": ["MEASURE-2", "MANAGE-4"],
        "owasp": [],
        "atlas": [],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-10.4",
        "category": "Logging, monitoring & incident response",
        "description": "Enforce mandatory skill-usage telemetry tracking across parent skills and delegated sub-agents.",
        "implementation_hints": "Gate skill execution on emitting start and end telemetry events with propagated PARENT_TRACKERID.",
        "verification_test": "Verify that SKILL.md defines a mandatory telemetry gate before tool calls, sub-agents, and final responses.",
        "applicability": "marketplace skills and multi-agent plugins",
        "eu": [12],
        "nist": ["GOVERN-1", "MANAGE-4"],
        "owasp": [],
        "atlas": ["AML.M0016"],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    {
        "number": "GR-10.5",
        "category": "Logging, monitoring & incident response",
        "description": "Expose a deterministic CLI status inspection command reporting live progress across all pipeline phases.",
        "implementation_hints": "Support `--status` on the pipeline CLI to inspect whether each phase is pending, awaiting-llm, response-ready, or done.",
        "verification_test": "Verify that `pipeline <project> --status` reports the current run root and the state of every phase.",
        "applicability": "multi-phase AI pipelines",
        "eu": [12, 14],
        "nist": ["GOVERN-3", "MANAGE-4"],
        "owasp": [],
        "atlas": [],
        "mit": ["4.3. Lack of transparency or interpretability"],
    },
    # GR-11: Supply-chain & component integrity (4)
    {
        "number": "GR-11.1",
        "category": "Supply-chain & component integrity",
        "description": "Version and content-address all external standards, catalogs, and reference artifacts using cryptographic SHA256 hashes.",
        "implementation_hints": "Commit catalog and standard updates via content-addressed `<date>__<sha8>` directories, `latest.json`, and `history.jsonl`.",
        "verification_test": "Verify content-addressed SHA256 hashing and manifest/history tracking in ai_standards_versioning.py.",
        "applicability": "systems depending on external catalogs, standards, or model artifacts",
        "eu": [15, 53],
        "nist": ["GOVERN-6", "MAP-2", "MANAGE-3"],
        "owasp": ["LLM03"],
        "atlas": ["AML.M0007", "AML.M0014"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-11.2",
        "category": "Supply-chain & component integrity",
        "description": "Compute deterministic source fingerprints of the target codebase to detect concurrent edits or environment drift.",
        "implementation_hints": "Hash sorted relative paths and modification timestamps across tracked source extensions via project_fingerprint().",
        "verification_test": "Verify that project_fingerprint() produces a deterministic SHA256 prefix that changes whenever a source file is edited.",
        "applicability": "codebase analysis and auditing tools",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM03"],
        "atlas": ["AML.M0014"],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-11.3",
        "category": "Supply-chain & component integrity",
        "description": "Minimize third-party runtime dependencies and isolate network-fetching utilities from the core execution runtime.",
        "implementation_hints": "Require only pydantic at runtime (stdlib for everything else); isolate requests/pyyaml to offline catalog refresh scripts.",
        "verification_test": "Verify that core `armor/` runtime modules import only stdlib and pydantic.",
        "applicability": "all software and AI plugins",
        "eu": [15],
        "nist": ["GOVERN-6", "MANAGE-3"],
        "owasp": ["LLM03"],
        "atlas": ["AML.M0014"],
        "mit": ["2.2. AI system security vulnerabilities and attacks"],
    },
    {
        "number": "GR-11.4",
        "category": "Supply-chain & component integrity",
        "description": "Keep packaged JSON Schemas byte-synchronized with runtime data models and provide automated drift verification.",
        "implementation_hints": "Ship `posture_report.schema.json` generated from `PostureReport.model_json_schema()` and enforce byte equality in tests.",
        "verification_test": "Verify `--write-schema` and test assertions that `posture_report.schema.json` byte-equals `PostureReport.model_json_schema()`.",
        "applicability": "all schema-driven AI pipelines",
        "eu": [15],
        "nist": ["MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM03", "LLM05"],
        "atlas": [],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    # GR-12: Agentic autonomy & action safety (4)
    {
        "number": "GR-12.1",
        "category": "Agentic autonomy & action safety",
        "description": "Enforce strict phase ordering so downstream agent actions cannot execute before prerequisite artifacts are verified.",
        "implementation_hints": "Guard each phase entry point with `require_phase_done(run, prerequisite_phase)` and abort with exact unblock instructions.",
        "verification_test": "Verify that calling later phases before earlier phases raises SystemExit via `require_phase_done`.",
        "applicability": "multi-step agentic workflows",
        "eu": [14, 15],
        "nist": ["GOVERN-3", "MANAGE-3"],
        "owasp": ["LLM06"],
        "atlas": ["AML.M0018"],
        "mit": ["7.4. Lack of capability to control AI", "5.2. Loss of human agency and autonomy"],
    },
    {
        "number": "GR-12.2",
        "category": "Agentic autonomy & action safety",
        "description": "Prevent recursive self-auditing or runaway self-targeting in autonomous agent wrappers.",
        "implementation_hints": "Enforce a mandatory self-targeting guard in `armor-agent` that refuses paths resolving to `armor-agent-plugin`.",
        "verification_test": "Verify that the agent wrapper specification mandates a self-targeting refusal returning `verdict: fail` and zeroed counts.",
        "applicability": "autonomous auditing and delegation agents",
        "eu": [14, 15],
        "nist": ["GOVERN-3", "MANAGE-3"],
        "owasp": ["LLM06", "LLM10"],
        "atlas": ["AML.M0018"],
        "mit": ["7.4. Lack of capability to control AI", "7.1. AI pursuing its own goals in conflict with human goals or values"],
    },
    {
        "number": "GR-12.3",
        "category": "Agentic autonomy & action safety",
        "description": "Protect concurrent file mutations with cross-platform exclusive file locks and atomic write-and-replace primitives.",
        "implementation_hints": "Provide `exclusive_lock`, `locked_write` (mkstemp + os.replace), and `locked_append` in `file_lock.py`.",
        "verification_test": "Verify cross-platform locking (`msvcrt` / `fcntl` + `threading.Lock`) and atomic `os.replace` writes in `file_lock.py`.",
        "applicability": "concurrent or multi-agent local workflows",
        "eu": [15],
        "nist": ["MANAGE-3"],
        "owasp": ["LLM06"],
        "atlas": [],
        "mit": ["7.3. Lack of capability or robustness"],
    },
    {
        "number": "GR-12.4",
        "category": "Agentic autonomy & action safety",
        "description": "Constrain red-team adversary agents to read-only verification of cited evidence without expanding scope or inventing findings.",
        "implementation_hints": "Instruct adversary phases not to read files beyond cited `file:line` spans and ignore any unknown SIDs in apply_deltas.",
        "verification_test": "Verify `apply_deltas` ignores unknown SIDs (recording them in `unknown_sids`) and preserves original row ordering.",
        "applicability": "multi-agent and adversarial AI systems",
        "eu": [14, 15],
        "nist": ["GOVERN-3", "MEASURE-2", "MANAGE-3"],
        "owasp": ["LLM06"],
        "atlas": ["AML.M0018"],
        "mit": ["7.4. Lack of capability to control AI"],
    },
]


def _format_standard_refs(spec: dict[str, Any]) -> str:
    parts: list[str] = []
    if spec["eu"]:
        arts = ", ".join(str(a) for a in spec["eu"])
        parts.append(f"EU AI Act Art {arts}")
    if spec["nist"]:
        parts.append("NIST " + ", ".join(spec["nist"]))
    if spec["owasp"]:
        parts.append("OWASP " + ", ".join(spec["owasp"]))
    if spec["atlas"]:
        parts.append("ATLAS " + ", ".join(spec["atlas"]))
    if spec["mit"]:
        parts.append("MIT " + "; ".join(spec["mit"]))
    return " | ".join(parts)


def build_catalog_payloads(standards_root: Path) -> dict[str, Any]:
    sub_guardrails: list[dict[str, Any]] = []
    by_category: dict[str, int] = {}

    for item in SUB_GUARDRAILS_SPEC:
        cat = item["category"]
        by_category[cat] = by_category.get(cat, 0) + 1
        sub_guardrails.append(
            {
                "number": item["number"],
                "category": cat,
                "description": item["description"],
                "implementation_hints": item["implementation_hints"],
                "verification_test": item["verification_test"],
                "applicability": item["applicability"],
                "standard_references": _format_standard_refs(item),
                "standard_references_detail": {
                    "eu_ai_act_articles": item["eu"],
                    "nist_ai_rmf_functions": item["nist"],
                    "owasp_llm_top10": item["owasp"],
                    "atlas_mitigations": item["atlas"],
                    "mit_subdomains": item["mit"],
                },
            }
        )

    matrix_source_sha = hashlib.sha256(
        json.dumps(sub_guardrails, sort_keys=True).encode("utf-8")
    ).hexdigest()

    guardrail_matrix = {
        "count": len(sub_guardrails),
        "source_sha": matrix_source_sha,
        "by_category": by_category,
        "sub_guardrails": sub_guardrails,
    }

    families_list: list[dict[str, Any]] = []
    coverage_by_family: dict[str, Any] = {}
    for fam_id, fam_name in FAMILIES:
        f_subs = [g for g in sub_guardrails if g["number"].startswith(fam_id + ".")]
        families_list.append(
            {
                "id": fam_id,
                "name": fam_name,
                "count": len(f_subs),
                "sub_guardrails": f_subs,
            }
        )
        eu_set = sorted({a for g in f_subs for a in g["standard_references_detail"]["eu_ai_act_articles"]})
        nist_set = sorted({n for g in f_subs for n in g["standard_references_detail"]["nist_ai_rmf_functions"]})
        owasp_set = sorted({o for g in f_subs for o in g["standard_references_detail"]["owasp_llm_top10"]})
        atlas_set = sorted({m for g in f_subs for m in g["standard_references_detail"]["atlas_mitigations"]})
        mit_set = sorted({d for g in f_subs for d in g["standard_references_detail"]["mit_subdomains"]})
        coverage_by_family[fam_id] = {
            "family_name": fam_name,
            "sub_guardrail_count": len(f_subs),
            "eu_ai_act_articles": eu_set,
            "nist_ai_rmf_functions": nist_set,
            "owasp_llm_top10": owasp_set,
            "atlas_mitigations": atlas_set,
            "mit_subdomains": mit_set,
        }

    guardrail_catalog = {
        "version": "6.0.0",
        "families_count": len(FAMILIES),
        "sub_guardrails_count": len(sub_guardrails),
        "families": families_list,
    }

    source_coverage = {
        "totals": {
            "guardrails": len(FAMILIES),
            "sub_guardrails": len(sub_guardrails),
        },
        "by_family": coverage_by_family,
    }

    source_versions: dict[str, Any] = {}
    for src_name in (
        "ai-incident-database",
        "eu-ai-act",
        "mitre-atlas",
        "nist-ai-rmf",
        "owasp-llm-top10",
    ):
        latest = read_latest(standards_root / src_name)
        if latest:
            source_versions[src_name] = {
                "version": latest.get("version"),
                "sha": latest.get("sha"),
            }
        else:
            source_versions[src_name] = {
                "version": "2026-05-12__pinned",
                "sha": "",
            }

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": {
            "guardrails": len(FAMILIES),
            "sub_guardrails": len(sub_guardrails),
        },
        "sources": source_versions,
    }

    return {
        "guardrail_matrix": guardrail_matrix,
        "guardrail_catalog": guardrail_catalog,
        "source_coverage": source_coverage,
        "manifest": manifest,
    }


def _render_matrix_md(matrix: dict[str, Any]) -> str:
    lines = [
        "# ARMOR Guardrail Matrix (53 Sub-Guardrails)",
        "",
        "| SID | Category | Description | Verification Test | Applicability | Standard References |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for g in matrix["sub_guardrails"]:
        lines.append(
            f"| {g['number']} | {g['category']} | {g['description']} | "
            f"{g['verification_test']} | {g['applicability']} | {g['standard_references']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_matrix_csv(matrix: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "number",
            "category",
            "description",
            "implementation_hints",
            "verification_test",
            "applicability",
            "standard_references",
        ]
    )
    for g in matrix["sub_guardrails"]:
        writer.writerow(
            [
                g["number"],
                g["category"],
                g["description"],
                g["implementation_hints"],
                g["verification_test"],
                g["applicability"],
                g["standard_references"],
            ]
        )
    return buf.getvalue()


def _render_catalog_md(catalog: dict[str, Any]) -> str:
    lines = [
        "# ARMOR AI/Agentic Guardrail Catalog",
        "",
        f"Total families: **{catalog['families_count']}** | Total sub-guardrails: **{catalog['sub_guardrails_count']}**",
        "",
    ]
    for fam in catalog["families"]:
        lines.append(f"## {fam['id']} — {fam['name']} ({fam['count']})")
        lines.append("")
        for g in fam["sub_guardrails"]:
            lines.append(f"### {g['number']}: {g['description']}")
            lines.append(f"- **Applicability**: {g['applicability']}")
            lines.append(f"- **Verification test**: {g['verification_test']}")
            lines.append(f"- **Implementation hints**: {g['implementation_hints']}")
            lines.append(f"- **Standards**: {g['standard_references']}")
            lines.append("")
    return "\n".join(lines)


def write_catalog_files(target_dir: Path, payloads: dict[str, Any]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    matrix = payloads["guardrail_matrix"]
    catalog = payloads["guardrail_catalog"]
    coverage = payloads["source_coverage"]
    manifest = payloads["manifest"]

    (target_dir / "guardrail_matrix.json").write_text(
        json.dumps(matrix, indent=2) + "\n", encoding="utf-8"
    )
    (target_dir / "guardrail_matrix.md").write_text(_render_matrix_md(matrix), encoding="utf-8")
    (target_dir / "guardrail_matrix.csv").write_text(_render_matrix_csv(matrix), encoding="utf-8")
    (target_dir / "guardrail_catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    (target_dir / "guardrail_catalog.md").write_text(_render_catalog_md(catalog), encoding="utf-8")
    (target_dir / "source_coverage.json").write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
    )
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate normalised 53-row guardrail catalog")
    parser.add_argument(
        "--standards-root",
        default=str(DEFAULT_STANDARDS_ROOT),
        help="Root directory of ai_standards",
    )
    args = parser.parse_args(argv)

    standards_root = Path(args.standards_root).resolve()
    catalog_root = standards_root / "_catalog"
    staged = Path(tempfile.mkdtemp(prefix="guardrail_catalog_stage_"))
    try:
        payloads = build_catalog_payloads(standards_root)
        write_catalog_files(staged, payloads)
        version_dir, status = commit_version(catalog_root, staged, "_catalog")
        print(f"[_catalog] {status} -> {version_dir}")
        return 0
    finally:
        shutil.rmtree(staged, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
