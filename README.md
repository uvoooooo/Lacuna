# Lacuna · Narrative Audit Pipeline (表述审阅引擎)

把一段叙述（narrative）画成知识图谱，然后审计这张图：**说了什么 / 暗示了什么 / 哪里矛盾 / 哪些必要的位置是空的**——不判断谁对谁错。

主线：叙述 → 知识图谱 → 本体推理（补全不显然的隐含节点）→ 冲突识别（图上的矛盾）→ 要素识别（必要要素空缺，空缺本身即可疑信号）。图谱轨道与逐条 claim 审计轨道并行，共享一份状态，最后汇总成报告。

> 核心理念（见 [`docs/paragraph.md`](docs/paragraph.md)）：不要只听他说了什么，更要注意整幅图里缺了什么——听没说出来的部分。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/)。Label 阶段依赖 LLM，因此运行前需设置 `OPENROUTER_API_KEY`（走 [OpenRouter](https://openrouter.ai)；其余阶段无 key 时可退回确定性逻辑）。

```bash
uv sync --extra dev          # 安装依赖
make run                     # 运行内置示例
# 或：
uv run python -m narrative_audit "上周五我被开除了，连补偿都没有。"
uv run python -m narrative_audit --json --demo
```

启用 LLM：复制 `.env.example` 为 `.env` 并填入 `OPENROUTER_API_KEY`（走 [OpenRouter](https://openrouter.ai)）。

## 流水线

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
  │   ↓  OntologyReasoner  事件对齐本体类型，推理不显然的隐含节点（标 inferred）
  │   ↓  ConflictDetector  图上找矛盾：时间线/互斥关系/属性不一致/语义矛盾
  │   ↓  GapDetector       对照本体查必要要素空缺，关键空缺 = 可疑信号
  │
  ↓  Evidence              只对可核查事实搜证据，判断 支持/反驳/部分/无关/不足
  ↓  Report                置信度校准 + 汇总两条轨道，生成报告
```

详见 [`docs/architecture.md`](docs/architecture.md)，路线图见 [`docs/roadmap.md`](docs/roadmap.md)。

## 目录结构

```
.
├── pyproject.toml            # 项目元数据 + 依赖（uv / hatchling, src 布局）
├── uv.lock                   # 依赖锁文件
├── .env.example              # 环境变量模板
├── .pre-commit-config.yaml   # 提交前钩子 (ruff)
├── Makefile                  # 常用命令
├── README.md / CHANGELOG.md
├── .github/workflows/        # CI（lint + test）
├── configs/                  # 运行时配置（模型/证据/置信度）
├── docs/                     # 架构、路线图、ADR、调研背景
├── examples/                 # 可直接运行的示例 + Gradio 演示
├── scripts/                  # 运维/一次性脚本
├── src/narrative_audit/      # 主代码包
└── tests/                    # 单元测试
```

## 开发

```bash
make lint      # ruff 检查
make format    # 自动格式化 + 修复
make test      # pytest
make demo      # 启动 Gradio 演示 (需 --extra demo)
```

## 代码调用

```python
from narrative_audit import audit
from narrative_audit.search import make_mock_search

state = audit("我带头研发了核心系统……上周五突然被开除……",
              context="社媒发帖",
              search_fn=make_mock_search())   # 不传则跳过外部检索

print(state.overall_confidence)
print(state.report_markdown)
for node in state.graph.nodes:      # 图谱节点（inferred = 本体推理出来的）
    print(node.to_dict())
for conflict in state.conflicts:    # 冲突
    print(conflict.to_dict())
for gap in state.gaps:              # 要素空缺
    print(gap.to_dict())
```

接真实检索：`search_fn` 只是 `Callable[[str], list[dict]]`，返回 `[{"snippet","source","url"}, ...]` 即可。
