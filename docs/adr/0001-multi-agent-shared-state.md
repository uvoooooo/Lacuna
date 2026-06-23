# ADR 0001: Multi-agent + shared-state pipeline

- Status: Accepted
- Date: 2026-06-22

## Context

We need to evaluate a piece of narrative text along several orthogonal axes:
claim segmentation, labeling, missing-context detection, evidence retrieval, and
confidence/reporting. A single monolithic LLM prompt that does everything at
once is hard to debug, hard to calibrate, and conflates concerns (e.g. it might
"search" for whether someone is "crazy", which is a subjective label, not a
checkable fact).

## Decision

Implement the pipeline as **multiple small agents that share one mutable
`AuditState` object**, rather than a serial chat that passes text between steps.

- Each agent reads the whole state and writes its own slice.
- Agents are ordered but not isolated: later agents (and future ones) can use
  everything produced so far.
- The Label agent **requires** an LLM (labeling is a semantic judgment): with no
  LLM it raises rather than emit guessed labels. The other agents keep a
  deterministic fallback, but a full run therefore needs an OpenRouter key.
- The Evidence Agent only searches claims labeled as externally checkable;
  emotional/subjective claims are never sent to search.

## Consequences

- Easy to insert new agents (Calibration, Source Credibility, Contradiction,
  Human Review, Domain) by extending the agent list — no orchestration rewrite.
- Each stage is independently testable and observable (`state.log`).
- The shared mutable state requires care: agents must not assume fields exist
  before the producing agent has run; ordering is enforced by the pipeline.
- Heuristic fallbacks are weaker than LLM output (esp. Chinese segmentation);
  acceptable for an offline MVP, revisited in v0.2.
