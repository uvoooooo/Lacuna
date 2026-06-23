import re
import time

import gradio as gr
import plotly.graph_objects as go

# ── Chinese font setup ──────────────────────────────────────────────────────

_CJK_FONT = "PingFang SC, Microsoft YaHei, SimHei, Arial Unicode MS, sans-serif"


# ── Graph layout & palette ──────────────────────────────────────────────────

_POS = {
    "小王": (0.0, 0.0),
    "核心系统": (1.8, 0.7),
    "部门经理": (-1.8, 0.7),
    "期权": (-1.8, -0.7),
    "HR介入": (-0.6, 1.6),
    "PIP预警": (0.6, 1.6),
    "数据泄漏\n(周四)": (1.8, -0.7),
    "小王叙事": (-0.7, -1.5),
    "隐瞒泄密事实": (0.7, -1.5),
    "时间锚点\nT-1(周四)": (0.2, 2.3),
    "时间锚点\nT0(周五)": (-1.0, 2.0),
}

_NODE_COLOR = {
    "小王": "#4FC3F7",
    "核心系统": "#81C784",
    "部门经理": "#FFB74D",
    "期权": "#B0BEC5",
    "数据泄漏\n(周四)": "#EF5350",
    "小王叙事": "#CE93D8",
    "隐瞒泄密事实": "#EF9A9A",
    "时间锚点\nT-1(周四)": "#FFF176",
    "时间锚点\nT0(周五)": "#FFD54F",
}

_GHOST_NODE_COLOR = "#FFCDD2"
_BG = "#FAFBFC"
_EDGE_COLOR = "#546E7A"
_GHOST_EDGE_COLOR = "#E53935"


# ── Rendering ───────────────────────────────────────────────────────────────


def _render_graph(
    title,
    solid_nodes,
    solid_edges,
    ghost_nodes=None,
    ghost_edges=None,
):
    """
    solid_nodes : list[str]
    solid_edges : list[(src, dst, label)]
    ghost_nodes : list[str] | None  —— dashed-border "missing" nodes
    ghost_edges : list[(src, dst, label)] | None
    """
    ghost_nodes = ghost_nodes or []
    ghost_edges = ghost_edges or []

    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, x=0.02, y=0.98, xanchor="left"),
        showlegend=True,
        plot_bgcolor=_BG,
        paper_bgcolor=_BG,
        margin=dict(l=20, r=20, t=70, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        font=dict(family=_CJK_FONT),
    )

    def _edge_timestamp(src, dst, label):
        key = (src, dst)
        explicit = {
            ("时间锚点\nT-1(周四)", "数据泄漏\n(周四)"): "T-1 / 周四",
            ("数据泄漏\n(周四)", "时间锚点\nT0(周五)"): "T0 / 周五",
            ("时间锚点\nT0(周五)", "部门经理"): "T0 / 周五",
            ("部门经理", "小王"): "T0 / 周五",
        }
        if key in explicit:
            return explicit[key]
        if "周四" in src or "周四" in dst or "周四" in label:
            return "周四"
        if "周五" in src or "周五" in dst or "周五" in label:
            return "周五"
        if "T+1" in label:
            return "周五（相对T-1）"
        return "时间待确认"

    def _add_edge_trace(src, dst, label, color, dash):
        x0, y0 = _POS[src]
        x1, y1 = _POS[dst]
        hover_text = f"关系：{label}<br>时间戳：{_edge_timestamp(src, dst, label)}"
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=2.2, dash=dash),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        # Invisible hitbox: only on hover show relation+timestamp
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color="rgba(0,0,0,0.01)", width=14),
                hovertemplate=f"{hover_text}<extra></extra>",
                showlegend=False,
            )
        )
        fig.add_annotation(
            x=x1,
            y=y1,
            ax=x0,
            ay=y0,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.1,
            arrowwidth=1.2,
            arrowcolor=color,
            opacity=0.9,
        )

    for s, d, lbl in solid_edges:
        _add_edge_trace(s, d, lbl, _EDGE_COLOR, "solid")
    for s, d, lbl in ghost_edges:
        _add_edge_trace(s, d, lbl, _GHOST_EDGE_COLOR, "dash")

    def _add_nodes(nodes, color_fn, symbol, border_color):
        x = [_POS[n][0] for n in nodes]
        y = [_POS[n][1] for n in nodes]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="markers+text",
                text=nodes,
                textposition="middle center",
                marker=dict(
                    size=58,
                    color=[color_fn(n) for n in nodes],
                    symbol=symbol,
                    line=dict(color=border_color, width=2),
                    opacity=0.92 if symbol == "circle" else 0.45,
                ),
                hovertemplate="<b>%{text}</b><extra></extra>",
                showlegend=False,
            )
        )

    _add_nodes(solid_nodes, lambda n: _NODE_COLOR.get(n, "#90CAF9"), "circle", "#37474F")
    if ghost_nodes:
        _add_nodes(ghost_nodes, lambda _: _GHOST_NODE_COLOR, "square", _GHOST_EDGE_COLOR)

    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=_EDGE_COLOR, width=2.2),
            name="已知关系",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color=_GHOST_EDGE_COLOR, width=2.2, dash="dash"),
            name="推断/缺失",
            hoverinfo="skip",
        )
    )

    return fig


