# Lacuna · Narrative Audit Pipeline (表述审阅引擎)

[English](README.md) | **中文**

> lacuna /ləˈkjuːnə/ n. 空缺、缺漏：一段叙述里本应存在、却没有被说出来的部分。

Lacuna 把一段单方面叙述（社媒发帖、投诉、声明、爆料）画成知识图谱，然后**审计这张图**，而不是判断谁对谁错。

## 它解决什么问题

一段有说服力的叙述，问题往往不在**说了什么**，而在**没说什么**。"我勤勤恳恳工作六年，上周五突然被开除，连补偿都没有"，听起来很完整。但开除理由是什么？此前有没有绩效沟通？有没有申诉？这些要素在本体上必然存在，却一个都没出现，而这种系统性的空缺本身就是信号。

人工审阅能凭经验追问这些问题，但慢、贵、不稳定。Lacuna 把这种"听没说出来的部分"的能力做成了确定性的流水线：

- **说了什么**：原文抽取出的实体、事件、关系（标 `stated`）；
- **暗示了什么**：本体推理补全的、没明说但逻辑上必然存在的节点（标 `inferred`）；
- **哪里矛盾**：图上的时间线冲突、互斥关系、属性不一致；
- **哪里是空的**：本体要求存在、但图中缺失的必要要素，每个空缺都附带该追问的问题。

## 设计原则（它不做什么）

- **不下"真/假"结论。** 输出的是结构化的审计发现 + 追问清单 + 置信度，判断留给人。
- **判定确定性，理解交给 LLM。** 要素空缺的判定是对照声明式本体查图，可复现、可解释；LLM 只负责真正需要语义理解的环节（抽取、打标签、实体消解、事件对齐），且每个 LLM 环节都有离线兜底或显式报错。
- **明说的和推出来的永远分开。** `stated` 与 `inferred` 从数据模型到报告全程分开标记，绝不混淆。
- **本体是数据不是代码。** 事件类型和角色清单是 TOML 文件，换领域（法律/保险/客服）就是换一份配置。

适用方向：内容平台的可信度辅助、客服/保险的投诉初筛、尽调与新闻编辑室的叙述核查。任何需要快速回答"这段话哪里经不起追问"的场景都适用。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 和一个 [OpenRouter](https://openrouter.ai) API key（Label 阶段必需；其余阶段无 key 时退回确定性逻辑）。

```bash
uv sync --extra dev                          # 1. 安装依赖
cp .env.example .env                         # 2. 填入 OPENROUTER_API_KEY
make run                                     # 3. 跑内置示例
```

### 命令行

```bash
# 审阅一段文本，输出 Markdown 报告
uv run python -m narrative_audit "上周五我被开除了，连补偿都没有。"

# 标注输入语境，帮助打标签
uv run python -m narrative_audit --context "社媒发帖" "……"

# 完整 JSON 状态（claims、图谱、冲突、空缺、证据、日志）
uv run python -m narrative_audit --json --demo

# 图谱可视化：实线=明说的，虚线=推理出来的，幽灵节点=该说没说的
uv run python -m narrative_audit --mermaid --demo    # 粘到 mermaid.live 即可看图
uv run python -m narrative_audit --dot --demo        # 喂给 graphviz: ... | dot -Tsvg
```

### Python API

```python
from narrative_audit import audit

state = audit("我带头研发了核心系统……上周五突然被开除……", context="社媒发帖")

print(state.report_markdown)              # 汇总报告（两条轨道）
print(state.overall_confidence)           # 整体置信度 0..1

for gap in state.gaps:                    # 要素空缺：核心输出
    print(gap.role_zh, gap.importance, gap.suggested_question)
for conflict in state.conflicts:          # 图上矛盾
    print(conflict.description)
for node in state.graph.nodes:            # 图谱节点（stated / inferred 分开标）
    print(node.status, node.label, node.aliases)

from narrative_audit import to_mermaid    # 可视化（或 to_dot）
print(to_mermaid(state.graph, gaps=state.gaps))
```

### 接真实检索

证据环节默认离线。`search_fn` 是一个 `Callable[[str], list[dict]]`，接什么后端都行：

```python
def my_search(query: str) -> list[dict]:
    return [{"snippet": "...", "source": "...", "url": "..."}, ...]

state = audit(text, search_fn=my_search)
```

### 换领域本体

内置本体覆盖 解雇/冲突/指控/损害/协议 五类事件。要扩展或替换，复制
[`src/narrative_audit/data/ontology.toml`](src/narrative_audit/data/ontology.toml)
改成你的领域（文件头有 schema 说明），然后在 `configs/default.toml` 里指过去：

```toml
[ontology]
path = "configs/my_domain_ontology.toml"
```

```python
from narrative_audit import pipeline_from_config
state = pipeline_from_config(path="configs/default.toml").run(text)
```

## 流水线

围绕一个共享的 `AuditState`：claim 轨道逐条审陈述，graph 轨道审整体结构，最后汇总。

```
Input 文本
  │
  ├─ Claim 轨道
  │   ↓  ClaimSplitter     把原文拆成原子陈述
  │   ↓  Label             打标签(事实/主观/推断/情绪化/引用/缺上下文) + 可核查度
  │   ↓  MissingContext    每条 claim 缺什么 + 该追问什么
  │
  ├─ Graph 轨道
  │   ↓  GraphBuilder      叙述 → 知识图谱（实体/事件/时间/关系，标 stated）
  │   ↓  EntityResolver    实体消解：合并同指实体（部门经理/经理/他 → 同一节点）
  │   ↓  OntologyReasoner  事件对齐本体类型，推理不显然的隐含节点（标 inferred）
  │   ↓  ConflictDetector  图上找矛盾：时间线/互斥关系/属性不一致/语义矛盾
  │   ↓  GapDetector       对照本体查必要要素空缺，关键空缺 = 可疑信号
  │
  ↓  Evidence              只对可核查事实搜证据，判断 支持/反驳/部分/无关/不足
  ↓  Report                置信度校准 + 汇总两条轨道，生成报告
```

更细的架构说明与路线图保留在本地 `docs/` 目录（不入远程仓库）。

## 目录结构

```
.
├── pyproject.toml            # 项目元数据 + 依赖（uv / hatchling, src 布局）
├── uv.lock                   # 依赖锁文件
├── .env.example              # 环境变量模板
├── .pre-commit-config.yaml   # 提交前钩子 (ruff)
├── Makefile                  # 常用命令
├── README.md / README.zh-CN.md / CHANGELOG.md
├── .github/workflows/        # CI（lint + test）
├── configs/                  # 运行时配置（模型/本体/证据/置信度）
├── examples/                 # 可直接运行的示例 + Gradio 演示
├── scripts/                  # 运维/一次性脚本
├── src/narrative_audit/      # 主代码包（含内置本体 data/ontology.toml）
└── tests/                    # 单元测试
```

## 开发

```bash
make lint      # ruff 检查
make format    # 自动格式化 + 修复
make test      # pytest
make demo      # 启动 Gradio 演示 (需 --extra demo)
```
