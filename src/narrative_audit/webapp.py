"""
Local web app (本地网页版): one input box, one button, out comes the card.

The zero-friction surface for the audit: paste a one-sided narrative, hit 审阅,
and get the shareable card rendered in place, with a download button. The page
and the API live in this one module; the card itself comes from `card.py`.

Requires the `web` extra and an OpenRouter key:

    uv sync --extra web
    uv run python -m narrative_audit.webapp        # http://127.0.0.1:8000

Host/port via env: LACUNA_HOST / LACUNA_PORT.
"""

# NOTE: no `from __future__ import annotations` here. FastAPI resolves
# endpoint annotations at request time against module globals; deferred
# (string) annotations would break the locally imported `Request` type.

import os

from .card import to_share_card
from .pipeline import NarrativeAuditPipeline

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lacuna · 听没说出来的部分</title>
<style>
  :root {
    --paper: #faf8f4; --ink: #1c1b19; --muted: #78736b;
    --line: #e3ded5; --red: #c0392b; --amber: #b9770e; --ghost: #a49e94;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #1a191c; min-height: 100vh; padding: 56px 16px;
    font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
    color: var(--paper); -webkit-font-smoothing: antialiased;
  }
  .shell { max-width: 680px; margin: 0 auto; }
  .wordmark { font-size: 15px; letter-spacing: .45em; font-weight: 700; }
  h1 {
    font-family: "Noto Serif SC", "Songti SC", Georgia, serif;
    font-size: 34px; font-weight: 700; margin: 18px 0 8px; line-height: 1.35;
  }
  h1 em { font-style: normal; color: #e5a34c; }
  .sub { color: #9b958c; font-size: 14px; line-height: 1.8; margin-bottom: 32px; }
  .panel {
    background: var(--paper); color: var(--ink); border-radius: 8px;
    padding: 24px; box-shadow: 0 24px 60px rgba(0,0,0,.45);
  }
  textarea {
    width: 100%; min-height: 150px; border: 1px solid var(--line); border-radius: 6px;
    padding: 14px; font-size: 15px; line-height: 1.9; resize: vertical;
    font-family: "Noto Serif SC", "Songti SC", Georgia, serif; background: #fff;
    color: var(--ink); outline: none;
  }
  textarea:focus { border-color: var(--ghost); }
  .row { display: flex; align-items: center; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
  select {
    border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px;
    font-size: 13px; color: var(--ink); background: #fff;
  }
  .examples { display: flex; gap: 8px; flex-wrap: wrap; }
  .example {
    font-size: 12px; color: var(--muted); border: 1px dashed var(--ghost);
    border-radius: 12px; padding: 4px 12px; cursor: pointer; background: none;
  }
  .example:hover { color: var(--ink); border-color: var(--ink); }
  .go {
    margin-left: auto; background: var(--ink); color: var(--paper); border: none;
    border-radius: 6px; padding: 10px 26px; font-size: 15px; letter-spacing: .3em;
    cursor: pointer;
  }
  .go:hover { background: #000; }
  .go:disabled { opacity: .5; cursor: wait; }
  .status { margin-top: 22px; color: #9b958c; font-size: 14px; display: none; }
  .status .dot { display: inline-block; animation: blink 1.2s infinite; }
  @keyframes blink { 0%,100% { opacity: .2 } 50% { opacity: 1 } }
  .error { margin-top: 22px; color: #e07b6d; font-size: 14px; display: none; line-height: 1.7; }
  .result { display: none; margin-top: 34px; }
  .actions { display: flex; gap: 10px; margin-bottom: 14px; }
  .action {
    font-size: 13px; color: var(--paper); background: none; cursor: pointer;
    border: 1px solid #4a474f; border-radius: 6px; padding: 7px 16px;
  }
  .action:hover { border-color: var(--paper); }
  iframe { width: 100%; border: none; border-radius: 8px; background: #1a191c; }
  footer { margin-top: 48px; color: #6f6a72; font-size: 12px; line-height: 1.8; }
</style>
</head>
<body>
<div class="shell">
  <div class="wordmark">LACUNA</div>
  <h1>听<em>没说出来</em>的部分</h1>
  <div class="sub">粘贴一段单方面叙述（社媒发帖、投诉、声明），Lacuna 把它画成知识图谱并审计：
说了什么、暗示了什么、哪里矛盾、哪些必要的位置是空的。不判断真假，只标注结构。</div>

  <div class="panel">
    <textarea id="text" placeholder="把那段话粘贴到这里……"></textarea>
    <div class="row">
      <select id="context">
        <option value="社媒发帖">社媒发帖</option>
        <option value="客服投诉">客服投诉</option>
        <option value="公开声明">公开声明</option>
        <option value="">其他</option>
      </select>
      <div class="examples">
        <button class="example" data-i="0">示例：被开除</button>
        <button class="example" data-i="1">示例：租房纠纷</button>
      </div>
      <button class="go" id="go">审 阅</button>
    </div>
  </div>

  <div class="status" id="status">多个 agent 审阅中<span class="dot">…</span>（视模型速度约需半分钟）</div>
  <div class="error" id="error"></div>

  <div class="result" id="result">
    <div class="actions">
      <button class="action" id="download">下载卡片 HTML</button>
      <button class="action" id="again">再来一段</button>
    </div>
    <iframe id="card"></iframe>
  </div>

  <footer>Lacuna · Narrative Audit Pipeline。卡片可直接截图分享，下载的 HTML 单文件可离线打开。</footer>
</div>

<script>
const EXAMPLES = [
  "我在喜多多集团勤勤恳恳工作了六年，带头研发了核心系统。上周五，部门经理突然叫我去办公室，跟我说我被开除了，连补偿金都没提。他踢走老员工，霸占我的期权，这是赤裸裸的压榨！",
  "房东上周突然把我的东西扔出来，押金一分不退。我去理论，他还叫人推了我一把。这种黑心房东必须曝光！"
];
const el = id => document.getElementById(id);
let cardHtml = "";

document.querySelectorAll(".example").forEach(b =>
  b.addEventListener("click", () => { el("text").value = EXAMPLES[+b.dataset.i]; }));

el("again").addEventListener("click", () => {
  el("result").style.display = "none";
  el("text").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

el("download").addEventListener("click", () => {
  const blob = new Blob([cardHtml], { type: "text/html;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "lacuna_card.html";
  a.click();
  URL.revokeObjectURL(a.href);
});

el("go").addEventListener("click", async () => {
  const text = el("text").value.trim();
  el("error").style.display = "none";
  if (!text) { el("text").focus(); return; }
  el("go").disabled = true;
  el("status").style.display = "block";
  el("result").style.display = "none";
  try {
    const resp = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, context: el("context").value })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    cardHtml = data.card_html;
    const frame = el("card");
    frame.onload = () => {
      frame.style.height = frame.contentDocument.body.scrollHeight + "px";
    };
    frame.srcdoc = cardHtml;
    el("result").style.display = "block";
    frame.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    el("error").textContent = "审阅失败：" + err.message;
    el("error").style.display = "block";
  } finally {
    el("go").disabled = false;
    el("status").style.display = "none";
  }
});
</script>
</body>
</html>
"""


def create_app(pipeline: NarrativeAuditPipeline | None = None):
    """Build the FastAPI app. Pass a custom pipeline for testing/offline use."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The web app needs the 'web' extra: uv sync --extra web") from exc

    app = FastAPI(title="Lacuna", docs_url=None, redoc_url=None)
    pipe = pipeline or NarrativeAuditPipeline()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _PAGE

    @app.post("/api/audit")
    async def audit(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "无效的 JSON 请求体"}, status_code=400)
        text = str(payload.get("text", "")).strip()
        context = str(payload.get("context", "")).strip()
        if not text:
            return JSONResponse({"error": "文本不能为空"}, status_code=400)
        if len(text) > 4000:
            return JSONResponse({"error": "文本过长（上限 4000 字）"}, status_code=400)
        try:
            # The pipeline is synchronous and slow (several LLM calls); keep
            # the event loop free while it runs.
            from starlette.concurrency import run_in_threadpool

            state = await run_in_threadpool(pipe.run, text, context=context)
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=503)
        return {
            "card_html": to_share_card(state),
            "gaps": len(state.gaps),
            "conflicts": len(state.conflicts),
            "confidence": round(state.overall_confidence, 2),
        }

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("LACUNA_HOST", "127.0.0.1"),
        port=int(os.environ.get("LACUNA_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
