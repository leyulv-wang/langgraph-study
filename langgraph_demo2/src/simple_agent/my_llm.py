#调用env_utils.py中的变量
try:
    from .env_utils import API_KEY, BASE_URL, MODEL
except ImportError:
    from env_utils import API_KEY, BASE_URL, MODEL
import os
from langchain_openai import ChatOpenAI

_llm: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    global _llm
    if _llm is not None:
        return _llm

    api_key = API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing API key: set API_KEY or OPENAI_API_KEY in environment/.env")

    kwargs = {"api_key": api_key}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    if MODEL:
        kwargs["model"] = MODEL

    _llm = ChatOpenAI(**kwargs)
    return _llm

#测试连接，只在这个代码文件中测试，不建议在其他文件中测试，因为会消耗API调用次数
# result = get_llm().invoke("你好")
# print(getattr(result, "content", result))
