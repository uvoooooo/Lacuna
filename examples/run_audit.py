"""
Minimal example: run the Narrative Audit Pipeline on a piece of text.

    uv run python examples/run_audit.py
"""

from narrative_audit import audit

TEXT = (
    "我在喜多多集团勤勤恳恳工作了六年，带头研发了核心系统。"
    "上周五，部门经理突然叫我去办公室，跟我说我被开除了，连补偿金都没提。"
    "他踢走老员工，霸占我的期权，这是赤裸裸的压榨！"
)


def main() -> None:
    state = audit(TEXT, context="社媒发帖")
    print(f"总体置信度: {state.overall_confidence:.2f}  (LLM={state.metadata['llm_enabled']})")
    print()
    print(state.report_markdown)


if __name__ == "__main__":
    main()
