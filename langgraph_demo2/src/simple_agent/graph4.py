from __future__ import annotations

#调用.env文件中的变量
import asyncio
import json
import os
import sys
from typing import Any

import dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool as Tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

_CURRENT_DIR = os.path.dirname(__file__)
if _CURRENT_DIR and _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

try:
    from .my_llm import get_llm
except ImportError:
    from my_llm import get_llm

dotenv.load_dotenv()
_mcp_client: MultiServerMCPClient | None = None

#这个用函数是为了避免重复创建MCPClient实例
def get_mcp_client() -> MultiServerMCPClient:
    global _mcp_client
    if _mcp_client is not None:
        return _mcp_client

    connections: dict[str, dict] = {}

    url = os.getenv("MCP_12306_URL")
    if url:
        connections["12306-mcp"] = {"transport": os.getenv("MCP_12306_TRANSPORT") or "sse", "url": url}

    url = os.getenv("MCP_CHART_URL")
    if url:
        connections["chart-mcp"] = {"transport": os.getenv("MCP_CHART_TRANSPORT") or "sse", "url": url}

    url = os.getenv("MCP_FETCH_URL")
    if url:
        connections["fetch-mcp"] = {"transport": os.getenv("MCP_FETCH_TRANSPORT") or "sse", "url": url}

    _mcp_client = MultiServerMCPClient(connections=connections, tool_name_prefix=True)
    return _mcp_client




#开始写工作流的内容，先写状态state，先继承MessagesState类，后面可以根据需要添加其他字段，如工具调用结果等
class State(MessagesState):
    pass


#在异步环境中创建graph,第一个节点定义一个节点函数，让LLM判断是否需要调用工具，第二个节点是工具调用节点
async def create_graph(*, llm: Any | None = None, tools: list[Tool] | None = None, checkpointer: Any | None = None):
    if tools is None:
        mcp_client = get_mcp_client()
        tools = []
        for server_name in ("12306-mcp", "chart-mcp", "fetch-mcp"):
            try:
                tools.extend(await mcp_client.get_tools(server_name=server_name))
            except Exception:
                continue
    builder = StateGraph(State)
    if llm is None:
        llm = get_llm()
    llm_plain = llm
    llm_with_tools = llm.bind_tools(tools)

    async def chatbot(state: State) -> dict:
        if state.get("tool_use_allowed", True) is False:
            response = await llm_plain.ainvoke(state["messages"])
        else:
            response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}
    builder.add_node("chatbot", chatbot)
    #使用langgraph自带的ToolNode来实现工具调用，路由函数在ToolNode内部实现，加一个包装函数，将工具调用结果转换为字符串格式
    async def _awrap_tool_call(
        request: Any,
        call_next: Any,
    ):
        result = await call_next(request)
        if isinstance(result, ToolMessage) and not isinstance(result.content, str):
            try:
                result.content = json.dumps(result.content, ensure_ascii=False)
            except Exception:
                result.content = str(result.content)
        return result

    tool_node = ToolNode(tools, awrap_tool_call=_awrap_tool_call)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "chatbot")
    #只有AImessage里包括tool_calls字段，才调用工具节点，否则直接结束,使用langgraph工具里的路由函数
    builder.add_conditional_edges("chatbot", tools_condition, ["tools", END])
    #从工具回到chatbot节点
    builder.add_edge("tools", "chatbot")
    #下面这个可以加入人工干预节点，比如中断工作流
    # 可以在工具节点调用前中断工作流，这个是对langgraph smith有用，没有指定检查点，因为在langgraph服务器里会指定checkpoint检查点
    #如果需要自定义内容的话，不能在studio里运行，需要在本地运行，自定义代码，手动本地运行的话需要加入checkpoint参数
    #使用内存检查点，也可以放到数据库postgresql里
    if checkpointer is None:
        checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["tools"]) 
    return graph

