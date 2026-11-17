# ARMOR AI/Agentic Guardrail Catalog

Total families: **12** | Total sub-guardrails: **53**

## GR-01 — Risk & impact assessment (5)

### GR-01.1: Classify AI system risk tier and intended purpose prior to deployment, documenting reasonably foreseeable misuse and affected populations.
- **Applicability**: any system; pre-deployment
- **Verification test**: Verify that a structured risk classification configuration or manifest exists and is validated before model or agent execution.
- **Implementation hints**: Maintain a machine-readable system risk card or manifest in repo config specifying risk tier, intended purpose, and out-of-scope uses.
- **Standards**: EU AI Act Art 6, 9, 27 | NIST GOVERN-1, MAP-1, MAP-3, MAP-5 | ATLAS AML.M0017 | MIT 7.3. Lack of capability or robustness; 5.1. Overreliance and unsafe use

### GR-01.2: Maintain a continuous risk register and iterative risk management lifecycle across design, development, and post-deployment changes.
- **Applicability**: any AI system
- **Verification test**: Verify automated validation of risk register entries or policy checks tied to model/agent configuration updates.
- **Implementation hints**: Enforce risk register schema checks in CI or policy-as-code gates when prompts, models, or tools change.
- **Standards**: EU AI Act Art 9 | NIST GOVERN-1, MANAGE-1, MANAGE-2 | MIT 7.1. AI pursuing its own goals in conflict with human goals or values

### GR-01.3: Perform fundamental rights, safety, and downstream impact assessments for high-impact or customer-facing AI deployments.
- **Applicability**: high-risk or customer-facing AI systems
- **Verification test**: Check for impact assessment gate logic or pre-flight validation prior to enabling high-impact workflows.
- **Implementation hints**: Include impact assessment assertions and threshold gates in deployment readiness checks.
- **Standards**: EU AI Act Art 9, 27 | NIST MAP-2, MAP-5, MEASURE-2 | MIT 6.1. Power centralization and unfair distribution of benefits

### GR-01.4: Define explicit operational boundaries, capability limits, and refusal conditions for out-of-domain requests.
- **Applicability**: all LLM and generative AI systems
- **Verification test**: Verify input routing or domain boundary enforcement that rejects or deflects out-of-scope queries.
- **Implementation hints**: Implement domain/topic classifiers or boundary guards in the request intake pipeline before invoking the model.
- **Standards**: EU AI Act Art 9, 13 | NIST MAP-3, MANAGE-3 | OWASP LLM01, LLM09 | ATLAS AML.M0015 | MIT 5.1. Overreliance and unsafe use

### GR-01.5: Gate release and runtime activation on quantitative risk acceptance thresholds and sign-off controls.
- **Applicability**: any production AI system
- **Verification test**: Verify threshold-check functions that block execution or deployment when evaluation metrics fall below required bounds.
- **Implementation hints**: Enforce automated evaluation score thresholds before promoting models, prompts, or agent workflows.
- **Standards**: EU AI Act Art 9, 43 | NIST GOVERN-4, MEASURE-4, MANAGE-4 | MIT 7.3. Lack of capability or robustness

## GR-02 — Data governance (5)

### GR-02.1: Track dataset, corpus, and retrieval index provenance, lineage, and licensing metadata across ingestion pipelines.
- **Applicability**: systems ingesting training, fine-tuning, or RAG data
- **Verification test**: Verify that ingestion and indexing functions record cryptographic hashes and provenance metadata per document.
- **Implementation hints**: Attach source URI, content SHA256 hash, timestamp, and license fields to ingested documents and vector store records.
- **Standards**: EU AI Act Art 10, 53 | NIST MAP-2, MEASURE-2 | OWASP LLM04, LLM08 | ATLAS AML.M0007 | MIT 4.3. Lack of transparency or interpretability

