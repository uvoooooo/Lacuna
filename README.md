# Lacuna · Narrative Audit Pipeline

**English** | [中文](README.zh-CN.md)

> lacuna /ləˈkjuːnə/ n. a gap, a missing part: what a story should have told you, but didn't.

Lacuna turns a one-sided narrative (a social media post, a complaint, a public statement, an exposé) into a knowledge graph, then **audits the graph itself**. It does not judge who is right or wrong.

## The problem it solves

The weakness of a persuasive narrative is usually not in what it says, but in what it leaves out. "I worked hard for six years, then last Friday I was suddenly fired, without any severance." Sounds complete. But what reason was given? Was there any performance record before that? Did the person appeal? These elements **must exist** for the event to have happened at all, yet none of them appear, and that systematic absence is itself a signal.

An experienced reviewer asks these questions by instinct, but human review is slow, expensive and inconsistent. Lacuna turns "listening to what has not been said" into a deterministic pipeline:

- **What was said**: entities, events and relations extracted from the text (marked `stated`);
- **What was implied**: nodes the narrative logically entails but never states, completed by ontology reasoning (marked `inferred`);
- **What contradicts**: timeline conflicts, mutually exclusive relations, inconsistent attributes found on the graph;
- **What is missing**: elements the ontology requires but the graph lacks, each with the follow-up question worth asking.

## Design principles (what it does not do)

- **No true/false verdicts.** The output is structured findings, a list of follow-up questions and a confidence score. Judgment stays with the human.
- **Deterministic verdicts; LLM only where semantics genuinely require it.** Gap detection checks the graph against a declared ontology, so it is reproducible and explainable. The LLM handles what needs real language understanding (extraction, labeling, entity resolution, event typing), and every LLM step has an offline fallback or an explicit error.
- **Stated and inferred are never mixed.** The two are marked separately from the data model all the way to the report.
- **The ontology is data, not code.** Event types and their role checklists live in a TOML file; switching domains (legal, insurance, customer service) means switching a config file.

Where it fits: credibility assistance for content platforms, complaint triage for customer service and insurance, narrative checking for due diligence and newsrooms. Any workflow that needs a fast answer to "where does this story not hold up to questioning".

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and an [OpenRouter](https://openrouter.ai) API key (the Label stage needs an LLM; the other stages fall back to deterministic logic without a key).

```bash
uv sync --extra dev                          # 1. install dependencies
cp .env.example .env                         # 2. fill in OPENROUTER_API_KEY
make run                                     # 3. run the built-in example
```

### Command line

```bash
# Audit a piece of text, print a Markdown report
uv run python -m narrative_audit "上周五我被开除了，连补偿都没有。"

# Provide the input context to help labeling
uv run python -m narrative_audit --context "social media post" "..."

# Full JSON state (claims, graph, conflicts, gaps, evidence, logs)
uv run python -m narrative_audit --json --demo

# Graph visualization: solid = stated, dashed = inferred, ghost nodes = gaps
uv run python -m narrative_audit --mermaid --demo    # paste into mermaid.live
uv run python -m narrative_audit --dot --demo        # pipe to graphviz: ... | dot -Tsvg
```

### Python API

```python
from narrative_audit import audit

state = audit("我带头研发了核心系统……上周五突然被开除……", context="社媒发帖")

print(state.report_markdown)              # combined report (both tracks)
print(state.overall_confidence)           # overall confidence 0..1

for gap in state.gaps:                    # element gaps: the core output
    print(gap.role_zh, gap.importance, gap.suggested_question)
for conflict in state.conflicts:          # contradictions on the graph
    print(conflict.description)
for node in state.graph.nodes:            # graph nodes (stated / inferred marked apart)
    print(node.status, node.label, node.aliases)

from narrative_audit import to_mermaid    # visualization (or to_dot)
print(to_mermaid(state.graph, gaps=state.gaps))
```

### Plugging in real search

The evidence stage is offline by default. `search_fn` is just a `Callable[[str], list[dict]]`, so any backend works:

```python
def my_search(query: str) -> list[dict]:
    return [{"snippet": "...", "source": "...", "url": "..."}, ...]

state = audit(text, search_fn=my_search)
```

### Swapping in a domain ontology

The built-in ontology covers five event types: dismissal, dispute, accusation, harm, agreement. To extend or replace it, copy
[`src/narrative_audit/data/ontology.toml`](src/narrative_audit/data/ontology.toml)
into your own domain catalogue (the schema is documented in the file header), then point the runtime config at it:

```toml
[ontology]
path = "configs/my_domain_ontology.toml"
```

```python
from narrative_audit import pipeline_from_config
state = pipeline_from_config(path="configs/default.toml").run(text)
```

## Pipeline

Everything revolves around one shared `AuditState`: the claim track audits statements one by one, the graph track audits the overall structure, and the report merges both.

```
Input text
  │
  ├─ Claim track
  │   ↓  ClaimSplitter     split the text into atomic statements
  │   ↓  Label             tag each one (fact/opinion/inference/emotional/quote/missing-context) + checkability
  │   ↓  MissingContext    what each claim lacks + what to ask
  │
  ├─ Graph track
  │   ↓  GraphBuilder      narrative -> knowledge graph (entities/events/time/relations, marked stated)
  │   ↓  EntityResolver    coreference: merge nodes that denote the same referent
  │   ↓  OntologyReasoner  align events to ontology types, infer implied nodes (marked inferred)
  │   ↓  ConflictDetector  contradictions on the graph: timeline / exclusive / attribute / semantic
  │   ↓  GapDetector       check required elements against the ontology; key absences = signals
  │
  ↓  Evidence              retrieve evidence for checkable facts only: support/refute/partial/irrelevant/insufficient
  ↓  Report                confidence calibration + merge both tracks into a report
```

Detailed architecture notes and the roadmap live in the local `docs/` directory (not pushed to the remote).

## Repository layout

```
.
├── pyproject.toml            # project metadata + dependencies (uv / hatchling, src layout)
├── uv.lock                   # dependency lockfile
├── .env.example              # environment variable template
├── .pre-commit-config.yaml   # pre-commit hooks (ruff)
├── Makefile                  # common commands
├── README.md / README.zh-CN.md / CHANGELOG.md
├── .github/workflows/        # CI (lint + test)
├── configs/                  # runtime config (model/ontology/evidence/confidence)
├── examples/                 # runnable examples + Gradio demo
├── scripts/                  # ops / one-off scripts
├── src/narrative_audit/      # main package (built-in ontology at data/ontology.toml)
└── tests/                    # unit tests
```

## Development

```bash
make lint      # ruff check
make format    # auto-format + fix
make test      # pytest
make demo      # launch the Gradio demo (needs --extra demo)
```
