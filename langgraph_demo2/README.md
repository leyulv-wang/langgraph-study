# langgraph_demo2
## graph.py：冷笑话生成-评估循环
## graph2.py：带 MCP 工具调用的小助手-异步
## graph3.py：带 MCP 工具调用的小助手-使用langgraph官方工具toolnode节点
## graph4.py：带 MCP 工具调用的小助手-使用langgraph官方工具toolnode节点，加入人工干预中断的内容
## graph5.py：带 MCP 工具调用的小助手-使用langgraph官方工具toolnode节点，加入人工干预中断的内容，使用库里的interrupt函数

## 项目思路，重点
### 线性设计流程（从需求到实现，LangGraph 通用架构）
下面用“因为 A，所以设计 a（a 的作用是什么）”的方式，把 graph5 的架构按工程化顺序串起来：

1) 因为需要一个“可编排的工作流”（而不是一段 if/else 代码），所以选择 StateGraph
- 作用：用节点（node）表达职责、用边（edge）表达顺序/分支，得到一个可运行、可观察、可扩展的流程。
- 对应实现：`StateGraph(State)`，再 `add_node/add_edge/add_conditional_edges`，最后 `compile()`。

2) 因为每个节点都需要共享“对话上下文”，所以状态以 MessagesState 为核心
- 作用：用 `state["messages"]` 贯穿整个图，让 LLM 和工具都在同一段消息历史上工作。
- 对应实现：`class State(MessagesState)`。

3) 因为要让模型“自己决定何时用工具”，所以需要把 tools 绑定到模型
- 作用：`llm.bind_tools(tools)` 让模型在需要时产出 `tool_calls`，把“工具选择”交给模型推理。
- 对应实现：`chatbot` 节点里选择调用 `llm_with_tools.ainvoke(messages)`。

4) 因为工具不是写死在代码里（要可替换、可扩展），所以引入 MCP 来动态提供工具
- 作用：把“工具来源”抽象为外部服务（MCP server），通过配置接入不同工具集（12306 / chart / fetch）。
- 对应实现：`.env` 配置连接信息；`get_mcp_client()` 构建 `MultiServerMCPClient`；`create_graph()` 拉取 tools 列表。

5) 因为工具调用是一个独立职责（执行、并发、格式化结果、错误处理），所以把它做成单独的工具节点
- 作用：把“执行 tool_calls → 产出 ToolMessage”封装成一个节点，chatbot 不需要关心调用细节。
- 对应实现：`BasicToolsNode.__call__` 读取最后一条 AIMessage 的 `tool_calls`，然后 `_execute_tool_calls` 并发执行并返回 `ToolMessage`。

6) 因为不是所有工具都需要人工确认，所以需要一个“可配置的中断规则”
- 作用：把“哪些工具要中断”写成配置（而不是散落在代码逻辑里），方便你学习和扩展。
- 对应实现：`_INTERRUPT_TOOL_NAME_PREFIXES`（tool name 前缀匹配），命中则在工具节点里触发 `interrupt(...)`。

7) 因为你希望“暂停后还能继续”，所以需要 interrupt + resume 的运行时控制
- 作用：`interrupt()` 让图在节点内部“暂停”；`Command(resume=...)` 把用户输入回填给图，让图从中断点继续执行。
- 对应实现：工具节点里 `response = interrupt(...)`；`run_graph()` 里检测返回 dict 的 `__interrupt__`，再 `graph.ainvoke(Command(resume=resume), ...)`。

8) 因为暂停/恢复需要状态可追踪（否则不知道从哪继续），所以必须使用 checkpointer + thread_id
- 作用：把当前线程的状态存下来，resume 时才能定位到正确的中断点继续跑。
- 对应实现：`MemorySaver()` + `config={"configurable": {"thread_id": "123456"}}`。

9) 因为“拒绝工具”不能破坏消息协议，也不能让模型继续反复要工具，所以需要两件事：补 ToolMessage + 写入拒绝状态
- 作用（补 ToolMessage）：当 AIMessage 里有 `tool_calls` 时，必须有对应 `tool_call_id` 的 ToolMessage，否则后续模型调用会 400。
- 作用（写入拒绝状态）：把 `tool_use_allowed=False`、`tool_use_denied_reason=...` 写入状态，让 chatbot 后续改用“纯模型”回答（不再生成 tool_calls）。
- 对应实现：拒绝时返回“拒绝 ToolMessage”并更新 `tool_use_allowed/tool_use_denied_reason`；`chatbot` 节点读取该标志决定用不用 tools。

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

## graph4.py：带 MCP 工具调用的小助手（加入人工干预中断）

### 核心目标
在 graph3 的“模型 ↔ 工具”的自动循环基础上，加上一个“人工确认”机制：

- 模型一旦产生 `tool_calls`，先不要立刻执行工具
- 先停下来，让用户决定：输入 `y` 才继续执行；否则输入拒绝原因，让模型不调用工具、直接给替代回答

### 为什么 graph4 需要 checkpointer + thread_id
`interrupt_before=["tools"]` 的中断/恢复依赖检查点保存状态：

- 第一次运行到工具节点前会中断，此时图必须把当前 `messages` 等状态写入 checkpointer
- 恢复时用 `graph.ainvoke(None, config=...)` 从上一次中断位置继续
- `config={"configurable": {"thread_id": "..."}}` 用来标识“这一次对话线程”的检查点归属，否则无法恢复到正确的那一次中断

graph4 默认用 `MemorySaver()`（内存检查点）方便本地跑通；以后也可以替换成 Postgres 等持久化 checkpointer。

### 工具节点为什么用 ToolNode + tools_condition
graph4 采用 LangGraph 内置的工具方案（比 graph2 自己写工具节点更省心）：

