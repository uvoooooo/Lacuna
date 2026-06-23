#!/usr/bin/env python3
"""
One-off script: audit a text file and write the full JSON state next to it.

    uv run python scripts/audit_file.py path/to/narrative.txt [--config configs/default.toml]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from narrative_audit.config import pipeline_from_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a text file -> JSON report")
    parser.add_argument("path", type=Path, help="输入文本文件")
    parser.add_argument("--config", default="configs/default.toml", help="运行时配置 TOML")
    parser.add_argument(
        "--out", type=Path, default=None, help="输出 JSON 路径（默认同名 .audit.json）"
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"找不到文件: {args.path}", file=sys.stderr)
        return 1

    text = args.path.read_text(encoding="utf-8").strip()
    pipeline = pipeline_from_config(path=args.config)
    state = pipeline.run(text)

    out = args.out or args.path.with_suffix(".audit.json")
    out.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出: {out}  (总体置信度 {state.overall_confidence:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