### GR-02.2: Validate data quality, schema conformance, and completeness prior to indexing, embedding, or model consumption.
- **Applicability**: systems ingesting external or structured data
- **Verification test**: Confirm presence of schema validation and rejection handling in data loading and RAG ingestion paths.
- **Implementation hints**: Use strict schema validation (e.g., Pydantic) and null/corruption checks on all ingested records.
- **Standards**: EU AI Act Art 10 | NIST MEASURE-2, MANAGE-2 | OWASP LLM04, LLM08 | ATLAS AML.M0007, AML.M0014 | MIT 7.3. Lack of capability or robustness

### GR-02.3: Scan training, fine-tuning, and RAG corpora for data poisoning, backdoor triggers, and anomalous payloads.
- **Applicability**: RAG, fine-tuning, and knowledge-grounded systems
- **Verification test**: Verify sanitization and poisoning detection filters execute on untrusted corpus inputs prior to storage.
- **Implementation hints**: Run anomaly detection, sanitization filters, and integrity verification over documents before embedding.
- **Standards**: EU AI Act Art 10, 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM04, LLM08 | ATLAS AML.M0006, AML.M0007, AML.M0014 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-02.4: Enforce tenant isolation and access-control filtering on vector stores, embeddings, and retrieved context chunks.
- **Applicability**: multi-tenant or access-controlled RAG systems
- **Verification test**: Verify that vector/document retrieval functions require and filter by caller authorization scope or tenant ID.
- **Implementation hints**: Bind caller principal/ACL attributes to retrieval queries so cross-tenant chunks are never injected into prompts.
- **Standards**: EU AI Act Art 10 | NIST GOVERN-6, MANAGE-3 | OWASP LLM02, LLM08 | ATLAS AML.M0018 | MIT 1.2. Privacy violations

### GR-02.5: Implement retention schedules, right-to-erasure purge routines, and versioned snapshots for datasets and embeddings.
- **Applicability**: systems persisting user or enterprise data
- **Verification test**: Verify existence of TTL/retention enforcement or document deletion routines in storage modules.
- **Implementation hints**: Provide deterministic delete-by-source-ID and TTL expiration jobs across document stores and caches.
- **Standards**: EU AI Act Art 10 | NIST GOVERN-1, MANAGE-4 | OWASP LLM02 | MIT 1.2. Privacy violations

## GR-03 — Transparency & disclosure (4)

### GR-03.1: Disclose clearly to users and downstream consumers when they are interacting with an AI system or reading AI-generated content.
- **Applicability**: user-facing AI and content generation systems
- **Verification test**: Verify response envelopes or UI rendering templates include an explicit AI-generated disclosure indicator.
- **Implementation hints**: Attach explicit AI disclosure headers, metadata flags, or UI notices to all generated responses.
- **Standards**: EU AI Act Art 13, 50 | NIST GOVERN-4, MAP-1, MEASURE-2 | OWASP LLM09 | MIT 4.3. Lack of transparency or interpretability; 3.1. Pollution of information ecosystem and loss of shared reality

### GR-03.2: Ground generated claims in verifiable source citations and cross-check citations against the underlying corpus or files.
- **Applicability**: RAG, coding, compliance, and analytical AI systems
- **Verification test**: Verify post-generation citation validation logic that checks cited sources exist and demotes or flags unverified claims.
- **Implementation hints**: Require structured citations on model outputs and deterministically verify file/document existence and line/span bounds.
- **Standards**: EU AI Act Art 13 | NIST MEASURE-2, MANAGE-2 | OWASP LLM09 | MIT 3.2. False or misleading information; 4.3. Lack of transparency or interpretability

### GR-03.3: Provide model/system cards documenting model architecture, version, known limitations, and evaluation benchmarks.
- **Applicability**: any AI system
- **Verification test**: Verify presence of structured system metadata, version identifiers, and documented limitations.
- **Implementation hints**: Ship structured system/model metadata alongside code and expose version/capability descriptors via CLI or API.
- **Standards**: EU AI Act Art 11, 13, 53 | NIST GOVERN-1, MAP-1, MEASURE-4 | MIT 4.3. Lack of transparency or interpretability

