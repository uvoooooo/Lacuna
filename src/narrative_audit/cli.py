"""
Command line entrypoint for the Narrative Audit Pipeline.

Usage:
    python -m narrative_audit "我勤勤恳恳工作六年，上周五突然被开除..."
    echo "..." | python -m narrative_audit
    python -m narrative_audit --json "..."          # print full JSON state
    python -m narrative_audit --demo                 # run the built-in example
"""

from __future__ import annotations

import argparse
import json
import sys

from .pipeline import NarrativeAuditPipeline

_DEMO_TEXT = (
    "我在喜多多集团勤勤恳恳工作了六年，带头研发了核心系统。"
    "上周五，部门经理突然叫我去办公室，跟我说我被开除了，连补偿金都没提。"
    "他踢走老员工，霸占我的期权，这是赤裸裸的压榨！"
)


def _read_input(args: argparse.Namespace) -> str:
    if args.demo:
        return _DEMO_TEXT
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="narrative_audit",
        description="表述审阅引擎：把一段话拆成 说了什么 / 暗示了什么 / 没说什么 / 证据够不够",
    )
    parser.add_argument("text", nargs="?", default="", help="要审阅的文本")
    parser.add_argument("--context", default="", help="输入语境，如 社媒发帖/客服投诉/新闻稿")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON 状态而非报告")
    parser.add_argument("--demo", action="store_true", help="运行内置示例")
    parser.add_argument("--dot", action="store_true", help="输出图谱的 Graphviz DOT 而非报告")
    parser.add_argument("--mermaid", action="store_true", help="输出图谱的 Mermaid 而非报告")
    parser.add_argument(
        "--card",
        nargs="?",
        const="lacuna_card.html",
        default=None,
        metavar="PATH",
        help="生成可分享的 HTML 审计卡片（默认 lacuna_card.html）",
    )
    args = parser.parse_args(argv)

    text = _read_input(args)
    if not text:
        parser.print_help()
        return 1

    pipeline = NarrativeAuditPipeline()

    if not pipeline.llm.available:
        print(
            "错误：未配置 LLM。本流水线的 Label 阶段需要 LLM。\n"
            "请设置 OPENROUTER_API_KEY（参见 .env.example），再重试。",
            file=sys.stderr,
        )
        return 2

    machine_output = args.json or args.dot or args.mermaid or args.card is not None
    if not machine_output:
        print("=" * 60)
        print(f"LLM: on (model={pipeline.llm.model})")
        print("=" * 60)

    def _progress(agent: str, message: str) -> None:
        if not machine_output:
            print(f"  [{agent}] {message}", file=sys.stderr)

    state = pipeline.run(text, context=args.context, on_progress=_progress)

    if args.card is not None:
        from pathlib import Path

        from .card import to_share_card

        out = Path(args.card)
        out.write_text(to_share_card(state), encoding="utf-8")
        print(out.resolve())
    elif args.dot:
        from .viz import to_dot

        print(to_dot(state.graph, gaps=state.gaps))
    elif args.mermaid:
        from .viz import to_mermaid

        print(to_mermaid(state.graph, gaps=state.gaps))
    elif args.json:
        print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
    else:
        print()
        print(state.report_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
