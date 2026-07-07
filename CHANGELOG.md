# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/), versioning per [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Gap verification second look: with an LLM available, candidate gaps are
  batch-checked against the original text and suppressed when the model
  quotes a verbatim span that addresses the element (quotes are verified to
  appear in the text, so gaps cannot be dismissed with invented evidence).
  Suppressions are recorded in `state.metadata["gaps_suppressed"]`. Detection
  itself stays deterministic; offline behavior is unchanged.
- Entity resolution agent: after graph building, an LLM proposes which
  entity nodes co-refer (names/titles/pronouns); merges are applied
  deterministically with validation and a confidence floor, merged labels
  survive as node `aliases`, and the merge log is recorded in
  `state.metadata["entity_merges"]`. Offline fallback merges exact duplicate
  labels only.
- Graph visualization exports: `to_dot()` / `to_mermaid()` render the
  narrative graph with stated vs. inferred styling and gaps as ghost
  "missing" nodes; CLI gains `--dot` and `--mermaid` flags.
- Ontology externalized to TOML: the built-in catalogue now lives in
  `src/narrative_audit/data/ontology.toml` (packaged with the wheel), and
  domain-specific ontologies can be loaded from any TOML file via
  `load_ontology()` or the `[ontology] path` key in the runtime config.
- src-layout repository scaffolding: `pyproject.toml`, `uv.lock`, `Makefile`,
  `.pre-commit-config.yaml`, GitHub Actions CI (lint + test), `configs/`,
  `examples/`, `scripts/`, `tests/`, expanded `docs/`.

### Changed
- LLM client now targets OpenRouter (Chat Completions API).
- All agent prompts rewritten in English.
- Label agent now **requires** an LLM (removed the hardcoded sentiment/keyword
  lexicons and the structural fallback); it raises if no LLM is configured.

## [0.1.0] - 2026-06-22

### Added
- Narrative Audit Pipeline (表述审阅引擎): multi-agent + shared-state framework.
- Five MVP agents: ClaimSplitter, Label, MissingContext, Evidence, Report.
- Shared `AuditState` model with controlled vocabularies.
- LLM client with offline heuristic fallback (runs without an API key).
- Pluggable search backend with an offline mock.
- CLI entrypoint (`python -m narrative_audit`).