### GR-03.4: Expose interpretable reasoning traces, confidence indicators, or uncertainty warnings on automated assessments.
- **Applicability**: decision-support and analytical AI systems
- **Verification test**: Verify output schemas require explicit reasoning and support inconclusive/uncertainty states rather than forced binary verdicts.
- **Implementation hints**: Include structured reasoning fields, uncertainty/inconclusive states, and audit trails in assessment outputs.
- **Standards**: EU AI Act Art 13, 14 | NIST MEASURE-2, MANAGE-1 | OWASP LLM09 | MIT 4.3. Lack of transparency or interpretability; 5.1. Overreliance and unsafe use

## GR-04 — Human oversight (4)

### GR-04.1: Require human-in-the-loop (HITL) approval before executing high-impact, irreversible, or state-mutating actions.
- **Applicability**: agentic and tool-using AI systems
- **Verification test**: Verify that state-mutating or high-risk actions check for explicit user/operator approval before execution.
- **Implementation hints**: Gate destructive, financial, or external write tool calls behind an explicit confirmation token or approval queue.
- **Standards**: EU AI Act Art 14 | NIST GOVERN-3, MAP-3, MANAGE-2 | OWASP LLM06 | ATLAS AML.M0018 | MIT 5.2. Loss of human agency and autonomy; 7.2. AI possessing dangerous capabilities

### GR-04.2: Provide an immediate stop, cancellation, or kill-switch mechanism to halt autonomous loops and background tasks.
- **Applicability**: autonomous and multi-step AI pipelines
- **Verification test**: Verify bounded loop counters (e.g., max revisions/steps) and clean abort handling in execution drivers.
- **Implementation hints**: Enforce hard iteration caps, timeouts, and signal/cancellation checks inside agent and audit loops.
- **Standards**: EU AI Act Art 14 | NIST GOVERN-3, MANAGE-3 | OWASP LLM06, LLM10 | MIT 7.4. Lack of capability to control AI; 5.2. Loss of human agency and autonomy

### GR-04.3: Support human override, correction, and escalation queues for contested or ambiguous model verdicts.
- **Applicability**: decision-support and auditing AI systems
- **Verification test**: Verify that unconverged or contested items are collected into an explicit open_questions or escalation structure.
- **Implementation hints**: Surface unresolved disputes as explicit open_questions for human review rather than silently masking disagreements.
- **Standards**: EU AI Act Art 14 | NIST GOVERN-3, MANAGE-1, MANAGE-4 | OWASP LLM09 | MIT 5.1. Overreliance and unsafe use

### GR-04.4: Prevent automation bias by presenting counter-evidence, adversarial critiques, and verification status alongside conclusions.
- **Applicability**: analytical, compliance, and recommendation AI systems
- **Verification test**: Verify presence of adversarial review/critique stages and explicit demotion markers in user-facing reports.
- **Implementation hints**: Run an independent adversarial critique pass and highlight demoted or weakly supported claims in reports.
- **Standards**: EU AI Act Art 14 | NIST MAP-3, MEASURE-2 | OWASP LLM09 | MIT 5.1. Overreliance and unsafe use

## GR-05 — Robustness & accuracy (5)

### GR-05.1: Validate all LLM outputs against strict structural and type schemas before downstream consumption or persistence.
- **Applicability**: all structured-output LLM and agentic systems
- **Verification test**: Verify strict schema validation on LLM responses and final report artifacts prior to writing or acting on them.
- **Implementation hints**: Parse and validate every LLM response against JSON Schema or Pydantic models with extra='forbid'; reject malformed payloads.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-2 | OWASP LLM05, LLM09 | ATLAS AML.M0015 | MIT 7.3. Lack of capability or robustness

### GR-05.2: Detect and mitigate hallucinations by cross-verifying model assertions against deterministic ground-truth sources.
- **Applicability**: all generative AI systems making factual or code assertions
- **Verification test**: Verify deterministic cross-verification of model citations/facts and automatic demotion + logging on failure.
- **Implementation hints**: Resolve file paths, line numbers, or database keys cited by the LLM and automatically demote unverified claims.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-2 | OWASP LLM09 | MIT 3.2. False or misleading information; 7.3. Lack of capability or robustness

