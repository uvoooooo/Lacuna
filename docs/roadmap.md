# Roadmap

## Now — MVP (v0.1)
- [x] Shared-state multi-agent pipeline
- [x] 5 agents: ClaimSplitter / Label / MissingContext / Evidence / Report
- [x] LLM-driven labeling (no hardcoded lexicons; requires OpenRouter key)
- [x] Pluggable search backend (offline mock)
- [x] CLI + JSON output
- [x] src layout, packaging, CI, tests

## Now — Graph-centric audit (v0.2)
主思想落地：叙述 → 知识图谱 → 本体推理 → 冲突识别 + 要素缺失识别（见 [`paragraph.md`](./paragraph.md)）。

- [x] **GraphBuilder Agent** — 叙述 → 知识图谱（实体/事件/时间/关系，标 stated）
- [x] **OntologyReasoner Agent** — 事件对齐本体类型，推理不显然的隐含节点（标 inferred）
- [x] **ConflictDetector Agent** — 图上矛盾：时间线冲突/互斥关系/属性不一致/语义矛盾
- [x] **GapDetector Agent** — 对照本体查必要要素空缺，关键空缺 = 可疑信号
- [x] 轻量声明式本体（事件类型 → required/expected 角色）
- [ ] 本体外置为 TOML/YAML，可按领域扩展
- [ ] 图谱可视化（导出 DOT / mermaid）

## Next — Reliability (v0.3)
- [ ] **Calibration Agent** — 把规则置信度替换为校准后的概率
- [ ] **Source Credibility Agent** — 来源可信度评级，喂给证据打分
- [ ] Real search backend (web / vector DB / 用户上传材料)
- [ ] Better Chinese claim segmentation (LLM-first, 规则兜底)
- [ ] 图谱与证据联动：inferred 节点自动生成检索 query

## Later — Product (v0.4+)
- [ ] **Human Review Agent** — 低置信度样本进入人工复核
- [ ] **Domain Agents** — 法律 / 保险 / 客服 / 新闻 各一套规则与 schema
- [ ] B2B Copilot 形态：API + 报告导出 (ClaimReview 结构化)
- [ ] 评测集与回归（FEVER 风格 verdict + 校准指标）

参见调研背景：[`industry_research_background.md`](./industry_research_background.md)。