- `ToolNode(tools, awrap_tool_call=...)`：负责把 `tool_calls` 真正执行成 `ToolMessage`
- `tools_condition`：官方的路由函数，判断最后一条 AIMessage 是否包含 `tool_calls`
  - 有 `tool_calls` → 进入 `tools`
  - 没有 `tool_calls` → END

另外，`awrap_tool_call` 的作用是“兜底把工具返回值转成字符串”，避免某些工具返回 dict/list 时触发模型接口 400（因为 ToolMessage.content 必须是字符串）。

### 人工干预分支为什么要补 ToolMessage（关键坑）
当你“拒绝执行工具”时，历史里依然存在一条带 `tool_calls` 的 AIMessage。
OpenAI 协议有硬性要求：

- 如果某条 assistant 消息带 `tool_calls`
- 后面必须紧跟每个 `tool_call_id` 对应的 `ToolMessage`

否则下一次再调用模型，就会报错：
`An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'`

所以 graph4 在拒绝分支里会为每个 pending 的 `tool_call_id` 追加一条“拒绝执行”的 `ToolMessage`，把对话历史修正成合法结构，然后再让模型生成“不用工具的替代回答”。

### 本地运行方式（run_graph）
`run_graph()` 做了一个最小 CLI 交互循环：

1. 输入正常问题 → 运行图
2. 如果检测到 `tool_calls` → 提示“输入 y 执行工具，否则输入拒绝原因”
3. 输入 `y` → `graph.ainvoke(None, config=...)` 从中断点继续执行工具
4. 输入其他文字 → 走拒绝分支：补 ToolMessage → 让模型直接回答 → 写回状态，继续下一轮对话

## graph5.py：用 interrupt() 对“特定工具”做人工中断（工程化拆解）

### 你要实现的能力（需求）
在“模型会自动决定调用工具”的前提下，你希望对某些敏感/昂贵/有风险的工具做人工确认：

- 命中特定工具 → 先暂停（interrupt）→ 用户输入 y 才执行
- 用户拒绝 → 不执行工具，但把“拒绝信息”写进状态，并且后续不要再走工具调用


### 这份代码需要哪些部件（模块化视角）
把 graph5 当成一个小框架来看，它由 6 个部件拼起来：

1) 配置层（Config）
- `.env`：提供 MCP 服务地址、模型配置等
- `_INTERRUPT_TOOL_NAME_PREFIXES`：定义“哪些工具需要人工确认”（通过 tool name 前缀匹配）

2) 集成层（Integration）
- `get_mcp_client()`：把 `.env` 里的连接信息组装成 `MultiServerMCPClient`，并做模块级缓存复用
- `create_graph()`：从多个 server 拉取 tools 列表，交给模型绑定

3) 状态层（State）
- `State(MessagesState)`：核心是 `messages`（对话上下文）
- 额外状态字段（工程上建议显式化）：`tool_use_allowed` / `tool_use_denied_reason`
  - `tool_use_allowed=False`：表示用户已拒绝工具，本线程后续应禁用工具
  - `tool_use_denied_reason`：记录拒绝原因，方便后续回答引用

4) 编排层（Orchestration）
- `StateGraph(State)`：把节点和边组织起来
- `MemorySaver()`：作为 checkpointer，确保 interrupt 后可以 resume
- `config={"configurable": {"thread_id": "..."} }`：为同一线程的恢复提供定位

5) 节点层（Nodes）
- `chatbot`：调用 LLM 生成 AIMessage
  - `tool_use_allowed=False` 时用“纯模型”（不绑定 tools）回答，确保不会再产生 tool_calls
  - 否则用 `llm.bind_tools(tools)` 让模型按需产生 tool_calls
- `tool_node(BasicToolsNode)`：执行工具调用（并且负责在必要时触发 interrupt）

6) 控制层（Control Flow）
- `route_tools_func`：检查最后一条 AIMessage 是否有 `tool_calls`
  - 有 → 进入 `tool_node`
  - 无 → END
- `run_graph()`：负责处理 interrupt 的“暂停/恢复”交互

### 运行时的数据流（从 START 到 END）
整体就是一个循环：

1. `START → chatbot`
2. `chatbot` 产出 AIMessage
3. `route_tools_func` 分支：
   - 没有 `tool_calls` → `END`
   - 有 `tool_calls` → `tool_node`
4. `tool_node` 做三种分支：
   - 不需要中断（不匹配前缀）→ 直接执行工具 → 返回 ToolMessage
   - 需要中断且用户输入 y → 执行工具 → 返回 ToolMessage
   - 需要中断且用户拒绝 → 不执行工具 → 返回“拒绝 ToolMessage”，并写入 `tool_use_allowed=False`
5. `tool_node → chatbot`，模型看到 ToolMessage 后继续生成最终回答/继续请求下一轮工具

### interrupt 的关键点：为什么需要 run_graph 循环处理 __interrupt__
`interrupt(value)` 不会像 `input()` 一样直接在 Python 里阻塞等待，它会让图返回一个特殊字段：

- 返回值 dict 里包含 `__interrupt__`
- 你在 `run_graph()` 里检查到它，就提示用户输入
- 再用 `graph.ainvoke(Command(resume=用户输入), config=...)` 把输入“喂回去”，让图从中断点继续跑

### 拒绝工具为什么要生成 ToolMessage（避免协议错误）
当 AIMessage 里有 `tool_calls` 时，消息历史里必须出现对应 `tool_call_id` 的 ToolMessage。
所以即使你拒绝执行工具，也要生成“拒绝执行”的 ToolMessage，把对话历史补齐成合法结构。
