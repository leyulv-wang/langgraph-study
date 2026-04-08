# langgraph_demo2
## graph.py：冷笑话生成-评估循环
## graph2.py：带 MCP 工具调用的小助手-异步
## graph3.py：带 MCP 工具调用的小助手-使用langgraph官方工具toolnode节点
## graph4.py：带 MCP 工具调用的小助手-使用langgraph官方工具toolnode节点，加入人工干预中断的内容
这个目录包含两个独立的 LangGraph 工作流示例：

综合来说，graph的设计流程思路：
    1. 设计状态字典的结构，包括输入、中间变量、输出等等。
    2.设计多个节点，每个节点负责不同的任务。
    3.设计工具节点，负责调用工具。如果需要mcp，需要设计mcp节点。mcp也算是工具节点
    4.设计边，有些条件边需要通过路由函数来判断是否跳转。
    5. 设计最终的节点，`结束工作流。
    6. 导出 LangGraph 对象，用于执行。

- `src/simple_agent/graph.py`：冷笑话生成 + 评估 + 循环改写（直到通过或达到最大次数）
- `src/simple_agent/graph2.py`：一个带工具调用的小助手（MCP：网页抓取 / 12306 车票 / 图表生成），包含“模型判断要不要调用工具 → 工具执行 → 回到模型”的循环

## graph.py：冷笑话生成-评估循环

### 核心目标
输入一个主题 `topic`，让模型生成冷笑话 `joke`，再用评估器判断是否幽默，并给出改进建议 `feedback`。如果不幽默，则带着建议重新生成，最多循环 `max_attempts` 次。

### 状态（State）
工作流用一个状态字典在节点之间传递数据（TypedDict）：

- `topic`：主题（外部输入，建议必填）
- `joke`：生成的冷笑话（generator 输出）
- `feedback`：评估建议（evaluator 输出，同时也是下一轮 generator 的输入）
- `funny_or_not`：评估结果（`funny` / `not funny`）
- `attempt`：当前第几次生成（每轮 +1）
- `max_attempts`：最多允许生成/评估循环次数（默认 3）

### 流程从哪里开始，到哪里结束
整体执行顺序（从 START 到 END）：

1. START → `generator`
2. `generator` → `evaluator`
3. `evaluator` 根据 `route_func` 的判断：
   - `funny_or_not == "funny"` → END
   - `funny_or_not == "not funny"` 且 `attempt < max_attempts` → 回到 `generator`
   - `attempt >= max_attempts` → END（即使还没评为 funny，也会停止，避免无限循环和无限消耗调用次数）

### 关键函数分别在做什么
开始的时候设计好状态字典的结构，包括输入、中间变量、输出。

- `generator_func(state)`，把状态字典输入，输出状态字典（包含 `joke` 和 `attempt`）
  - 读取：`topic`、`feedback`、`attempt`
  - 行为：拼 prompt（有 feedback 就带反馈改写；没有就直接按 topic 生成）
  - 写入：`joke`、`attempt`

- `Feedback(BaseModel)`
  - 作用：定义评估器的结构化输出 schema（`grade` + `feedback`）
  - 目的：让评估结果稳定可解析，避免出现“模型随便写一段话”导致后续路由不稳定

- `evaluator_func(state)`
  - 读取：`topic`、`joke`
  - 行为：
    - 使用 `with_structured_output(Feedback)` 让模型按 `Feedback` 的结构返回
    - 兼容不同模型/代理对结构化输出协议的支持（依次尝试 `function_calling` / `json_mode` / `json_schema`）
    - 每种方法失败会重试，最终失败则返回兜底（`not funny` + 提示）
  - 写入：`funny_or_not`、`feedback`

路由函数，自己设计，根据 `funny_or_not` 和 `attempt` 决定是否跳 END 或回 generator。
- `route_func(state)`
  - 读取：`funny_or_not`、`attempt`、`max_attempts`
  - 作用：决定 `evaluator` 的下一跳（去 END 或回 generator）

### 最终导出 LangGraph 对象，用于执行
`graph = builder.compile()` 生成可运行的 LangGraph 对象。

## graph2.py：带 MCP 工具调用的小助手

### 核心目标
让模型能在对话中按需调用工具（tools），例如：

- 网页抓取（fetch MCP）
- 12306 车票查询（12306 MCP）
- 图表生成（chart MCP）

整体模式是“模型先决定是否需要工具 → 如果需要就执行工具 → 把工具结果作为 ToolMessage 回给模型 → 模型继续回答/再次决定是否需要工具”。

### 工具从哪里来（MCP）
在 `.env` 中配置 MCP server 的连接信息（SSE）：

- `MCP_12306_URL` / `MCP_12306_TRANSPORT`
- `MCP_CHART_URL` / `MCP_CHART_TRANSPORT`
- `MCP_FETCH_URL` / `MCP_FETCH_TRANSPORT`

`get_mcp_client()` 用这些环境变量构建 `MultiServerMCPClient`，并通过模块级缓存避免重复创建 client（减少握手/连接开销）。

### 流程从哪里开始，到哪里结束
整体执行顺序（从 START 到 END）：

1. START → `chatbot`
2. `chatbot`（模型节点）生成一条 AIMessage
3. `route_tools_func` 检查最后一条 AIMessage 是否包含 `tool_calls`
   - 有 `tool_calls` → 跳到 `tool_node`
   - 没有 `tool_calls` → END
4. `tool_node` 执行所有工具调用，产生 `ToolMessage` 列表
5. `tool_node` → `chatbot`（把工具结果交给模型继续推理/回答）
6. 重复 2~5，直到模型不再请求工具，流程结束

### 关键函数分别在做什么
同样，开始的时候设计好状态字典的结构，包括输入、中间变量、输出。
    设计最开始的节点，`chatbot`，负责生成一条 AIMessage。
- `chatbot(state)`
  - 输入：`state["messages"]`（对话上下文）
  - 行为：`llm.bind_tools(tools)` 后调用 `ainvoke`，让模型在需要时自动生成 `tool_calls`
  - 输出：把新生成的 AIMessage 追加到 `messages` 中

同样的，路由函数，自己设计，根据最后一条消息是否包含 `tool_calls` 决定是否跳工具执行节点。
- `route_tools_func(state)`
  - 读取：最后一条消息的 `tool_calls`
  - 作用：决定是否进入工具执行节点

这是工具执行基础系欸但，要得到toolmessage，需要执行工具。
`BasicToolsNode` 是一个 LangGraph 节点，负责执行工具调用，把结果包装成 `ToolMessage` 列表。
`BasicToolsNode` 会根据 `tool_calls` 列表，调用对应的工具，把工具返回值（可能是异步的）转换为字符串，最后把字符串写入 `ToolMessage.content`。
整个大的异步函数里包括了异步调用单个工具的函数，最终可以根据 `tool_calls` 列表，并发调用多个工具。
- `BasicToolsNode(tools)`
  - 作用：把“模型请求的 tool_calls”真正执行掉，并把结果包装成 `ToolMessage`
  - 关键点：
    - 支持并发执行（`asyncio.gather`）
    - 会把工具返回值强制转换为字符串写入 `ToolMessage.content`（避免把 list/dict 直接塞进 content 导致模型接口 400）

### 最终导出 LangGraph 对象，用于执行
`agent = asyncio.run(create_graph())` 导出编译后的图对象，供 `langgraph.json` 引用加载。