# ── Graph stages ────────────────────────────────────────────────────────────


def graph_initial():
    return _render_graph(
        "阶段一：初步关系图谱 — 基于当事人叙述",
        solid_nodes=["小王", "核心系统", "部门经理", "期权"],
        solid_edges=[
            ("小王", "核心系统", "服务6年 / 核心研发"),
            ("部门经理", "小王", "突然解雇"),
            ("小王", "期权", "失去"),
        ],
    )


def graph_gap():
    return _render_graph(
        "阶段二：逻辑缺口检测 — 结构性留白分析",
        solid_nodes=["小王", "核心系统", "部门经理", "期权"],
        solid_edges=[
            ("小王", "核心系统", "服务6年 / 核心研发"),
            ("部门经理", "小王", "突然解雇"),
            ("小王", "期权", "失去"),
        ],
        ghost_nodes=["HR介入", "PIP预警"],
        ghost_edges=[
            ("HR介入", "小王", "缺失"),
            ("PIP预警", "小王", "缺失"),
        ],
    )


def graph_cross_domain():
    return _render_graph(
        "阶段三：跨域时序关联 — 引入外部情报",
        solid_nodes=[
            "小王",
            "核心系统",
            "部门经理",
            "期权",
            "数据泄漏\n(周四)",
            "时间锚点\nT-1(周四)",
            "时间锚点\nT0(周五)",
        ],
        solid_edges=[
            ("小王", "核心系统", "服务6年 / 核心研发"),
            ("部门经理", "小王", "周五紧急开除"),
            ("小王", "期权", "失去"),
            ("核心系统", "数据泄漏\n(周四)", "发生"),
            ("时间锚点\nT-1(周四)", "数据泄漏\n(周四)", "先发生"),
            ("时间锚点\nT0(周五)", "部门经理", "后触发处置"),
        ],
        ghost_nodes=["HR介入", "PIP预警"],
        ghost_edges=[
            ("HR介入", "小王", "缺失"),
            ("PIP预警", "小王", "缺失"),
            ("小王", "数据泄漏\n(周四)", "时序重合 (p=0.87)"),
        ],
    )


