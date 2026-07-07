"""
Gradio demo: paste a one-sided narrative, run the real pipeline, get the
shareable card and the Markdown report.

This is a thin shell over the actual `NarrativeAuditPipeline` (no mocked
search, no canned verdicts). The Label stage needs an LLM, so set
OPENROUTER_API_KEY first.

Run:
    uv run --extra demo python examples/gradio_demo.py
"""

import html

import gradio as gr

from narrative_audit import NarrativeAuditPipeline, to_share_card

_DEMO_TEXT = (
    "我在喜多多集团勤勤恳恳工作了六年，带头研发了核心系统。"
    "上周五，部门经理突然叫我去办公室，跟我说我被开除了，连补偿金都没提。"
    "他踢走老员工，霸占我的期权，这是赤裸裸的压榨！"
)

_pipeline = NarrativeAuditPipeline()


def run_audit(text: str, context: str):
    text = (text or "").strip()
    if not text:
        return "请输入要审阅的文本。", ""
    try:
        state = _pipeline.run(text, context=context)
    except RuntimeError as exc:
        return f"审阅失败：{exc}", ""
    card = to_share_card(state)
    frame = (
        f'<iframe srcdoc="{html.escape(card, quote=True)}" '
        'style="width:100%;height:960px;border:none;border-radius:8px;"></iframe>'
    )
    return state.report_markdown, frame


with gr.Blocks(title="Lacuna 表述审阅") as demo:
    gr.Markdown(
        "# Lacuna · 听没说出来的部分\n"
        "不判断真假，只标注结构：说了什么、暗示了什么、哪里矛盾、缺了什么。"
    )
    with gr.Row():
        text_box = gr.Textbox(label="单方面叙述", lines=5, value=_DEMO_TEXT)
        with gr.Column(scale=0):
            context_box = gr.Dropdown(
                ["社媒发帖", "客服投诉", "公开声明", ""],
                value="社媒发帖",
                label="语境",
            )
            run_btn = gr.Button("审 阅", variant="primary")
    with gr.Tab("审计卡片"):
        card_html = gr.HTML()
    with gr.Tab("Markdown 报告"):
        report_md = gr.Markdown()

    run_btn.click(run_audit, inputs=[text_box, context_box], outputs=[report_md, card_html])

if __name__ == "__main__":
    demo.launch()
