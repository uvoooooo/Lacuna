"""
Lightweight declarative ontology (轻量本体).

Each event type declares the roles that logically belong to it:

- `required` roles must exist for the event to have happened at all
  (a dismissal必然有开除方和在先的劳动关系). If the graph lacks them, that
  absence is itself a signal.
- `expected` roles usually accompany a full account (compensation handling,
  prior warnings). Their absence is worth asking about.

The catalogue itself is data, not code: the built-in ontology lives in
`data/ontology.toml` (packaged with the library) and domain-specific ones can
be loaded from any TOML file via `load_ontology()` — see the schema comment at
the top of that file.

Event typing is done by the LLM when available (the reasoner shows it this
catalogue); the keyword lists are only the offline fallback. Gap checking
against the declared roles is fully deterministic — no model judgement.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from .graph import GapImportance

_IMPORTANCE_VALUES = (GapImportance.REQUIRED, GapImportance.EXPECTED)


@dataclass(frozen=True)
class RoleSpec:
    name: str
    label_zh: str
    importance: str  # GapImportance.REQUIRED | EXPECTED
    question: str  # follow-up question when the role is missing


@dataclass(frozen=True)
class EventType:
    name: str
    label_zh: str
    keywords: tuple[str, ...]  # offline fallback typing only
    roles: tuple[RoleSpec, ...]

    def required_roles(self) -> tuple[RoleSpec, ...]:
        return tuple(r for r in self.roles if r.importance == GapImportance.REQUIRED)


class OntologyError(ValueError):
    """Raised when an ontology TOML file does not match the expected schema."""


def _parse_role(raw: Any, where: str) -> RoleSpec:
    if not isinstance(raw, dict):
        raise OntologyError(f"{where}: each role must be a table, got {type(raw).__name__}")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise OntologyError(f"{where}: role is missing a 'name'")
    importance = str(raw.get("importance", "")).strip()
    if importance not in _IMPORTANCE_VALUES:
        raise OntologyError(
            f"{where}: role '{name}' importance must be one of {_IMPORTANCE_VALUES}, "
            f"got {importance!r}"
        )
    return RoleSpec(
        name=name,
        label_zh=str(raw.get("label_zh", name)).strip(),
        importance=importance,
        question=str(raw.get("question", "")).strip(),
    )


def _parse_event_type(raw: Any) -> EventType:
    if not isinstance(raw, dict):
        raise OntologyError(f"each [[event_types]] must be a table, got {type(raw).__name__}")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise OntologyError("an [[event_types]] entry is missing a 'name'")
    keywords = raw.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise OntologyError(f"event type '{name}': 'keywords' must be a list of strings")
    roles = raw.get("roles", [])
    if not isinstance(roles, list):
        raise OntologyError(f"event type '{name}': 'roles' must be an array of tables")
    return EventType(
        name=name,
        label_zh=str(raw.get("label_zh", name)).strip(),
        keywords=tuple(keywords),
        roles=tuple(_parse_role(r, f"event type '{name}'") for r in roles),
    )


def parse_ontology(data: dict[str, Any]) -> dict[str, EventType]:
    """Build an ontology from parsed TOML data. Raises `OntologyError` on bad schema."""
    raw_events = data.get("event_types", [])
    if not isinstance(raw_events, list) or not raw_events:
        raise OntologyError("ontology must declare at least one [[event_types]] entry")
    ontology: dict[str, EventType] = {}
    for raw in raw_events:
        et = _parse_event_type(raw)
        if et.name in ontology:
            raise OntologyError(f"duplicate event type '{et.name}'")
        ontology[et.name] = et
    return ontology


def load_ontology(path: str | Path) -> dict[str, EventType]:
    """Load an ontology from a TOML file (see data/ontology.toml for the schema)."""
    with Path(path).open("rb") as fh:
        return parse_ontology(tomllib.load(fh))


def _load_builtin() -> dict[str, Any]:
    source = resources.files("narrative_audit").joinpath("data/ontology.toml")
    return tomllib.loads(source.read_text(encoding="utf-8"))


_BUILTIN = _load_builtin()

# 任何事件都默认预期的通用要素。
GENERIC_ROLES: tuple[RoleSpec, ...] = tuple(
    _parse_role(r, "[[generic_roles]]") for r in _BUILTIN.get("generic_roles", [])
)

DEFAULT_ONTOLOGY: dict[str, EventType] = parse_ontology(_BUILTIN)


def match_event_type(text: str, ontology: dict[str, EventType] | None = None) -> EventType | None:
    """Keyword-based fallback typing for offline runs."""
    catalogue = ontology or DEFAULT_ONTOLOGY
    for event_type in catalogue.values():
        if any(kw in text for kw in event_type.keywords):
            return event_type
    return None


def catalogue_for_prompt(ontology: dict[str, EventType] | None = None) -> str:
    """Render the ontology as a compact catalogue for LLM prompts."""
    catalogue = ontology or DEFAULT_ONTOLOGY
    lines: list[str] = []
    for et in catalogue.values():
        roles = ", ".join(f"{r.name}({r.label_zh},{r.importance})" for r in et.roles)
        lines.append(f"- {et.name} ({et.label_zh}): roles = [{roles}]")
    return "\n".join(lines)
