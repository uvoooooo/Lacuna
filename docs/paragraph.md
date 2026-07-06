# Idea: 基于知识图谱的叙述审计——听没说出来的部分

Have you ever experienced this: You listen to a narrative. Although the speaker is trying to illustrate what he has suffered, you discover the fact that he is actually more defective in this story. Given that his narrative is self-supportive, why can you find that?

The very core of this idea is: you should not only listen to what he has said, but pay more attention to what is missing in this whole picture. That is, listen to what hasn't been involved.

## 主思想

这个 repo 的主线是一条 **图谱为中心** 的叙述审计流水线：

1. **叙述 → 知识图谱**：把一段话（narrative）抽取成知识图谱——实体、事件、时间、关系，保留叙事顺序与时间锚点。
2. **本体推理，补全不显然的节点**：叙述里的每个事件在本体（ontology）上都蕴含着一组"必然存在的角色与前提"。例如"被开除"这个事件必然蕴含：开除方、开除理由、在此之前存在的劳动关系、补偿的处理方式。这些节点即使原文没提，也应该被推理出来并标记为"推断"（inferred），与原文明说的（stated）区分开。
3. **冲突识别**：在图上找矛盾——时间线冲突（叙事顺序自相矛盾）、互斥关系（同一对实体间出现不能共存的关系）、同一实体的属性不一致，以及陈述之间的语义矛盾。
4. **要素识别（图空缺检测）**：对照本体，检查每个事件"必要角色"是否在图中出现。**关键要素的空缺本身就是一种信号**——一个自洽的叙述如果系统性地缺失了对己方不利的要素（起因、对方视角、第三方记录），这个空缺的形状比说出来的内容更能说明问题。

一句话：**不判断谁对谁错，而是把叙述画成一张图，然后审计这张图——图里推理出了什么、图里哪里矛盾、图里哪些必要的位置是空的。**
