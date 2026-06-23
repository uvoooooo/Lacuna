"""Base agent contract."""

from __future__ import annotations

from ..llm import LLMClient
from ..state import AuditState, _Timer


class BaseAgent:
    """
    Every agent reads from and writes to the shared `AuditState`.

    Subclasses implement `_run`. The public `run` wraps it with timing and
    logging so the orchestrator stays simple.
    """

    name: str = "base"
    description: str = ""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def run(self, state: AuditState) -> AuditState:
        timer = _Timer()
        message = self._run(state)
        state.add_log(self.name, message or "done", timer.ms())
        return state

    def _run(self, state: AuditState) -> str:
        """Mutate `state` in place. Return a short status message."""
        raise NotImplementedError

    @property
    def uses_llm(self) -> bool:
        return self.llm is not None and self.llm.available
