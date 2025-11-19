# 使用 LangChain/LangGraph 重写 gui_agents/s3

## 目标描述
使用 LangChain 和 LangGraph 重写现有的 `gui_agents/s3` 代理，以利用其生态系统（"造轮子"），同时保留原始代理的核心逻辑和"grounding"（落地/基础）能力。

## 需要用户审查
> [!IMPORTANT]
> 此重写涉及将自定义的 `LMMAgent` 和 `LMMEngine` 类替换为标准的 LangChain `ChatModel` 实现（例如 `ChatOpenAI`, `ChatAnthropic`）。这假设用户可以通过标准的 LangChain 提供商访问这些模型。

## 建议的更改

### `gui_agents/s3_langgraph`
为 LangGraph 实现创建一个新目录。

#### [NEW] [state.py](file:///e:/tmp/Agent-S/gui_agents/s3_langgraph/state.py)
定义 `AgentState` TypedDict。
- `messages`: List[BaseMessage]
- `screenshot`: str (Base64)
- `instruction`: str
- `notes`: List[str]
- `scratchpad`: Dict

#### [NEW] [utils.py](file:///e:/tmp/Agent-S/gui_agents/s3_langgraph/utils.py)
调整 `OSWorldACI` 以配合 LangChain 工作。
- 从 `gui_agents/s3/agents/grounding.py` 复制 `OSWorldACI` 逻辑。
- 将 `LMMAgent` 替换为 `BaseChatModel`。
- 使用 `BaseChatModel.invoke` 实现 `generate_coords` 和 `generate_text_coords`。
- 保留 `agent_action` 装饰器和工具方法（`click`, `type` 等）。
- 保留 `create_pyautogui_code` 逻辑。

#### [NEW] [nodes.py](file:///e:/tmp/Agent-S/gui_agents/s3_langgraph/nodes.py)
定义图节点。
- `worker_node`:
    - 使用 `PROCEDURAL_MEMORY`（从现有代码导入）构建提示。
    - 调用 `ChatModel`。
    - 解析输出以查找代码块。
- `execution_node`:
    - 获取 `worker_node` 的代码。
    - 使用适配后的 `OSWorldACI` 实例通过 `exec()` 执行代码。
    - 捕获 stdout/stderr。
    - 将结果返回给状态。

#### [NEW] [graph.py](file:///e:/tmp/Agent-S/gui_agents/s3_langgraph/graph.py)
构建 StateGraph。
- 节点: `worker`, `execution`。
- 边: `worker` -> `execution` -> `worker`（循环直到 DONE/FAIL）。

#### [NEW] [main.py](file:///e:/tmp/Agent-S/gui_agents/s3_langgraph/main.py)
运行 LangGraph 代理的 CLI 入口点。

## 验证计划

### 自动化测试
- 我将创建一个简单的测试脚本来初始化图并运行模拟任务（如果可以在没有真实 GUI 环境的情况下进行，否则我将依赖手动验证）。

### 手动验证
- 使用简单的查询运行代理（例如，"打开计算器"）。
- 验证它是否截取屏幕截图、生成计划、执行操作并与桌面交互。
