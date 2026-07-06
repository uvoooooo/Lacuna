# Narrative Audit Pipeline (表述审阅引擎)

多 agent + shared state 的叙述审阅框架，**以知识图谱为核心**。把一段话（narrative）画成一张图，然后审计这张图：

- **说了什么**——原文抽取出的实体、事件、关系（stated）；
- **暗示了什么**——本体推理补全的、原文没明说但逻辑上必然存在的节点（inferred）；
- **哪里矛盾**——图上的时间线冲突、互斥关系、属性不一致（conflict）；
- **哪里是空的**——本体要求存在、但图中缺失的必要要素；关键要素的空缺本身就是可疑信号（gap）。

不判断谁对谁错。核心思想见 [`paragraph.md`](./paragraph.md)，claim 层设计见 [`MVP_items.md`](./MVP_items.md)，路线图见 [`roadmap.md`](./roadmap.md)。

## 架构

整条流水线围绕一个共享的 `AuditState` 对象，每个 agent 读写同一份状态（而非串行聊天）。状态里有两条并行的视图：**claim 列表**（逐条陈述审计）和 **叙述图谱**（结构审计），最后由 Report 汇总。

```
Input 文本
  │
  ├─ Claim 轨道
  │   ↓  ClaimSplitterAgent    把原文拆成原子陈述
  │   ↓  LabelAgent            打标签(事实/主观/推断/情绪化/引用/缺上下文) + 可核查度
  │   ↓  MissingContextAgent   每条 claim 缺什么 + 该追问什么
  │
  ├─ Graph 轨道
  │   ↓  GraphBuilderAgent     叙述 → 知识图谱（实体/事件/时间/关系，标 stated）
  │   ↓  OntologyReasonerAgent 事件对齐本体类型；推理不显然的隐含节点（标 inferred）
  │   ↓  ConflictDetectorAgent 图上找矛盾：时间线冲突/互斥关系/属性不一致/语义矛盾
  │   ↓  GapDetectorAgent      对照本体查必要要素空缺，关键空缺 = 可疑信号
  │
  ↓  EvidenceAgent             只对可核查事实搜证据，判断 支持/反驳/部分/无关/不足
  ↓  ReportAgent               置信度校准 + 汇总两条轨道，生成可读报告
```

### 图谱数据模型（`graph.py`）

- `GraphNode`：`id / label / node_type(entity|event|time|role) / status(stated|inferred)`
- `GraphEdge`：`source / target / relation / status / confidence`
- `Conflict`：`kind(timeline|exclusive_relation|attribute|semantic) / involved / description / severity`
- `Gap`：`event_id / role / importance(required|expected) / why_suspicious / suggested_question`

`status` 是整个设计的关键：**stated（原文明说）与 inferred（本体推理出来的）永远分开标记**，报告里也分开呈现。

### 本体（`ontology.py`）

轻量声明式本体：每种事件类型声明它的必要角色（required）与预期角色（expected），以及该类型蕴含的隐含前提。例如：

```
dismissal(解雇):
  required: employer(开除方), reason(理由), prior_employment(在先劳动关系)
  expected: compensation(补偿处理), prior_warning(事先警告/绩效记录), employee_response(当事人回应)
```

事件 → 本体类型的对齐由 LLM 完成（离线时用关键词兜底）；**要素空缺的判定本身是确定性的**——对照声明的角色清单查图，不靠模型"感觉"。

## 目录

```
src/narrative_audit/
  state.py        # 共享状态 AuditState / Claim / Evidence + 受控词表
  graph.py        # NarrativeGraph / GraphNode / GraphEdge / Conflict / Gap
  ontology.py     # 事件类型 → 必要/预期角色 的轻量本体
  llm.py          # LLM 封装（OpenRouter）
  agents/         # 9 个 agent + BaseAgent
  pipeline.py     # 编排器 NarrativeAuditPipeline + audit()
  search.py       # 可插拔检索后端（含离线 mock）
  config.py       # TOML 运行时配置加载 (configs/default.toml)
  extractor.py    # 时序知识图谱抽取 baseline（GraphBuilder 的离线兜底）
  cli.py          # 命令行入口
```

## 用法

Label 与本体推理阶段需要 LLM：必须配置 `OPENROUTER_API_KEY`（走 OpenRouter）。其余阶段（拆分/建图/冲突/空缺/证据匹配）在无 key 时可退回确定性逻辑。

```bash
# 内置示例
python -m narrative_audit --demo

# 直接传文本
python -m narrative_audit "我勤勤恳恳工作六年，上周五突然被开除，连补偿都没有。"

# 输出完整 JSON 状态（含图谱、冲突、要素空缺）
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
for node in state.graph.nodes:      # 图谱节点（含 inferred）
    print(node.to_dict())
for conflict in state.conflicts:    # 冲突
    print(conflict.to_dict())
for gap in state.gaps:              # 要素空缺
    print(gap.to_dict())
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
