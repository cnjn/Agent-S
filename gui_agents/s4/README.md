# Agent-S4

基于 LangChain + LangGraph 重构的 Agent-S，核心特性：

- LangGraph `StateGraph` 驱动 UI 循环，使用 `interrupt` 将动作执行权交还 CLI，可视化 workflow；
- 直接复用 S3 的 OSWorldACI 与 CodeAgent 逻辑，通过 LangChain ChatModel 生成桌面操作代码；
- 所有 UI 动作与 `call_code_agent` 均封装为 LangChain `StructuredTool`，Planner 通过 tool calling 触发，彻底 LangChain 化；
- `MemorySaver` checkpoint 维护消息历史，LangChain Prompt 统一管理系统提示；
- CLI 仍提供权限确认、暂停/恢复等调试手势，执行动作前会弹窗确认。

## 运行

```bash
uv pip install -r requirements.txt
uv run python -m gui_agents.s4.cli_app \
  --provider openai \
  --model gpt-4o \
  --ground_provider openai \
  --ground_model gpt-4o-mini \
  --ground_url https://api.openai.com/v1 \
  --grounding_width 1280 \
  --grounding_height 720
```

## 结构

- `agent.py`：封装 LangGraph 图与线程管理；
- `graph/workflow.py`：StateGraph 节点（observe/plan/act/decide）以及 interrupt 协议；
- `models.py`：根据 provider 构建 LangChain ChatModel；
- `prompts.py`：复用 S3 procedural memory；
- `cli_app.py`：主循环、权限管理、执行反馈。

