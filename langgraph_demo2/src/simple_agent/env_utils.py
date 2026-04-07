#调用.env文件中的变量
import os
from typing import Any, Dict
import asyncio
import json
import dotenv
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool as Tool
from langchain_mcp_adapters.client import MultiServerMCPClient

dotenv.load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("api_key")
BASE_URL = os.getenv("BASE_URL") or os.getenv("base_url")
MODEL = os.getenv("MODEL") or os.getenv("model")


