# Roadmap

## Now — MVP (v0.1)
- [x] Shared-state multi-agent pipeline
- [x] 5 agents: ClaimSplitter / Label / MissingContext / Evidence / Report
- [x] LLM-driven labeling (no hardcoded lexicons; requires OpenRouter key)
- [x] Pluggable search backend (offline mock)
- [x] CLI + JSON output
- [x] src layout, packaging, CI, tests

## Next — Reliability (v0.2)
- [ ] **Calibration Agent** — 把规则置信度替换为校准后的概率
- [ ] **Source Credibility Agent** — 来源可信度评级，喂给证据打分
- [ ] **Contradiction Agent** — claim 之间 / claim 与证据的矛盾检测
- [ ] Real search backend (web / vector DB / 用户上传材料)
- [ ] Better Chinese claim segmentation (LLM-first, 规则兜底)

## Later — Product (v0.3+)
- [ ] **Human Review Agent** — 低置信度样本进入人工复核
- [ ] **Domain Agents** — 法律 / 保险 / 客服 / 新闻 各一套规则与 schema
- [ ] B2B Copilot 形态：API + 报告导出 (ClaimReview 结构化)
- [ ] 评测集与回归（FEVER 风格 verdict + 校准指标）

参见调研背景：[`industry_research_background.md`](./industry_research_background.md)。