def graph_final():
    return _render_graph(
        "阶段四：时序知识图谱 — 最终取证",
        solid_nodes=[
            "小王",
            "核心系统",
            "部门经理",
            "数据泄漏\n(周四)",
            "隐瞒泄密事实",
            "时间锚点\nT-1(周四)",
            "时间锚点\nT0(周五)",
        ],
        solid_edges=[
            ("小王", "核心系统", "具备高权限"),
            ("核心系统", "数据泄漏\n(周四)", "发生"),
            ("时间锚点\nT-1(周四)", "数据泄漏\n(周四)", "事件发生"),
            ("数据泄漏\n(周四)", "时间锚点\nT0(周五)", "T+1天"),
            ("时间锚点\nT0(周五)", "部门经理", "合规应急流程"),
            ("部门经理", "小王", "合规处理 / 紧急开除"),
        ],
        ghost_edges=[
            ("小王", "数据泄漏\n(周四)", "疑似内鬼 / 重大失职 (p=0.87)"),
            ("小王", "隐瞒泄密事实", "结构性留白"),
        ],
    )


# ── Analysis pipeline (generator) ──────────────────────────────────────────

_MOCK_NEWS_POOL = [
    {
        "title": "喜多多集团启动年度组织盘点，多个业务线进入成本优化阶段",
        "source": "TechDaily",
        "time": "3天前",
        "summary": "公司内部进行人员和项目结构调整，重点关注核心业务ROI。",
    },
    {
        "title": "该公司核心产品线发布新版本，强调数据安全治理",
        "source": "产业观察",
        "time": "2天前",
        "summary": "发布会上多次提到安全合规和访问审计能力升级。",
    },
    {
        "title": "传该喜多多集团某部门负责人更替，研发管理权重新划分",
        "source": "职场前线",
        "time": "2天前",
        "summary": "部门内部管理链条出现调整，部分历史项目责任界面重定义。",
    },
    {
        "title": "行业快讯：某头部互联网企业上周四发生大规模数据泄漏事件",
        "source": "安全内参",
        "time": "1天前",
        "summary": "事故涉及核心系统访问权限，事后启动紧急审计与问责。",
    },
    {
        "title": "该企业合规团队近期提升异常操作追溯等级",
        "source": "Compliance Weekly",
        "time": "20小时前",
        "summary": "对高危权限变更和敏感数据导出实施更严格追踪机制。",
    },
    {
        "title": "社媒舆情：关于“无补偿开除资深员工”说法引发争议",
        "source": "PublicPulse",
        "time": "12小时前",
        "summary": "网友观点分化，一方质疑管理粗暴，另一方怀疑存在未披露背景。",
    },
]


def _extract_query_keywords(text):
    text = (text or "").strip()
    if not text:
        return ["喜多多集团", "核心系统", "开除", "数据泄漏"]

    candidate_terms = [
        "喜多多集团",
        "核心系统",
        "核心研发",
        "开除",
        "补偿",
        "期权",
        "经理",
        "HR",
        "PIP",
        "数据泄漏",
        "合规",
        "审计",
    ]
    extracted = [term for term in candidate_terms if term in text]

    # 叙事里出现“突然开除 + 核心系统”时，补一个安全主题词提升检索命中
    if (
        "开除" in text
        and ("核心系统" in text or "核心研发" in text)
        and "数据泄漏" not in extracted
    ):
        extracted.append("数据泄漏")

    if not extracted:
        extracted = ["喜多多集团", "核心系统", "开除", "数据泄漏"]

    return extracted[:5]


def _mock_search(keywords):
    if not keywords:
        return _MOCK_NEWS_POOL[:5]

    if isinstance(keywords, str):
        keywords = [kw for kw in re.split(r"[,，\s]+", keywords) if kw]

    scored_hits = []
    for item in _MOCK_NEWS_POOL:
        blob = f"{item['title']} {item['summary']}"
        score = sum(1 for keyword in keywords if keyword and keyword in blob)
        if score > 0:
            scored_hits.append((score, item))

    scored_hits.sort(key=lambda x: x[0], reverse=True)
    hits = [item for _, item in scored_hits]

    # 如果匹配太少，补齐一些通用公司资讯，让“检索过程”更真实
    if len(hits) < 4:
        for item in _MOCK_NEWS_POOL:
            if item not in hits:
                hits.append(item)
            if len(hits) >= 5:
                break
    return hits[:6]


