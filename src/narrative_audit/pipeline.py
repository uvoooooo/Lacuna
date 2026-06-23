"""
Narrative Audit Pipeline orchestrator.

Holds the shared `AuditState` and runs the agents over it in order. This is a
shared-state pipeline rather than a serial chat: each agent enriches the same
state object, so later agents (and future ones) can read everything produced so
far.

MVP agents (docs/MVP_items.md):
    1. ClaimSplitterAgent
    2. LabelAgent
    3. MissingContextAgent
    4. EvidenceAgent
    5. ReportAgent

Later additions (Calibration / Source Credibility / Contradiction / Human
Review / Domain agents) can be inserted by passing a custom `agents` list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .agents import (
    BaseAgent,
    ClaimSplitterAgent,
    EvidenceAgent,
    LabelAgent,
    MissingContextAgent,
    ReportAgent,
    SearchFn,
)
from .llm import LLMClient
from .state import AuditState

ProgressFn = Callable[[str, str], None]  # (agent_name, message) -> None


class NarrativeAuditPipeline:
    """Run the multi-agent audit over a piece of text."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        search_fn: SearchFn | None = None,
        agents: Iterable[BaseAgent] | None = None,
    ) -> None:
        self.llm = llm if llm is not None else LLMClient()
        if agents is not None:
            self.agents: list[BaseAgent] = list(agents)
        else:
            self.agents = [
                ClaimSplitterAgent(self.llm),
                LabelAgent(self.llm),
                MissingContextAgent(self.llm),
                EvidenceAgent(self.llm, search_fn=search_fn),
                ReportAgent(self.llm),
            ]

    def run(
        self,
        text: str,
        language: str = "zh-CN",
        context: str = "",
        on_progress: ProgressFn | None = None,
    ) -> AuditState:
        state = AuditState(text=text, language=language, context=context)
        state.metadata["llm_enabled"] = self.llm.available
        state.metadata["pipeline"] = [a.name for a in self.agents]

        for agent in self.agents:
            agent.run(state)
            if on_progress is not None and state.log:
                last = state.log[-1]
                on_progress(last.agent, last.message)

        return state


def audit(
    text: str,
    *,
    context: str = "",
    language: str = "zh-CN",
    search_fn: SearchFn | None = None,
) -> AuditState:
    """Convenience one-shot entrypoint."""
    return NarrativeAuditPipeline(search_fn=search_fn).run(text, language=language, context=context)
