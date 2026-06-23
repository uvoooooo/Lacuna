"""
Example: enable the Evidence Agent with the offline mock search backend, and
inspect per-claim evidence.

    uv run python examples/run_with_search.py
"""

import json

from narrative_audit import NarrativeAuditPipeline
from narrative_audit.search import make_mock_search

TEXT = (
    "我带头研发了核心系统。公司上周四发生了大规模数据泄漏，"
    "上周五部门经理突然把我开除了，连补偿都没有。"
)


def main() -> None:
    pipeline = NarrativeAuditPipeline(search_fn=make_mock_search())
    state = pipeline.run(TEXT, context="社媒发帖")

    for claim in state.claims:
        print(f"- {claim.text}")
        print(
            f"    类型={claim.labels} 可核查={claim.checkability} "
            f"证据状态={claim.evidence_status} 置信度={claim.confidence:.2f}"
        )
        for ev in claim.evidence:
            print(f"      · [{ev.source}] {ev.snippet[:30]}... -> {ev.stance}")

    print()
    print(json.dumps(state.to_dict()["segments"][0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
