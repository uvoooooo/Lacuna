# Narrative Audit Pipeline (表述审阅引擎)

多 agent + shared state 的叙述审阅框架。把一段话拆成：**说了什么 / 暗示了什么 / 没说什么 / 证据够不够**——不判断谁对谁错。

对应设计见 [`MVP_items.md`](./MVP_items.md)、路线图见 [`roadmap.md`](./roadmap.md)。

## 架构

整条流水线围绕一个共享的 `AuditState` 对象，每个 agent 读写同一份状态（而非串行聊天）：

```
Input 文本
  ↓  ClaimSplitterAgent   把原文拆成原子陈述
  ↓  LabelAgent           打标签(事实/主观/推断/情绪化/引用/缺上下文) + 可核查度
  ↓  MissingContextAgent  缺什么(起因/证据/时间地点/第三方/反方/后续) + 该追问什么
  ↓  EvidenceAgent        只对可核查事实搜证据，判断 支持/反驳/部分/无关/不足
  ↓  ReportAgent          置信度校准 + 生成可读报告
```

MVP 实现了上述 5 个 agent。后续可加：Calibration / Source Credibility / Contradiction / Human Review / Domain agents——通过给 `NarrativeAuditPipeline(agents=[...])` 传自定义列表即可插入。

## 目录

```
src/narrative_audit/
  state.py        # 共享状态 AuditState / Claim / Evidence + 受控词表
  llm.py          # LLM 封装（OpenRouter）
  agents/         # 5 个 agent + BaseAgent
  pipeline.py     # 编排器 NarrativeAuditPipeline + audit()
  search.py       # 可插拔检索后端（含离线 mock）
  config.py       # TOML 运行时配置加载 (configs/default.toml)
  extractor.py    # 时序知识图谱抽取 baseline（独立模块）
  cli.py          # 命令行入口
```

## 用法

Label 阶段需要 LLM：必须配置 `OPENROUTER_API_KEY`（走 OpenRouter）。其余阶段（拆分/缺口/证据匹配）在无 key 时可退回确定性逻辑，但 Label 缺 LLM 会直接报错，绝不输出"猜的"标签。

```bash
# 内置示例
python -m narrative_audit --demo

# 直接传文本
python -m narrative_audit "我勤勤恳恳工作六年，上周五突然被开除，连补偿都没有。"

# 输出完整 JSON 状态
python -m narrative_audit --json --demo
```

代码调用：

```python
from narrative_audit import audit
from narrative_audit.search import make_mock_search

state = audit(
    "我在喜多多集团勤勤恳恳工作了六年……上周五突然被开除……",
    context="社媒发帖",
    search_fn=make_mock_search(),   # 不传则跳过外部检索
)

print(state.overall_confidence)
print(state.report_markdown)
for claim in state.claims:
    print(claim.to_dict())
```

## 接入真实检索

`EvidenceAgent` 的 `search_fn` 只是一个 `Callable[[str], list[dict]]`：

```python
def my_search(query: str) -> list[dict]:
    # 返回 [{"snippet": ..., "source": ..., "url": ...}, ...]
    ...

audit(text, search_fn=my_search)
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `OPENROUTER_API_KEY` | 配置后启用 LLM；缺省走启发式 |
| `OPENROUTER_MODEL` | 默认 `openai/gpt-4o-mini`（任意 OpenRouter 模型 slug） |
| `OPENROUTER_BASE_URL` | 默认 `https://openrouter.ai/api/v1` |
| `OPENROUTER_SITE_URL` / `OPENROUTER_APP_NAME` | 可选，OpenRouter 归因用 |
