import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DATABASE = os.getenv("PG_DATABASE", "langgraph_db")

# 1. 创建 PostgreSQL 异步引擎 (使用 asyncpg)
ASYNC_DATABASE_URL = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,  # 可选，输出 SQL 日志
    pool_size=10,  # 设置连接池活跃的连接数
    max_overflow=20  # 允许额外的连接数 
)

# 2. 创建异步 session 工厂，session工厂是一个函数，用于创建异步会话实例，这只是一个工厂，不是实际的会话实例
#AsyncSessionLocal()才会创建实际的会话实例
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, # 绑定异步引擎，数据库配置
    class_=AsyncSession, # 使用异步会话类
    autoflush=False, # 禁用自动刷新，避免你没注意到的自动写入行为
    autocommit=False, # 禁用自动提交，确保事务控制
    expire_on_commit=False, # 禁用自动过期，影响“commit 后对象会不会过期”
)

# 3. 依赖注入函数，用于在路由中获取数据库会话
"""
异步数据库会话依赖注入函数

该函数用于在 FastAPI 路由中获取异步数据库会话。
它使用异步上下文管理器确保会话在请求处理完成后正确关闭。

Yields:
    AsyncSession: 异步数据库会话实例
"""
# 3.1 异步数据库会话依赖注入函数
# 用于在路由中获取异步数据库会话
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session: # 创建异步会话，AsyncSessionLocal()是一个函数，用于创建异步会话实例，这个就是with前面加了async，表示这是一个异步上下文管理器，和一般的with一样，会自动关闭会话实例
        try:
            yield session # 返回异步会话实例
            await session.commit()
        except Exception as e:
            await session.rollback() #存在异常，回滚事务
            raise e

            
        
# 1. 进入 async with ：创建 session（并向连接池借连接）
# 2. yield session ：把 session 交给路由函数用
# 3. 路由函数执行完、响应返回后：FastAPI 会“回到 get_db 里”，结束 async with
# 4. 结束 async with ：自动关闭 session，把连接还回连接池
# 如果这里写 return session ，就变成：

# - 你把 session 给了路由
# - 但 get_db 函数立刻结束
# - 它就没有机会自动退出 async with ，也就没机会自动 close（连接容易被占着不还）