def _format_retrieval_markdown(items, keywords=None):
    lines = ["### 🌐 外部检索过程（模拟）", ""]
    if keywords:
        query = " ".join(keywords)
        lines.append(f"- 检索关键词：`{query}`")
        lines.append("")
    for idx, item in enumerate(items, start=1):
        lines.append(
            f"- **[{idx}] {item['title']}**  "
            f"来源：`{item['source']}` · 时间：`{item['time']}`  \n"
            f"  摘要：{item['summary']}"
        )
    return "\n".join(lines)


def _extract_external_intel(items):
    for item in items:
        text = f"{item['title']} {item['summary']}"
        if "数据泄漏" in text:
            return (
                "喜多多集团在上周四发生了严重的大规模数据泄漏事件，"
                "事故涉及核心系统访问权限并触发紧急审计。"
            )
    return ""


def _build_conclusion_popup_html(title, analysis, confidence, timeline_points, conclusion):
    timeline_html = "".join(f"<li>{point}</li>" for point in timeline_points)
    return f"""
<div id="forensics-popup-overlay" style="
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.55);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
">
  <div style="
      width: min(760px, 92vw);
      max-height: 86vh;
      overflow: auto;
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.25);
      border: 1px solid #e5e7eb;
      padding: 22px 24px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #0f172a;
  ">
    <button
      onclick="document.getElementById('forensics-popup-overlay').style.display='none'"
      style="
        float: right;
        border: 0;
        background: #f1f5f9;
        color: #334155;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 18px;
        line-height: 1;
      "
      aria-label="关闭弹窗"
      title="关闭"
    >×</button>
    <div style="font-size: 22px; font-weight: 700; margin-bottom: 12px;">{title}</div>
    <div style="margin-bottom: 8px;"><b>分析结果：</b> {analysis}</div>
    <div style="margin-bottom: 12px;"><b>结论置信度：</b> <code>{confidence}</code></div>
    <div style="font-weight: 600; margin-bottom: 6px;">时序证据链：</div>
    <ul style="margin-top: 0; margin-bottom: 14px; padding-left: 18px;">
      {timeline_html}
    </ul>
    <div style="line-height: 1.6;"><b>结论：</b> {conclusion}</div>
    <div style="margin-top: 14px; color: #64748b; font-size: 13px;">
      再次点击“开始真相溯源”将自动关闭并刷新本弹窗内容。
    </div>
  </div>
</div>
"""


