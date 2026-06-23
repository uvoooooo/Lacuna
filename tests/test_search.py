"""Tests for the offline mock search backend."""

from narrative_audit.search import make_mock_search


def test_mock_search_matches_chinese_via_bigrams():
    search = make_mock_search()
    hits = search("公司上周四发生了大规模数据泄漏")
    assert hits
    assert any("数据泄漏" in h["snippet"] for h in hits)


def test_mock_search_returns_empty_for_unrelated_query():
    search = make_mock_search()
    assert search("今天天气真好心情不错") == []


def test_mock_search_respects_max_hits():
    search = make_mock_search(max_hits=1)
    hits = search("数据泄漏 合规 系统 部门")
    assert len(hits) <= 1
