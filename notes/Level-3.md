# 多个agent 的设计实现机制

## 过程描述
共享总线机制：所有 agent 都读写同一个 state["data"]["analyst_signals"] 字典，用 agent_id 做 key，ticker 做二级 key。

异步并行：LangGraph 自动并行运行所有 analyst（都连接到 start_node，相互间无依赖）。

两层决策：

确定性层（Risk + Portfolio 中的 compute_allowed_actions）：确保不违反现金/保证金/流动性约束
模型决策层（LLM）：在合法动作集合内选最优 action

## 多agent 冲突合并策略

