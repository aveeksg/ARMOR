"""ARMOR v6 — LLM-driven AI-guardrail posture pipeline.

6-phase pipeline (load -> triage -> triage-audit -> conform -> conform-audit -> report)
auditing a codebase against a 53-row catalog of AI/agentic standards with citation
cross-verification and adversarial red-team loops. No internal LLM calls: the calling
agent (Copilot/Claude) IS the LLM via a disk-queue exchange.
"""

__version__ = "6.0.0"
