"""
Lightweight declarative ontology (轻量本体).

Each event type declares the roles that logically belong to it:

- `required` roles must exist for the event to have happened at all
  (a dismissal必然有开除方和在先的劳动关系). If the graph lacks them, that
  absence is itself a signal.
- `expected` roles usually accompany a full account (compensation handling,
  prior warnings). Their absence is worth asking about.

Event typing is done by the LLM when available (the reasoner shows it this
catalogue); the keyword lists are only the offline fallback. Gap checking
against the declared roles is fully deterministic — no model judgement.
"""

from __future__ import annotations

from dataclasses import dataclass

from .graph import GapImportance


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


# 任何事件都默认预期的通用要素。
GENERIC_ROLES: tuple[RoleSpec, ...] = (
    RoleSpec("cause", "起因", GapImportance.EXPECTED, "这件事是怎么开始的？"),
    RoleSpec("time_place", "时间地点", GapImportance.EXPECTED, "具体发生在什么时候、什么地方？"),
)

DEFAULT_ONTOLOGY: dict[str, EventType] = {
    et.name: et
    for et in (
        EventType(
            name="dismissal",
            label_zh="解雇/开除",
            keywords=("开除", "解雇", "辞退", "劝退", "裁员"),
            roles=(
                RoleSpec("employer", "开除方", GapImportance.REQUIRED, "是谁做出的开除决定？"),
                RoleSpec(
                    "reason", "开除理由", GapImportance.REQUIRED, "对方给出的开除理由是什么？"
                ),
                RoleSpec(
                    "prior_employment",
                    "在先劳动关系",
                    GapImportance.REQUIRED,
                    "劳动关系（合同/入职时间）是怎样的？",
                ),
                RoleSpec(
                    "compensation",
                    "补偿处理",
                    GapImportance.EXPECTED,
                    "补偿/赔偿是如何处理的？",
                ),
                RoleSpec(
                    "prior_warning",
                    "事先警告/绩效记录",
                    GapImportance.EXPECTED,
                    "此前是否有警告、绩效沟通或处分记录？",
                ),
                RoleSpec(
                    "employee_response",
                    "当事人回应/申诉",
                    GapImportance.EXPECTED,
                    "当事人是否申诉、仲裁或有其他回应？",
                ),
            ),
        ),
        EventType(
            name="dispute",
            label_zh="冲突/争执",
            keywords=("冲突", "争执", "吵架", "打架", "对峙", "追逐", "追了"),
            roles=(
                RoleSpec("counterparty", "冲突对方", GapImportance.REQUIRED, "冲突的另一方是谁？"),
                RoleSpec("cause", "冲突起因", GapImportance.REQUIRED, "冲突是怎么开始的？"),
                RoleSpec(
                    "third_party",
                    "第三方记录",
                    GapImportance.EXPECTED,
                    "有没有报警记录、监控或目击者？",
                ),
                RoleSpec(
                    "opposing_view",
                    "对方视角",
                    GapImportance.EXPECTED,
                    "对方会如何描述同一件事？",
                ),
            ),
        ),
        EventType(
            name="accusation",
            label_zh="指控/归责",
            keywords=("霸占", "压榨", "欺骗", "侵占", "诬陷", "克扣", "违法", "侵权"),
            roles=(
                RoleSpec("accused", "被指控方", GapImportance.REQUIRED, "指控针对的是谁？"),
                RoleSpec("evidence", "指控依据", GapImportance.REQUIRED, "指控的具体依据是什么？"),
                RoleSpec(
                    "accused_response",
                    "被指控方回应",
                    GapImportance.EXPECTED,
                    "被指控方对此有何回应？",
                ),
            ),
        ),
        EventType(
            name="harm",
            label_zh="损害/受害",
            keywords=("受伤", "损失", "受害", "赔偿", "医院", "事故"),
            roles=(
                RoleSpec("victim", "受害方", GapImportance.REQUIRED, "受损害的是谁？"),
                RoleSpec(
                    "damage_detail",
                    "损害情况",
                    GapImportance.REQUIRED,
                    "具体损失/伤害是什么？有无凭证？",
                ),
                RoleSpec(
                    "responsible_party",
                    "责任方认定",
                    GapImportance.EXPECTED,
                    "责任是如何认定的？由谁认定？",
                ),
            ),
        ),
        EventType(
            name="agreement",
            label_zh="承诺/协议",
            keywords=("承诺", "协议", "合同", "答应", "约定", "期权"),
            roles=(
                RoleSpec("parties", "协议双方", GapImportance.REQUIRED, "协议/承诺的双方是谁？"),
                RoleSpec(
                    "terms", "约定内容", GapImportance.REQUIRED, "具体约定了什么？有无书面凭证？"
                ),
                RoleSpec(
                    "fulfillment",
                    "履行情况",
                    GapImportance.EXPECTED,
                    "双方各自履行到什么程度？",
                ),
            ),
        ),
    )
}


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
