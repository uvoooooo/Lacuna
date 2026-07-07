"""
Shareable audit card (可分享审计卡片).

Renders an `AuditState` as one standalone, screenshot-ready HTML page: the
original text with subjective spans highlighted, and the centerpiece list
"这段话没告诉你的 N 件事" (the gaps, drawn as ghost boxes), plus conflicts,
implied-but-unstated nodes and a confidence bar.

    html = to_share_card(state)
    Path("audit.html").write_text(html, encoding="utf-8")

The card is a pure function of the state: no LLM, no network, no external
assets, so the file can be opened, screenshotted and shared anywhere.
"""

from __future__ import annotations

import html as _html
from datetime import date

from .graph import GapImportance, NodeStatus
from .state import AuditState, Claim, Label

_CSS = """
  :root {
    --paper: #faf8f4; --ink: #1c1b19; --muted: #78736b;
    --line: #e3ded5; --red: #c0392b; --amber: #b9770e;
    --hl: #fdf0d5; --ghost: #a49e94;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #1a191c; padding: 48px 16px;
    font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
    color: var(--ink); -webkit-font-smoothing: antialiased;
  }
  .card {
    max-width: 640px; margin: 0 auto; background: var(--paper);
    border-radius: 6px; padding: 44px 48px 36px;
    box-shadow: 0 24px 60px rgba(0,0,0,.45);
  }
  header { display: flex; justify-content: space-between; align-items: baseline; }
  .wordmark { font-size: 13px; letter-spacing: .35em; font-weight: 700; }
  .wordmark small { letter-spacing: .1em; font-weight: 400; color: var(--muted); margin-left: 8px; }
  .date { font-size: 12px; color: var(--muted); }
  .rule { border-top: 1px solid var(--ink); border-bottom: 1px solid var(--line);
          height: 3px; margin: 14px 0 28px; }
  .section-label {
    font-size: 11px; letter-spacing: .25em; color: var(--muted);
    text-transform: uppercase; margin-bottom: 12px;
  }
  .narrative {
    font-family: "Noto Serif SC", "Songti SC", Georgia, serif;
    font-size: 16px; line-height: 2; padding-left: 16px;
    border-left: 2px solid var(--line);
  }
  .hl-subjective { background: var(--hl); border-bottom: 1px dashed var(--amber);
                   padding: 1px 2px; border-radius: 2px; }
  .legend { font-size: 11px; color: var(--muted); margin-top: 10px; padding-left: 18px; }
  .legend .swatch { background: var(--hl); border-bottom: 1px dashed var(--amber);
                    padding: 0 4px; border-radius: 2px; }
  .headline {
    font-family: "Noto Serif SC", "Songti SC", Georgia, serif;
    font-size: 26px; font-weight: 700; line-height: 1.4; margin: 40px 0 6px;
  }
  .headline .count { color: var(--red); }
  .subhead { font-size: 13px; color: var(--muted); margin-bottom: 20px; }
  .gap {
    border: 1.5px dashed var(--ghost); border-radius: 6px;
    padding: 14px 16px; margin-bottom: 12px; display: flex; gap: 14px;
    background: rgba(255,255,255,.5);
  }
  .gap.required { border-color: var(--red); }
  .gap .num {
    font-family: Georgia, serif; font-size: 22px; font-style: italic;
    color: var(--ghost); min-width: 26px; line-height: 1.2;
  }
  .gap.required .num { color: var(--red); }
  .gap .role { font-size: 15px; font-weight: 600; }
  .badge {
    display: inline-block; font-size: 10px; font-weight: 600; letter-spacing: .1em;
    padding: 1px 7px; border-radius: 9px; margin-left: 8px; vertical-align: 2px;
  }
  .badge.required { color: #fff; background: var(--red); }
  .badge.expected { color: var(--amber); border: 1px solid var(--amber); }
  .gap .question { font-size: 13px; color: var(--muted); margin-top: 5px; line-height: 1.6; }
  .conflict {
    border-left: 3px solid var(--red); background: rgba(192,57,43,.06);
    padding: 10px 14px; margin-bottom: 10px; font-size: 13.5px; line-height: 1.7;
  }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip {
    font-size: 12px; color: var(--muted); border: 1px dashed var(--ghost);
    border-radius: 12px; padding: 3px 12px;
  }
  footer { margin-top: 40px; border-top: 1px solid var(--line); padding-top: 16px; }
  .meter { display: flex; align-items: center; gap: 10px; font-size: 12px;
           color: var(--muted); margin-bottom: 12px; }
  .meter .track { flex: 1; height: 4px; background: var(--line); border-radius: 2px; }
  .meter .fill { height: 4px; background: var(--ink); border-radius: 2px; }
  .tagline { font-size: 12px; color: var(--muted); line-height: 1.7; }
  .tagline b { color: var(--ink); }
"""

