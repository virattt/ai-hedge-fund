# 一 上手运行起来(学是为了用)
## 新增：生产者-消费者&解释：数据-行为
## 不要犹豫，越快进入得到反馈越快
1. 主流程里新增一个分析师，在全流程的状态结构里新增一个字段
2. 消费新增的内容
3. 解释核心用到的数据结构字段哪里写入，哪里读取的，最核心的action 是怎么触发的

# 二 关于agent 输出的结果如何合并显示到命令行的
- dag state 约定列表追加和map key 覆盖合并
- graph 图读取message 显示到命令行
```text
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, any], merge_dicts]
    metadata: Annotated[dict[str, any], merge_dicts]
```