### GR-05.3: Handle malformed inputs, transient failures, and partial responses gracefully with deterministic error codes and recovery paths.
- **Applicability**: all AI systems
- **Verification test**: Verify deterministic validation error handling and non-zero exit codes when inputs or responses are missing or invalid.
- **Implementation hints**: Wrap file/JSON parsing and phase transitions in explicit error handlers that emit actionable error messages and non-zero exit codes.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM05, LLM10 | MIT 7.3. Lack of capability or robustness

### GR-05.4: Maintain an automated regression and unit test suite covering pipeline invariants, edge cases, and failure modes.
- **Applicability**: all AI systems
- **Verification test**: Verify existence of automated tests covering schema validation, citation verification, and pipeline phase transitions.
- **Implementation hints**: Ship automated pytest tests verifying happy paths, invalid inputs, hallucination demotions, and schema drift.
- **Standards**: EU AI Act Art 15, 43 | NIST MEASURE-1, MEASURE-2, MEASURE-4 | MIT 7.3. Lack of capability or robustness

### GR-05.5: Enforce multi-agent or adversarial cross-checking to reduce single-pass model blind spots and drift.
- **Applicability**: high-assurance analytical and agentic systems
- **Verification test**: Verify implementation of adversarial audit phases that critique and apply deltas to primary LLM outputs.
- **Implementation hints**: Pair primary assessment phases with bounded adversarial red-team audit phases that can CONFIRM, REVISE, or INVESTIGATE.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-2 | OWASP LLM09 | ATLAS AML.M0003 | MIT 7.3. Lack of capability or robustness

## GR-06 — Adversarial security (5)

### GR-06.1: Defend against direct and indirect prompt injection by separating untrusted data from system instructions and constraining model outputs.
- **Applicability**: all LLM and agentic systems processing untrusted inputs
- **Verification test**: Verify that untrusted inputs are structured separately from instructions and responses are strictly validated as data.
- **Implementation hints**: Isolate untrusted repository content into structured data fields, forbid prose execution, and require strict JSON schema adherence.
- **Standards**: EU AI Act Art 15 | NIST MAP-3, MEASURE-2, MANAGE-3 | OWASP LLM01, LLM08 | ATLAS AML.M0015, AML.M0019 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-06.2: Sanitize and validate all model-generated strings, paths, and parameters before passing them to OS, filesystem, shell, or database APIs.
- **Applicability**: all AI systems interacting with filesystems, shells, or APIs
- **Verification test**: Verify path traversal checks (relative_to project_root) and absence of unsanitized shell interpolation.
- **Implementation hints**: Resolve paths against project_root, reject '..' traversal, avoid shell=True, and validate identifiers against strict regexes.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM05, LLM06 | ATLAS AML.M0015, AML.M0018 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-06.3: Enforce resource bounds, input size limits, and loop caps to prevent denial-of-service or unbounded token consumption.
- **Applicability**: all LLM and agentic systems
- **Verification test**: Verify explicit character/file limits on context gathering and hard upper bounds on retry/revision loops.
- **Implementation hints**: Truncate ingested manifest/doc previews (e.g., 6000 chars), cap file walks (e.g., 200 files), and bound audit revisions.
- **Standards**: EU AI Act Art 15 | NIST MANAGE-3 | OWASP LLM10 | ATLAS AML.M0004 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-06.4: Prevent system prompt leakage and sensitive internal context exposure in user-facing or downstream outputs.
- **Applicability**: all LLM systems
- **Verification test**: Verify that external output contracts exclude raw system prompts, credentials, and unrestricted source dumps.
- **Implementation hints**: Emit only validated contract fields in final reports and agent wrappers; strip internal prompts and raw source excerpts.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM02, LLM07 | ATLAS AML.M0002, AML.M0015 | MIT 2.2. AI system security vulnerabilities and attacks; 1.2. Privacy violations

