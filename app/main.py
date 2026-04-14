from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.router import api_router
from app.api.middlewares import setup_middlewares
from app.db.session import async_engine
from app.db.base import Base
import app.models  # 导入模型，确保 Base.metadata 能够注册到表
# 应用生命周期管理函数
# 该函数用于在 FastAPI 应用启动时和关闭时执行一些操作。
# 1. 应用启动时创建数据库表
# 2. 应用关闭时释放数据库引擎连接
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时执行：创建数据库表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) # 使用base类的元数据来创建所有数据库表
    yield # 函数不会结束，而是暂停在这里，等待后续继续执行，把函数切成启动阶段 + 关闭阶段，
    # 我们关闭应用就会执行关闭阶段的操作，这个逻辑是内置的，不需要我们手动实现
    # 应用关闭时执行：释放数据库引擎连接
    await async_engine.dispose()

app = FastAPI(title="FastAPI Study", lifespan=lifespan)
setup_middlewares(app)
app.include_router(api_router, prefix="/api")


# @app.get("/")
# def root() -> dict:
#     return {"message": "Hello, FastAPI"}

# #写一个/hello 路径，返回你好
# @app.get("/hello")
# async def hello() -> dict:
#     return {"message": "你好"}
        
# #写一个带参数的路径，返回book_id的内容
# @app.get("/book/{id}")
# async def get_book(id: int) -> dict:
#     return {"book_id": id, "book_name": "Python FastAPI Study"}
