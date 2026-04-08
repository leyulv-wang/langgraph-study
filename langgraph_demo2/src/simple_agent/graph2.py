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

#写一个异步的工具调用类，这个是自己写的，实际上可以使用langgraph提供的toolnode来实现，不过自定义不方便
class BasicToolsNode:
    """
    异步工具节点，用于并发执行AIMessage中请求的工具调用

    功能:
        1.接收工具列表并建立名称索引
        2.并发执行消息中的工具调用请求
        3.自动处理同步/异步工具适配调用类
    """
    def __init__(self, tools: list[Tool]):
        """
        初始化工具节点
        Args:
            tools: 工具列表，每个工具都有一个唯一的名称，包含name属性
        """
        self.tools_by_name = {tool.name: tool for tool in tools}
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, list[ToolMessage]]:
        """
        异步调用入口,有异步调用优先异步调用,否则同步调用
        Args:
            state:输入字典，需包含"messages"字段
        Returns:
            包含ToolMessage列表的字典
        Raises:
            ValueError:当输入无效时抛出
        """
        #1.检查输入字典是否包含"messages"字段
        if not (messages := state.get("messages")) or not isinstance(messages, list):
            raise ValueError("输入字典必须包含'messages'字段，且该字段必须是一个列表")
        message = messages[-1]
       
        #2.并发执行工具调用
        tool_calls = getattr(message, "tool_calls", None) or []
        outputs = await self._execute_tool_calls(tool_calls)
        return {"messages": outputs}
    
    async def _execute_tool_calls(self, tool_calls: list[Dict]) -> list[ToolMessage]:
        """
        异步执行工具列表调用
        Args:
            tool_calls: 工具调用列表，每个工具调用都有一个唯一的工具名称和参数
        Returns:
            包含工具调用结果的ToolMessage列表
        """
        async def _invoke_tool(tool_call: Dict) -> ToolMessage:
            """
            异步调用单个工具
            Args:
                tool_call: 工具调用字典，包含工具名称和参数
            Returns:
                包含工具调用结果的ToolMessage
            Raises:
                KeyError: 当工具名称不存在时抛出
                RuntimeError: 当工具调用失败时抛出
            """
            tool_name = tool_call.get("name")
            if not tool_name and isinstance(tool_call.get("function"), dict):
                tool_name = tool_call["function"].get("name")
            if not tool_name:
                raise KeyError("Missing tool name in tool_call")

            tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id") or tool_call.get("call_id") or tool_name

            args = tool_call.get("args")
            if args is None:
                args = tool_call.get("arguments")
            if args is None and isinstance(tool_call.get("function"), dict):
                args = tool_call["function"].get("arguments")
            if args is None:
                args = {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"input": args}
            if not isinstance(args, dict):
                args = {"input": args}

            tool = self.tools_by_name.get(tool_name)
            if tool is None:
                raise KeyError(f"Tool not found: {tool_name}")

            try:
                result = await tool.ainvoke(args)
            except Exception as e:
                raise RuntimeError(f"Tool call failed: {tool_name}") from e

            if isinstance(result, str):
                content = result
            else:
                try:
                    content = json.dumps(result, ensure_ascii=False)
                except Exception:
                    content = str(result)
            return ToolMessage(content=content, tool_call_id=str(tool_call_id), name=tool_name)

        if not tool_calls:
            return []

        tasks = [_invoke_tool(tc) for tc in tool_calls]
        try:
            return await asyncio.gather(*tasks) #gather表示并发执行所有任务
        #并发过程中如果报错，也抛出异常
        except Exception as e:
            raise RuntimeError(f"Error in tool call: {e}") from e

#开始写工作流的内容，先写状态state，先继承MessagesState类，后面可以根据需要添加其他字段，如工具调用结果等
class State(MessagesState):
    pass

#定义路由函数，route_tools_func，根据消息是否包含tool_calls字段，判断是否调用工具节点
def route_tools_func(state: State) -> str:
    """
    路由函数，根据AImessage消息是否包含tool_calls字段，判断是否调用工具节点
    Args:
        state: 状态字典，需包含"messages"字段
    Returns:
        路由目标节点名称，"tool_node"或"end"
    """
    message = state["messages"][-1]
    if hasattr(message, "tool_calls") and message.tool_calls:
        return "tool_node"
    return END

#在异步环境中创建graph,第一个节点定义一个节点函数，让LLM判断是否需要调用工具，第二个节点是工具调用节点
async def create_graph():
    mcp_client = get_mcp_client()
    tools = await mcp_client.get_tools()
    builder = StateGraph(State)
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    async def chatbot(state: State) -> dict:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}
    builder.add_node("chatbot", chatbot)
    tool_node = BasicToolsNode(tools)
    builder.add_node("tool_node", tool_node)
    builder.add_edge(START, "chatbot")
    #只有AImessage里包括tool_calls字段，才调用工具节点，否则直接结束
    builder.add_conditional_edges("chatbot", route_tools_func, ["tool_node", END])
    #从工具回到chatbot节点
    builder.add_edge("tool_node", "chatbot")
    graph = builder.compile()
    return graph

agent = asyncio.run(create_graph())