def analyze_narrative(text):
    yield (
        "🧾 正在解析当事人陈述并提取检索关键词...",
        None,
        gr.update(value="### 🌐 外部检索过程（模拟）\n\n- 正在从陈述中抽取关键词...", visible=True),
        gr.update(value="", visible=False),
        gr.update(visible=False),
    )
    time.sleep(0.8)

    keywords = _extract_query_keywords(text)
    yield (
        "🌐 正在检索外部公开信息...",
        None,
        gr.update(
            value=_format_retrieval_markdown([], keywords=keywords) + "\n\n- 正在建立查询...",
            visible=True,
        ),
        gr.update(value="", visible=False),
        gr.update(visible=False),
    )
    time.sleep(0.8)

    retrieved = _mock_search(keywords)
    progressive_items = []
    for idx, item in enumerate(retrieved, start=1):
        progressive_items.append(item)
        yield (
            f"🌐 检索进行中：已抓取 {idx}/{len(retrieved)} 条相关资讯",
            None,
            gr.update(
                value=_format_retrieval_markdown(progressive_items, keywords=keywords), visible=True
            ),
            gr.update(value="", visible=False),
            gr.update(visible=False),
        )
        time.sleep(0.45)

    external_news = _extract_external_intel(retrieved)
    yield (
        "🔍 正在提取实体...",
        None,
        gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
        gr.update(value="", visible=False),
        gr.update(visible=False),
    )
    time.sleep(1)

    yield (
        "🕸️ 正在构建初步关系图谱...",
        graph_initial(),
        gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
        gr.update(value="", visible=False),
        gr.update(visible=False),
    )
    time.sleep(1.5)

    yield (
        "⚠️ 发现逻辑缺口：缺失 HR 介入节点、缺失 PIP 预警节点。检测到叙事结构不完整。",
        graph_gap(),
        gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
        gr.update(value="", visible=False),
        gr.update(visible=False),
    )
    time.sleep(2)

    if "数据泄漏" in external_news:
        yield (
            "🧠 正在跨域关联外部新闻：发现'数据泄漏'与'核心负责人解雇'在时间轴高度重合...",
            graph_cross_domain(),
            gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
            gr.update(value="", visible=False),
            gr.update(visible=False),
        )
        time.sleep(2)

        conclusion_popup = _build_conclusion_popup_html(
            title="🚨 真相取证结论",
            analysis="叙事可信度极低",
            confidence="0.93（高）",
            timeline_points=[
                "T-1（周四）核心系统发生大规模数据泄漏",
                "T0（周五）出现紧急开除且流程异常（缺失 HR/PIP 常规链）",
                "两事件时间紧邻且人物权限高度重合，形成“事故 -> 应急处置 -> 叙事留白”闭环",
            ],
            conclusion="小王利用信息差，将“抓包开除”包装成“职场霸凌”。",
        )
        yield (
            "✅ 分析完成！逻辑补全已达成。",
            graph_final(),
            gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
            gr.update(value=conclusion_popup, visible=True),
            gr.update(visible=True),
        )
    else:
        conclusion_popup = _build_conclusion_popup_html(
            title="ℹ️ 真相取证结论",
            analysis="未发现足够强的外部反转证据",
            confidence="0.61（中）",
            timeline_points=[
                "已完成多源公开资讯检索并抽取关键事件",
                "当前结果与“数据泄漏/合规处置”时序链关联不足",
                "仅能确认叙事存在结构性留白，需更多证据补强",
            ],
            conclusion="现阶段暂不足以下强反转结论。",
        )
        yield (
            "✅ 分析完成。未发现显著外部冲突。",
            graph_gap(),
            gr.update(value=_format_retrieval_markdown(retrieved, keywords=keywords), visible=True),
            gr.update(value=conclusion_popup, visible=True),
            gr.update(visible=True),
        )


# ── Gradio UI ───────────────────────────────────────────────────────────────

with gr.Blocks(title="GraphRAG 真相取证引擎") as demo:
    gr.Markdown("""
    # 🕵️‍♂️ GraphRAG-based Truth Forensics
    ### 挖掘叙事背后的"逻辑留白"与事实反转
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📥 输入端 (Input)")
            input_text = gr.Textbox(
                label="当事人陈述",
                placeholder="在此输入当事人的叙事...",
                lines=5,
                value=(
                    "我在喜多多集团勤勤恳恳工作了六年，带头研发了核心系统。"
                    "上周五，部门经理突然叫我去办公室，跟我说我被开除了，"
                    "连补偿金都没提。他踢走老员工，霸占我的期权，这是赤裸裸的压榨！"
                ),
            )
            btn = gr.Button("开始真相溯源", variant="primary")
            retrieval_display = gr.Markdown(
                value="### 🌐 外部检索过程（模拟）\n\n- 待检索",
                label="外部检索过程",
                visible=False,
            )

        with gr.Column(scale=2):
            gr.Markdown("### 🧠 推理引擎 (Reasoning)")
            status_box = gr.Label(label="系统状态", value="待命")
            graph_display = gr.Plot(
                label="GraphRAG 动态拓扑演变",
            )

    result_display = gr.HTML(label="最终取证结论弹窗", visible=False)

    btn.click(
        fn=analyze_narrative,
        inputs=[input_text],
        outputs=[status_box, graph_display, retrieval_display, result_display, btn],
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
