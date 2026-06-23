"""
Pluggable search backends for the Evidence Agent.

`make_mock_search` returns an offline `SearchFn` backed by an in-memory corpus,
so you can demo the full evidence flow without network access. Swap in a real
implementation (web search, vector DB, internal docs) with the same signature:

    def my_search(query: str) -> list[dict]:
        return [{"snippet": ..., "source": ..., "url": ...}, ...]
"""

from __future__ import annotations

import re

from .agents import SearchFn

_DEFAULT_CORPUS: list[dict[str, str]] = [
    {
        "snippet": "行业快讯：某头部企业上周四发生大规模数据泄漏，事故涉及核心系统访问权限，事后启动紧急审计与问责。",
        "source": "安全内参",
        "url": "https://example.com/news/leak",
    },
    {
        "snippet": "该公司合规团队近期提升异常操作追溯等级，对高危权限变更与敏感数据导出实施更严格追踪。",
        "source": "Compliance Weekly",
        "url": "https://example.com/news/compliance",
    },
    {
        "snippet": "传该集团某部门负责人更替，研发管理权重新划分，部分历史项目责任界面重定义。",
        "source": "职场前线",
        "url": "https://example.com/news/reorg",
    },
]


def make_mock_search(corpus: list[dict[str, str]] = None, max_hits: int = 3) -> SearchFn:
    """Build an offline keyword-overlap search function."""
    docs = corpus if corpus is not None else _DEFAULT_CORPUS

    def _search(query: str) -> list[dict[str, str]]:
        grams = _ngrams(query)
        if not grams:
            return []
        scored = []
        for doc in docs:
            blob = doc.get("snippet", "")
            score = sum(1 for g in grams if g in blob)
            if score >= 2:  # require a bit of overlap to avoid spurious hits
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:max_hits]]

    return _search


def _ngrams(text: str) -> list[str]:
    """Character bigrams for CJK + whole words for latin/digits (no segmenter needed)."""
    grams: list[str] = []
    for chunk in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]+", text or ""):
        if re.match(r"[A-Za-z0-9]+", chunk) and "\u4e00" not in chunk:
            if len(chunk) >= 2:
                grams.append(chunk)
            continue
        for i in range(len(chunk) - 1):
            grams.append(chunk[i : i + 2])
    return grams