### GR-06.5: Conduct regular adversarial red-teaming against model verdicts and evidence claims under strict read-scope constraints.
- **Applicability**: all high-assurance AI systems
- **Verification test**: Verify adversary instructions and delta application forbid inventing new IDs or expanding scope.
- **Implementation hints**: Run dedicated adversary phases constrained to auditing existing citations without inventing new scope.
- **Standards**: EU AI Act Art 15, 55 | NIST MEASURE-2, MANAGE-2 | OWASP LLM01, LLM09 | ATLAS AML.M0003 | MIT 2.2. AI system security vulnerabilities and attacks

## GR-07 — Privacy & data protection (4)

### GR-07.1: Minimize sensitive and personal data exposure by restricting context collection to necessary manifests and bounded file excerpts.
- **Applicability**: all AI systems accessing user or repository data
- **Verification test**: Verify that context collection skips dotfiles/environments and enforces strict character and file count limits.
- **Implementation hints**: Read only curated manifest filenames with character caps and skip hidden/credential directories during project walks.
- **Standards**: EU AI Act Art 10, 15 | NIST GOVERN-1, MAP-2, MANAGE-3 | OWASP LLM02 | ATLAS AML.M0012 | MIT 1.2. Privacy violations

### GR-07.2: Prevent unauthorized outbound network exfiltration of codebase or user data during inference and pipeline execution.
- **Applicability**: all enterprise and local-first AI tools
- **Verification test**: Verify that runtime pipeline modules make zero network requests and never import or invoke external HTTP/LLM clients.
- **Implementation hints**: Execute assessment pipelines purely locally via disk-queue exchanges without opening outbound network sockets.
- **Standards**: EU AI Act Art 15 | NIST GOVERN-6, MANAGE-3 | OWASP LLM02, LLM06 | ATLAS AML.M0018 | MIT 1.2. Privacy violations; 2.2. AI system security vulnerabilities and attacks

### GR-07.3: Scrub or exclude secrets, API keys, and credentials from logs, artifacts, and model context windows.
- **Applicability**: all AI systems
- **Verification test**: Verify that .env and secret files are excluded from manifest candidate lists and no credentials appear in artifacts.
- **Implementation hints**: Never read .env or credential files into prompts and avoid hardcoding or logging tokens in pipeline state.
- **Standards**: EU AI Act Art 10, 15 | NIST MANAGE-3 | OWASP LLM02 | MIT 1.2. Privacy violations

### GR-07.4: Confine all runtime state, temporary files, and reports to a designated, git-ignorable workspace directory.
- **Applicability**: all local and repository-auditing AI tools
- **Verification test**: Verify that all runtime file writes target <project_root>/.armor/ (or atomic temp files in the same directory).
- **Implementation hints**: Write all run artifacts, queues, logs, and reports exclusively beneath <project_root>/.armor/.
- **Standards**: EU AI Act Art 10, 12 | NIST GOVERN-1, MANAGE-3 | OWASP LLM02 | MIT 1.2. Privacy violations

## GR-08 — Fairness & non-discrimination (4)

### GR-08.1: Evaluate and document affected user populations and potential disparate impacts during system profiling.
- **Applicability**: all AI systems
- **Verification test**: Verify that the triage system_profile schema requires explicit user_population profiling.
- **Implementation hints**: Require user_population and data_sensitivity fields in the Phase 2 system_profile schema.
- **Standards**: EU AI Act Art 10, 13, 27 | NIST MAP-1, MAP-2, MEASURE-2 | MIT 1.1. Unfair discrimination and misrepresentation

### GR-08.2: Apply consistent, deterministic scoring weights and evaluation criteria across all assessed components or subjects.
- **Applicability**: scoring, ranking, and auditing AI systems
- **Verification test**: Verify that coverage and suggestion rankings are computed deterministically from a fixed weight map.
- **Implementation hints**: Compute posture scores using a fixed, transparent weight table (VERDICT_WEIGHT) and deterministic sorting.
- **Standards**: EU AI Act Art 10, 15 | NIST MEASURE-1, MEASURE-2 | MIT 1.1. Unfair discrimination and misrepresentation