# agent = asyncio.run(create_graph())
#本地运行graph函数
async def run_graph():
    graph = await create_graph()
    #检查点需要会话ID,包含乘客id和线程id
    config = {"configurable": {"thread_id": "123456"}}

    def format_output(messages: list[BaseMessage]) -> str:
        parts: list[str] = []
        for m in messages:
            c = getattr(m, "content", "")
            if isinstance(c, str):
                parts.append(c)
            else:
                try:
                    parts.append(json.dumps(c, ensure_ascii=False))
                except Exception:
                    parts.append(str(c))
        return "\n".join(parts)

    def _get_pending_tool_calls() -> list[dict]:
        snapshot = graph.get_state(config)
        state_values = getattr(snapshot, "values", None) or {}
        last_msg = (state_values.get("messages") or [None])[-1]
        tool_calls = getattr(last_msg, "tool_calls", None) or []
        return list(tool_calls)

    def _refusal_tool_messages(tool_calls: list[Any], refuse_reason: str) -> list[ToolMessage]:
        tool_messages: list[ToolMessage] = []
        for i, call in enumerate(tool_calls):
            if isinstance(call, dict):
                tool_call_id = call.get("id") or call.get("tool_call_id") or call.get("call_id") or ""
            else:
                tool_call_id = getattr(call, "id", None) or getattr(call, "tool_call_id", None) or ""
            if not tool_call_id:
                tool_call_id = f"missing-tool-call-id-{i}"
            tool_messages.append(
                ToolMessage(
                    content=f"用户拒绝执行工具调用，原因：{refuse_reason}",
                    tool_call_id=str(tool_call_id),
                )
            )
        return tool_messages

    async def get_answer(refuse_reason: str) -> AIMessage:
        snapshot = graph.get_state(config)
        state_values = getattr(snapshot, "values", None) or {}
        messages: list[BaseMessage] = list(state_values.get("messages") or [])
        tool_calls = list(getattr(messages[-1], "tool_calls", None) or []) if messages else []
        if tool_calls:
            messages.extend(_refusal_tool_messages(tool_calls, refuse_reason))
        messages.append(
            HumanMessage(
                content=f"用户拒绝调用工具，原因：{refuse_reason}。请不要调用工具，直接给出回答。"
            )
        )
        llm_plain = get_llm()
        response = await llm_plain.ainvoke(messages)
        return AIMessage(content=str(getattr(response, "content", response)))

    async def execute_graph(user_input: str) -> dict:
        """执行工作流,这个是为了自定义中断的逻辑，全部都是异步，如果从中断点开始的话，要保证输入的是none，这样子才会继续执行"""
        if user_input.strip().lower() == "y":
            graph.update_state(
                config,
                {"tool_use_allowed": True, "tool_use_denied_reason": ""},
                as_node="chatbot",
            )
            return await graph.ainvoke(None, config=config)

        result = await graph.ainvoke({"messages": [HumanMessage(content=user_input)]}, config=config)
        last = result["messages"][-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if tool_calls:
            print("检测到将要调用工具。输入 y 继续执行工具；输入其他文字表示拒绝并给出原因。")
            return result
        return result
    
    #循环交互的方式执行工作流
    while True:
        user_input = input("请输入: ")
        normalized = user_input.strip()
        if normalized.lower() == "exit":
            break
        if normalized.lower() != "y":
            pending_calls = _get_pending_tool_calls()
            if pending_calls:
                ai_msg = await get_answer(normalized)
                tool_messages = _refusal_tool_messages(pending_calls, normalized)
                if tool_messages:
                    graph.update_state(config, {"messages": tool_messages}, as_node="tools")
                graph.update_state(
                    config,
                    {
                        "messages": [HumanMessage(content=normalized), ai_msg],
                        "tool_use_allowed": False,
                        "tool_use_denied_reason": normalized,
                    },
                    as_node="chatbot",
                )
                print(ai_msg.content)
                continue
        res = await execute_graph(normalized)
        print(format_output(res["messages"]))

#在本地运行
if __name__ == "__main__":
    asyncio.run(run_graph())
