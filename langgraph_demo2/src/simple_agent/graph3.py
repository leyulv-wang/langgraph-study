from __future__ import annotations

#调用.env文件中的变量
import asyncio
import json
import os
import sys
from typing import Any, Dict

import dotenv
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool as Tool
from langchain_mcp_adapters.client import MultiServerMCPClient
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
async def create_graph():
    mcp_client = get_mcp_client()
    tools: list[Tool] = []
    for server_name in ("12306-mcp", "chart-mcp", "fetch-mcp"):
        try:
            tools.extend(await mcp_client.get_tools(server_name=server_name))
        except Exception:
            continue
    builder = StateGraph(State)
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    async def chatbot(state: State) -> dict:
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
    graph = builder.compile()
    return graph

agent = asyncio.run(create_graph())