### GR-08.3: Exclude inapplicable criteria from scoring denominators so specialized systems are not unfairly penalized.
- **Applicability**: evaluation and compliance scoring systems
- **Verification test**: Verify that 'n/a' verdicts are excluded from the coverage denominator in report rollup calculations.
- **Implementation hints**: Exclude rows with verdict == 'n/a' from in_scope_count and max_possible_points when computing coverage percentages.
- **Standards**: EU AI Act Art 9, 15 | NIST MEASURE-1, MEASURE-2 | MIT 1.1. Unfair discrimination and misrepresentation

### GR-08.4: Audit subjective classifications through an independent review pass to detect biased or unsubstantiated scoping decisions.
- **Applicability**: classification and triage AI systems
- **Verification test**: Verify that triage applicability decisions are audited by triage-audit before conformance scoring proceeds.
- **Implementation hints**: Subject all Phase 2 applicability tags (applies/partial_scope/n_a) to the Phase 3 triage-audit red-team loop.
- **Standards**: EU AI Act Art 10, 14 | NIST MEASURE-2, MANAGE-2 | MIT 1.1. Unfair discrimination and misrepresentation

## GR-09 — Content safety (4)

### GR-09.1: Enforce output content quality and forbid vague, boilerplate, or non-actionable safety/remediation advice.
- **Applicability**: advisory, code-review, and remediation-generating AI systems
- **Verification test**: Verify that conformance instructions mandate codebase-specific, action-leading remediations and list banned phrases.
- **Implementation hints**: Instruct the model with explicit remediation quality rules and a list of banned boilerplate phrases.
- **Standards**: EU AI Act Art 13, 15 | NIST MEASURE-2, MANAGE-2 | OWASP LLM05, LLM09 | MIT 5.1. Overreliance and unsafe use

### GR-09.2: Escape and sanitize untrusted or model-generated strings before rendering them into Markdown tables or reports.
- **Applicability**: systems generating Markdown or HTML reports from LLM outputs
- **Verification test**: Verify Markdown rendering functions escape '|' and newlines in table cells.
- **Implementation hints**: Escape pipe characters ('|') and normalize newlines when rendering model reasoning and actions into Markdown tables.
- **Standards**: EU AI Act Art 15 | NIST MANAGE-3 | OWASP LLM05 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-09.3: Provide safe, deterministic fallback guidance whenever model-generated remediation text is missing or inconclusive.
- **Applicability**: advisory and reporting AI systems
- **Verification test**: Verify report suggestion builder provides explicit fallback action strings when remediation is empty.
- **Implementation hints**: Supply deterministic fallback action strings for inconclusive or empty-remediation rows during report generation.
- **Standards**: EU AI Act Art 13, 15 | NIST MANAGE-2, MANAGE-3 | OWASP LLM09 | MIT 5.1. Overreliance and unsafe use

### GR-09.4: Constrain agent wrapper summaries to concise, bounded notes free of raw source code, citations, or prompt instructions.
- **Applicability**: agent wrappers and automated CI/CD gates
- **Verification test**: Verify agent wrapper specification enforces bounded notes (<200 chars) with no source excerpts or prompts.
- **Implementation hints**: Enforce a strict <200 character single-line summary note in the agent YAML verdict contract.
- **Standards**: EU AI Act Art 13, 15 | NIST GOVERN-4, MANAGE-3 | OWASP LLM02, LLM05 | MIT 1.2. Privacy violations

## GR-10 — Logging, monitoring & incident response (5)

