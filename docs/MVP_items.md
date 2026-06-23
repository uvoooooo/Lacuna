**agent pipeline 是最自然的实现方式**。核心不是一个大模型直接打分，而是把“判断一段表述”拆成多道工序。

一个可行 pipeline：

```text
Input 文本
  ↓
1. Segment / Claim Agent
把原文拆成原子陈述：
事实、时间、地点、行为、损害、归因、评价
  ↓
2. Label Agent
给每个片段打标签：
事实陈述 / 主观评价 / 推断 / 情绪化词 / 引用转述 / 缺失上下文
  ↓
3. Missing Context Agent
判断为了评估这句话，还缺什么：
起因、证据、时间地点、第三方记录、反方视角、后续处理
  ↓
4. Search / Evidence Agent
只对“可核查事实”去搜证据：
网页、新闻、数据库、内部文档、用户上传材料
  ↓
5. Evidence Matching Agent
判断证据和 claim 的关系：
支持 / 反驳 / 部分支持 / 无关 / 信息不足
  ↓
6. Confidence Calibration Agent
综合：
证据质量、来源可信度、时间新鲜度、claim 模糊度、模型分歧
输出置信度
  ↓
7. Report Agent
生成用户可读报告：
哪些可靠、哪些只是推断、哪些没说、应该追问什么
```

我会把它做成**多 agent + shared state**，而不是完全串行聊天。中间状态可以是这种结构：

```json
{
  "claim": "对方追了我们二十分钟",
  "type": "fact_claim",
  "checkability": "medium",
  "evidence_status": "not_enough_info",
  "confidence": 0.54,
  "missing_context": [
    "冲突起因",
    "是否有行车记录仪",
    "是否报警",
    "是否有第三方目击"
  ],
  "suggested_questions": [
    "这件事是怎么开始的？",
    "有没有报警或保险记录？"
  ]
}
```

关键是：**Search Agent 不应该一开始就搜所有东西**。它只负责能被外部证据验证的 claim。像“路怒症疯子”这种，应该先被 Label Agent 标成“情绪化定性/主观判断”，而不是拿去搜索“这个人是不是疯子”。

我会建议 MVP 先做 5 个 agent：

1. **Claim Splitter**
2. **Label Agent**
3. **Missing Context Agent**
4. **Evidence Agent**
5. **Final Judge / Report Agent**

后面再加：

* Calibration Agent
* Source Credibility Agent
* Contradiction Agent
* Human Review Agent
* Domain Agent：法律、保险、客服、新闻分别一套规则

产品叫：

**Narrative Audit Pipeline**
或者中文：**表述审阅引擎 / 叙述证据分析器**。

核心卖点是：

> 不判断谁对谁错，而是把一段话拆成：它说了什么、暗示了什么、没说什么、证据够不够。
