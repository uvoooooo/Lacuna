"""
Agent 5 — Final Judge / Report Agent (置信度 + 报告).

Computes a per-claim confidence from labels, checkability and evidence, rolls it
up into an overall confidence, and renders a human-readable markdown report:
what is reliable, what is only inference, what is unsaid, what to ask next.

This also contains the lightweight confidence calibration that the MVP folds
into the report agent (a dedicated Calibration Agent comes later).
"""

from __future__ import annotations

from ..state import AuditState, Checkability, Claim, EvidenceStance, Label
from .base import BaseAgent

_STATUS_ZH = {
    EvidenceStance.SUPPORT: "证据支持",
    EvidenceStance.REFUTE: "证据反驳",
    EvidenceStance.PARTIAL: "部分支持",
    EvidenceStance.IRRELEVANT: "证据无关",
    EvidenceStance.NOT_ENOUGH: "证据不足/待核实",
}


class ReportAgent(BaseAgent):
    name = "report"
    description = "计算置信度并生成可读报告"

    def _run(self, state: AuditState) -> str:
        for claim in state.claims:
            claim.confidence = self._score(claim)

        state.overall_confidence = self._rollup(state.claims)
        state.report_markdown = self._render(state)
        return f"总体置信度 {state.overall_confidence:.2f}，已生成报告"

    @staticmethod
    def _score(claim: Claim) -> float:
        # Base prior by checkability.
        base = {
            Checkability.HIGH: 0.6,
            Checkability.MEDIUM: 0.5,
            Checkability.LOW: 0.4,
            Checkability.NONE: 0.35,
        }.get(claim.checkability, 0.5)

        # Evidence moves it.
        if claim.evidence:
            avg_cred = sum(e.credibility for e in claim.evidence) / len(claim.evidence)
            avg_fresh = sum(e.freshness for e in claim.evidence) / len(claim.evidence)
            quality = 0.5 * avg_cred + 0.5 * avg_fresh
            delta = {
                EvidenceStance.SUPPORT: 0.30,
                EvidenceStance.PARTIAL: 0.12,
                EvidenceStance.REFUTE: -0.45,
                EvidenceStance.IRRELEVANT: -0.02,
                EvidenceStance.NOT_ENOUGH: -0.05,
            }.get(claim.evidence_status, 0.0)
            base += delta * (0.5 + 0.5 * quality)

        # Pure emotion/opinion is inherently low-confidence as a "fact".
        if set(claim.labels) & {Label.EMOTIONAL, Label.OPINION} and Label.FACT not in claim.labels:
            base = min(base, 0.4)

        # Lots of missing context lowers confidence.
        base -= min(0.15, 0.04 * len(claim.missing_context))

        return max(0.0, min(1.0, base))

    @staticmethod
    def _rollup(claims: list[Claim]) -> float:
        checkable = [c for c in claims if c.is_checkable]
        pool = checkable or claims
        if not pool:
            return 0.0
        return sum(c.confidence for c in pool) / len(pool)

    def _render(self, state: AuditState) -> str:
        lines: list[str] = []
        lines.append("# 表述审阅报告 (Narrative Audit)")
        lines.append("")
        lines.append(f"**总体置信度：{state.overall_confidence:.2f}**")
        lines.append("")
        lines.append(f"> 输入语境：{state.context or '未提供'}")
        lines.append("")

        reliable = [c for c in state.claims if c.evidence_status == EvidenceStance.SUPPORT]
        refuted = [c for c in state.claims if c.evidence_status == EvidenceStance.REFUTE]
        inferences = [
            c
            for c in state.claims
            if set(c.labels) & {Label.INFERENCE, Label.OPINION, Label.EMOTIONAL}
            and Label.FACT not in c.labels
        ]
        all_missing = []
        for c in state.claims:
            all_missing.extend(c.missing_context)
        all_questions = []
        for c in state.claims:
            all_questions.extend(c.suggested_questions)

        lines.append("## 一句话结论")
        lines.append(self._headline(reliable, refuted, inferences))
        lines.append("")

        lines.append("## 逐条拆解")
        for c in state.claims:
            label_zh = "、".join(Label.ZH.get(lbl, lbl) for lbl in c.labels) or "未标注"
            status_zh = _STATUS_ZH.get(c.evidence_status, c.evidence_status)
            lines.append(
                f"- **{c.text}**  \n"
                f"  类型：{label_zh} ｜ 可核查：{c.checkability} ｜ "
                f"{status_zh} ｜ 置信度：`{c.confidence:.2f}`"
            )
            if c.missing_context:
                lines.append(f"  - 缺失：{'、'.join(c.missing_context)}")
        lines.append("")

        if inferences:
            lines.append("## 这些只是推断/主观，不是事实")
            for c in inferences:
                lines.append(f"- {c.text}")
            lines.append("")

        if all_missing:
            lines.append("## 没说的部分（结构性留白）")
            for item in list(dict.fromkeys(all_missing)):
                lines.append(f"- {item}")
            lines.append("")

        if all_questions:
            lines.append("## 应该追问什么")
            for q in list(dict.fromkeys(all_questions)):
                lines.append(f"- {q}")
            lines.append("")

        lines.append("---")
        lines.append("*本报告不判断谁对谁错，只分析：说了什么、暗示了什么、没说什么、证据够不够。*")
        return "\n".join(lines)

    @staticmethod
    def _headline(reliable, refuted, inferences) -> str:
        if refuted:
            return "存在被外部证据反驳的陈述，叙事可信度需重点存疑。"
        if not reliable and inferences:
            return "目前缺乏可核查证据，叙事主要由主观评价与推断构成，建议补充材料后再判断。"
        if reliable:
            return "部分事实可被证据支持，但仍存在结构性留白，需结合追问补全。"
        return "证据不足，暂不能给出强结论，建议优先核查可验证的事实陈述。"