### GR-10.1: Maintain an immutable, timestamped run directory recording the input/output artifact of every pipeline phase.
- **Applicability**: all production and auditing AI pipelines
- **Verification test**: Verify that new_run creates UTC-timestamped run directories and each phase persists its numbered artifact.
- **Implementation hints**: Create UTC-timestamped directories under .armor/runs/<iso>/ and persist numbered JSON/MD artifacts for Phases 1–6.
- **Standards**: EU AI Act Art 12, 19 | NIST GOVERN-1, MEASURE-2, MANAGE-4 | ATLAS AML.M0016 | MIT 4.3. Lack of transparency or interpretability

### GR-10.2: Log every detected model hallucination or rejected citation to an append-only structured incident log.
- **Applicability**: all citation-backed generative AI systems
- **Verification test**: Verify that rejected citations in conform and conform-audit are appended to hallucination_log.jsonl.
- **Implementation hints**: Append JSONL records with UTC timestamp, phase, sid, citation, and rejection reason to .armor/hallucination_log.jsonl.
- **Standards**: EU AI Act Art 12, 73 | NIST MEASURE-2, MANAGE-4 | OWASP LLM09 | ATLAS AML.M0016 | MIT 3.2. False or misleading information; 4.3. Lack of transparency or interpretability

### GR-10.3: Record full multi-round adversarial audit trails capturing per-round verdict counts, critiques, and before/after row diffs.
- **Applicability**: systems with multi-step or adversarial review loops
- **Verification test**: Verify that audit phases record per-round verdict_counts and before/after diffs in audit_trail.
- **Implementation hints**: Persist audit_trail arrays in 03_triage_audit.json and 05_conformance_audit.json with before/after revision records.
- **Standards**: EU AI Act Art 12 | NIST MEASURE-2, MANAGE-4 | MIT 4.3. Lack of transparency or interpretability

### GR-10.4: Enforce mandatory skill-usage telemetry tracking across parent skills and delegated sub-agents.
- **Applicability**: marketplace skills and multi-agent plugins
- **Verification test**: Verify that SKILL.md defines a mandatory telemetry gate before tool calls, sub-agents, and final responses.
- **Implementation hints**: Gate skill execution on emitting start and end telemetry events with propagated PARENT_TRACKERID.
- **Standards**: EU AI Act Art 12 | NIST GOVERN-1, MANAGE-4 | ATLAS AML.M0016 | MIT 4.3. Lack of transparency or interpretability

### GR-10.5: Expose a deterministic CLI status inspection command reporting live progress across all pipeline phases.
- **Applicability**: multi-phase AI pipelines
- **Verification test**: Verify that `pipeline <project> --status` reports the current run root and the state of every phase.
- **Implementation hints**: Support `--status` on the pipeline CLI to inspect whether each phase is pending, awaiting-llm, response-ready, or done.
- **Standards**: EU AI Act Art 12, 14 | NIST GOVERN-3, MANAGE-4 | MIT 4.3. Lack of transparency or interpretability

## GR-11 — Supply-chain & component integrity (4)

### GR-11.1: Version and content-address all external standards, catalogs, and reference artifacts using cryptographic SHA256 hashes.
- **Applicability**: systems depending on external catalogs, standards, or model artifacts
- **Verification test**: Verify content-addressed SHA256 hashing and manifest/history tracking in ai_standards_versioning.py.
- **Implementation hints**: Commit catalog and standard updates via content-addressed `<date>__<sha8>` directories, `latest.json`, and `history.jsonl`.
- **Standards**: EU AI Act Art 15, 53 | NIST GOVERN-6, MAP-2, MANAGE-3 | OWASP LLM03 | ATLAS AML.M0007, AML.M0014 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-11.2: Compute deterministic source fingerprints of the target codebase to detect concurrent edits or environment drift.
- **Applicability**: codebase analysis and auditing tools
- **Verification test**: Verify that project_fingerprint() produces a deterministic SHA256 prefix that changes whenever a source file is edited.
- **Implementation hints**: Hash sorted relative paths and modification timestamps across tracked source extensions via project_fingerprint().
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM03 | ATLAS AML.M0014 | MIT 7.3. Lack of capability or robustness