_SUBJECTIVE = {Label.OPINION, Label.EMOTIONAL}


def _esc(text: str) -> str:
    return _html.escape(text, quote=True)


def _highlighted_text(text: str, claims: list[Claim]) -> str:
    """Wrap each claim span found in the text; subjective spans get highlighted."""
    spans: list[tuple[int, int, Claim]] = []
    cursor = 0
    for claim in claims:
        fragment = claim.text.strip()
        if not fragment:
            continue
        index = text.find(fragment, cursor)
        if index == -1:
            index = text.find(fragment)
        if index == -1:
            continue
        spans.append((index, index + len(fragment), claim))
        cursor = index + len(fragment)
    spans.sort(key=lambda s: s[0])

    parts: list[str] = []
    position = 0
    for start, end, claim in spans:
        if start < position:  # overlapping span, keep the earlier one
            continue
        parts.append(_esc(text[position:start]))
        labels_zh = "、".join(Label.ZH.get(lbl, lbl) for lbl in claim.labels) or "陈述"
        css = "hl-subjective" if _SUBJECTIVE & set(claim.labels) else ""
        parts.append(
            f'<span class="{css}" title="{_esc(labels_zh)}">{_esc(text[start:end])}</span>'
        )
        position = end
    parts.append(_esc(text[position:]))
    return "".join(parts).replace("\n", "<br>")


def _gap_items(state: AuditState) -> str:
    items: list[str] = []
    ordered = sorted(state.gaps, key=lambda g: (g.importance != GapImportance.REQUIRED,))
    for i, gap in enumerate(ordered, 1):
        required = gap.importance == GapImportance.REQUIRED
        badge = (
            '<span class="badge required">必要</span>'
            if required
            else '<span class="badge expected">预期</span>'
        )
        items.append(
            f'<div class="gap{" required" if required else ""}">'
            f'<div class="num">{i}</div>'
            f'<div><div class="role">{_esc(gap.role_zh or gap.role)}{badge}</div>'
            f'<div class="question">{_esc(gap.suggested_question)}</div></div>'
            f"</div>"
        )
    return "\n".join(items)


def _conflict_items(state: AuditState) -> str:
    return "\n".join(
        f'<div class="conflict">{_esc(c.description or c.kind)}</div>' for c in state.conflicts
    )


def _implied_chips(state: AuditState) -> str:
    inferred = [n for n in state.graph.nodes if n.status == NodeStatus.INFERRED]
    return "\n".join(f'<div class="chip">{_esc(n.label)}</div>' for n in inferred)


def to_share_card(state: AuditState) -> str:
    """Render the audit as one standalone HTML page (no external assets)."""
    gap_count = len(state.gaps)
    if gap_count:
        headline = (
            f'这段话<span class="count">没告诉你</span>的 '
            f'<span class="count">{gap_count}</span> 件事'
        )
        subhead = "按本体应当存在、但叙述中没有出现的要素，缺失本身即是信号。"
    else:
        headline = "关键要素基本齐全"
        subhead = "对照事件本体，这段叙述没有明显的要素空缺。"

    conflicts_html = _conflict_items(state)
    conflicts_section = (
        f'<div class="section-label" style="margin-top:36px">前后矛盾</div>{conflicts_html}'
        if conflicts_html
        else ""
    )
    chips_html = _implied_chips(state)
    implied_section = (
        f'<div class="section-label" style="margin-top:32px">暗示但没明说</div>'
        f'<div class="chips">{chips_html}</div>'
        if chips_html
        else ""
    )
    confidence = max(0.0, min(1.0, state.overall_confidence))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lacuna 表述审阅</title>
<style>{_CSS}</style>
</head>
<body>
<div class="card">
  <header>
    <div class="wordmark">LACUNA<small>表述审阅</small></div>
    <div class="date">{date.today().isoformat()}</div>
  </header>
  <div class="rule"></div>

  <div class="section-label">原文</div>
  <div class="narrative">{_highlighted_text(state.text, state.claims)}</div>
  <div class="legend"><span class="swatch">黄底</span> = 主观 / 情绪化表述（悬停查看标签）</div>

  <div class="headline">{headline}</div>
  <div class="subhead">{subhead}</div>
  {_gap_items(state)}
  {conflicts_section}
  {implied_section}

  <footer>
    <div class="meter">
      <span>整体可信度</span>
      <div class="track"><div class="fill" style="width:{confidence:.0%}"></div></div>
      <span>{confidence:.0%}</span>
    </div>
    <div class="tagline"><b>Lacuna</b> 不判断真假，只标注结构：说了什么、暗示了什么、哪里矛盾、缺了什么。</div>
  </footer>
</div>
</body>
</html>
"""
