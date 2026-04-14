#引用my_llm.py中的llm实例
import os
import sys

from typing import Literal, TypedDict
from pydantic import BaseModel, Field

_CURRENT_DIR = os.path.dirname(__file__)
if _CURRENT_DIR and _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

try:
    from .my_llm import get_llm
except ImportError:
    from my_llm import get_llm
from langgraph.graph import START, END, StateGraph
#定义状态类作为LangGraph的状态,做一个笑话评估的状态，包括冷笑话，主题，建议，和是否幽默。
class State(TypedDict):
    joke: str
    topic: str
    feedback: str
    funny_or_not: str
    attempt: int
    max_attempts: int

#定义结构化输出模型，用于LLM评估冷笑话反馈
class Feedback(BaseModel):
    """使用此工具来结构化你的响应"""
    grade: Literal["funny", "not funny"] = Field(description="判断笑话是否幽默，返回funny或not funny",
        example=["funny", "not funny"])
    feedback: str = Field(description="对笑话的建议", example=["可以加入意外结局"])


#定义一个节点函数，generator_func，用于生成冷笑话
def generator_func(state: State) -> State:
    """
    生成一个冷笑话的节点
    """
    #用prompt提示词，提示词里包括feedback和topic，生成一个冷笑话，如果没有建议，就根据主题直接生成一个冷笑话
    feedback = state.get("feedback", "")
    topic = state.get("topic", "")
    attempt = int(state.get("attempt", 0)) + 1
    prompt = (
        f"请根据以下建议和主题生成一个冷笑话：{feedback}\n主题：{topic}"
        if feedback
        else f"请根据以下主题生成一个冷笑话：{topic}"
    )
    llm = get_llm()
    response = llm.invoke(prompt)
    joke = getattr(response, "content", response)
    #返回生成的冷笑话
    # print(joke)
    return {"joke": joke, "attempt": attempt}
    #还可以用output_parsers来解析返回的冷笑话
    #chain = llm | StrOutputParser() 
    #resp = chain.invoke(prompt)
    #return {"joke": resp}

#生成评估函数，作为评估节点
def evaluator_func(state: State) -> State:
    """评估generator节点生成的冷笑话"""
    prompt = (
        "你是一个严格的冷笑话评审。"
        "请判断下面这条冷笑话是否幽默，并给出具体改进建议。"
        f"\n主题：{state.get('topic', '')}\n笑话：{state.get('joke', '')}"
    )
    llm = get_llm()
    last_error: Exception | None = None
    for method in ("function_calling", "json_mode", "json_schema"):
        structured_llm = llm.with_structured_output(Feedback, method=method)
        for _ in range(2):
            try:
                result = structured_llm.invoke(prompt)
                grade = getattr(result, "grade", None) or result["grade"]
                feedback = getattr(result, "feedback", None) or result["feedback"]
                if grade not in ("funny", "not funny"):
                    raise ValueError("Invalid grade")
                feedback = str(feedback).strip() or "请给出更具体的改进建议。"
                return {"feedback": feedback, "funny_or_not": grade}
            except Exception as e:
                last_error = e
                continue
    return {
        "feedback": (
            f"评估失败（{type(last_error).__name__ if last_error else 'UnknownError'}："
            f"{str(last_error)[:200] if last_error else ''}），请给出更具体的改进建议。"
        ),
        "funny_or_not": "not funny",
    }

#定义一个路由函数，用于判断是否重新生成冷笑话
def route_func(state: State) -> str:
    """动态路由函数，根据评估结果判断是否重新生成冷笑话"""
    grade = state.get("funny_or_not", "not funny")
    if grade == "funny":
        return END
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    if attempt >= max_attempts:
        return END
    return "generator"
    
#构建一个工作流，开始到生成节点，然后到评估节点，评估节点返回评估结果，如果不行就重新生成，知道通过评估最终输出结果
builder = StateGraph(State)
#添加开始节点
builder.add_edge(START, "generator")
#添加生成节点
builder.add_node("generator", generator_func)
#添加评估节点
builder.add_node("evaluator", evaluator_func)
#添加边，从生成节点到评估节点
builder.add_edge("generator", "evaluator")
#添加边，从评估节点开始是有条件的，结果是funny，就返回结果，到结束节点，否则返回生成节点，重新生成冷笑话，用路由函数来判断
builder.add_conditional_edges("evaluator", route_func, ["generator", END])

graph = builder.compile()