### GR-11.3: Minimize third-party runtime dependencies and isolate network-fetching utilities from the core execution runtime.
- **Applicability**: all software and AI plugins
- **Verification test**: Verify that core `armor/` runtime modules import only stdlib and pydantic.
- **Implementation hints**: Require only pydantic at runtime (stdlib for everything else); isolate requests/pyyaml to offline catalog refresh scripts.
- **Standards**: EU AI Act Art 15 | NIST GOVERN-6, MANAGE-3 | OWASP LLM03 | ATLAS AML.M0014 | MIT 2.2. AI system security vulnerabilities and attacks

### GR-11.4: Keep packaged JSON Schemas byte-synchronized with runtime data models and provide automated drift verification.
- **Applicability**: all schema-driven AI pipelines
- **Verification test**: Verify `--write-schema` and test assertions that `posture_report.schema.json` byte-equals `PostureReport.model_json_schema()`.
- **Implementation hints**: Ship `posture_report.schema.json` generated from `PostureReport.model_json_schema()` and enforce byte equality in tests.
- **Standards**: EU AI Act Art 15 | NIST MEASURE-2, MANAGE-3 | OWASP LLM03, LLM05 | MIT 7.3. Lack of capability or robustness

## GR-12 — Agentic autonomy & action safety (4)

### GR-12.1: Enforce strict phase ordering so downstream agent actions cannot execute before prerequisite artifacts are verified.
- **Applicability**: multi-step agentic workflows
- **Verification test**: Verify that calling later phases before earlier phases raises SystemExit via `require_phase_done`.
- **Implementation hints**: Guard each phase entry point with `require_phase_done(run, prerequisite_phase)` and abort with exact unblock instructions.
- **Standards**: EU AI Act Art 14, 15 | NIST GOVERN-3, MANAGE-3 | OWASP LLM06 | ATLAS AML.M0018 | MIT 7.4. Lack of capability to control AI; 5.2. Loss of human agency and autonomy

### GR-12.2: Prevent recursive self-auditing or runaway self-targeting in autonomous agent wrappers.
- **Applicability**: autonomous auditing and delegation agents
- **Verification test**: Verify that the agent wrapper specification mandates a self-targeting refusal returning `verdict: fail` and zeroed counts.
- **Implementation hints**: Enforce a mandatory self-targeting guard in `armor-agent` that refuses paths resolving to `armor-agent-plugin`.
- **Standards**: EU AI Act Art 14, 15 | NIST GOVERN-3, MANAGE-3 | OWASP LLM06, LLM10 | ATLAS AML.M0018 | MIT 7.4. Lack of capability to control AI; 7.1. AI pursuing its own goals in conflict with human goals or values

### GR-12.3: Protect concurrent file mutations with cross-platform exclusive file locks and atomic write-and-replace primitives.
- **Applicability**: concurrent or multi-agent local workflows
- **Verification test**: Verify cross-platform locking (`msvcrt` / `fcntl` + `threading.Lock`) and atomic `os.replace` writes in `file_lock.py`.
- **Implementation hints**: Provide `exclusive_lock`, `locked_write` (mkstemp + os.replace), and `locked_append` in `file_lock.py`.
- **Standards**: EU AI Act Art 15 | NIST MANAGE-3 | OWASP LLM06 | MIT 7.3. Lack of capability or robustness

### GR-12.4: Constrain red-team adversary agents to read-only verification of cited evidence without expanding scope or inventing findings.
- **Applicability**: multi-agent and adversarial AI systems
- **Verification test**: Verify `apply_deltas` ignores unknown SIDs (recording them in `unknown_sids`) and preserves original row ordering.
- **Implementation hints**: Instruct adversary phases not to read files beyond cited `file:line` spans and ignore any unknown SIDs in apply_deltas.
- **Standards**: EU AI Act Art 14, 15 | NIST GOVERN-3, MEASURE-2, MANAGE-3 | OWASP LLM06 | ATLAS AML.M0018 | MIT 7.4. Lack of capability to control AI
