from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import common_parameters
from app.db.session import get_db
import app.services.book as book_service
router = APIRouter(tags=["route_demo"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}

#定义一个根目录路由
@router.get("/")
async def root() -> dict:
    return {"message": "Hello, FastAPI"}

@router.get("/hello")
async def hello() -> dict:
    return {"message": "你好"}

#...表示必填参数，这个是路径url，url里包括一个可变参数，可以直接到达对应的网址，函数里的对应的就是Path参数
@router.get("/demo/book/{id:int}") #这里可以指定路径参数的类型为int，范围为1-100，描述为书籍id，但是注意不能有空格
async def get_book(id: int = ApiPath(..., gt=0, lt=101, description="书籍id，取值范围1-100")) -> dict:
    return {"book_id": id, "book_name": "Python FastAPI Study"}

#写一个查找作者的路由，路径参数 name，长度在2-10之间
@router.get("/author/{name}")
async def get_author(name: str = ApiPath(..., min_length=2, max_length=10, description="作者姓名，长度2-10之间")) -> dict:
    return {"msg": f"这是{name}的信息"}

#路径参数用于表示具体资源，比如 /book/1 表示某一本书，
# URL路径本身会变化。

# 查询参数用于对资源进行筛选或附加条件，路径里有的 → 路径参数。函数参数但不在路径里 → 查询参数
# 比如 /book?id=1 或 /book?author=Tom，
# 路径不变，参数在 ? 后面。比如/users?age=20
@router.get("/news/news_list")
async def get_news_list(
    skip: int = Query(0, description = "跳过的记录数", lt=100),
    limit: int = Query(10, description = "返回的记录数")
) -> dict:
    return {"skip": skip, "limit": limit}

#写请求体参数，用的是post，客户端向服务器发送请求，写一个注册用户的请求
class User(BaseModel):
    username: str = Field(default="张三", min_length=2, max_length=10, description="用户名，长度要求2-10个字")
    password: str = Field(min_length=3, max_length=20)

@router.post("/register")
async def register(user: User) -> dict:
    return {"msg": f"注册成功，用户名：{user.username}，密码：{user.password}"}

# @router.post("/register")
# async def register(user: User):
#     return user

#指定响应html格式的接口,同时规定响应的类型为HTMLResponse
@router.get("/html", response_class=HTMLResponse)
async def get_html() -> HTMLResponse:
    return HTMLResponse(content="<html><body><h1>这是一级标题</h1></body></html>")

#定义一个文件的接口，来返回图片，用查询参数name
BASE_DIR = FilePath(r"D:\下载\壁纸\天爱星")
@router.get("/file/{name}")
async def get_file(name: str = ApiPath(..., description="文件名")) -> FileResponse:
    file_path = (BASE_DIR / name).resolve() #.resolve() ：把路径规范化成“绝对真实路径”（会处理 .. 这种上级路径）
    if not str(file_path).startswith(str(BASE_DIR.resolve())): #判断最终得到的 file_path 必须仍然在 BASE_DIR 目录下。不满足就直接拒绝请求
        raise HTTPException(status_code=400, detail="invalid file name")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="file not found")

    return FileResponse(str(file_path), media_type="image/jpeg")

#自定义响应格式
class News(BaseModel):
    news_id: int
    title: str
    content: str

##这种写法会先用News模型来验证返回的内容，符合模型的定义，才会返回，否则会报错
# @router.get("/news/{news_id}", response_model=News)#声明响应模型为News
# async def get_news(news_id: int = ApiPath(..., description="新闻id")) -> News:
#     return News(news_id=news_id, title=f"这是第{news_id}条新闻", content="这是一条新闻")

#这种写法会把返回内容里不应该存在的字段过滤掉，不会报错
@router.get("/news/{news_id}", response_model=News)#声明响应模型为News
async def get_news(news_id: int = ApiPath(..., description="新闻id")) -> News:
    return {"news_id": news_id, 
            "title": f"这是第{news_id}条新闻", 
            "content": "这是一条新闻",
            }

@router.get("/deps/news_list")
async def get_news_list(commons: dict = Depends(common_parameters)) -> dict:
    return commons


@router.get("/deps/user_list")
async def get_user_list(commons: dict = Depends(common_parameters)) -> dict:
    return commons

# 测试数据库连接
#注意这里get_db没有（），需要的是“函数本身”，让 FastAPI 在合适的时机去调用它；如果你写成 get_db() 就变成你在定义路由时立刻执行了。
@router.get("/test-db")
async def test_db(db: AsyncSession = Depends(get_db)): 
    return {"ok": True}

#定义一个数据库查询函数路由
@router.get("/book/books")
async def get_books_list(db: AsyncSession = Depends(get_db)):
    return await book_service.list_books(db)

#定义一个根据ID查询数据库的路由
@router.get("/book/get_book/{book_id}")
async def get_book_by_id(book_id: int, db: AsyncSession = Depends(get_db)):
    return await book_service.get_books_by_id(db, book_id)
   
#定义一个根据价格查询数据库的路由
@router.get("/book/get_books_by_price")
async def get_books_by_price(min_price: float = Query(20, ge=0), db: AsyncSession = Depends(get_db)):
    return await book_service.get_books_by_price(db, min_price)

#定义一个使用模糊查询的路由
@router.get("/book/search_books")
async def search_books(db: AsyncSession = Depends(get_db)):
    return await book_service.get_search_books(db)

#定义一个聚合查询的路由
@router.get("/book/count")
async def get_count(db: AsyncSession = Depends(get_db)):
    return await book_service.get_count(db)

#定义一个分页查询的路由
@router.get("/book/get_books_by_page")
async def get_books_by_page(page: int = Query(1, ge=1), page_size: int = Query(2, le=60), db: AsyncSession = Depends(get_db)):
    return await book_service.get_books_by_page(db, page, page_size)

#需求： 增加书籍到数据库
#先定义一个请求体模型，包含书籍的属性，如果使用Book(**book.__dict__)，那么请求体模型的属性和数据库表的属性要一致，否则会报错
#如果请求体模型的属性和数据库表的属性不一致，需要手动建立映射
class BookBase(BaseModel):
    bookname: str
    author: str
    price: float
    publisher: str

@router.post("/book/add_book")
async def add_book(book: BookBase, db: AsyncSession = Depends(get_db)):
    data = book.model_dump() if hasattr(book, "model_dump") else book.dict() #判断 book 这个对象有没有 model_dump 这个属性
    #model_dump() 方法是将模型实例转换为字典，而 dict() 方法是将模型实例转换为字典，但是 model_dump() 方法会过滤掉 None 值，而 dict() 方法不会过滤掉 None 值
    return await book_service.add_book(db, data)

#定义一个更新数据的请求体类和路由
class BookUpdate(BaseModel):
    bookname: str
    author: str
    price: float
    publisher: str

#需求：更新数据库
@router.put("/book/update_book/{book_id:int}")
async def update_book(book_id: int, data: BookUpdate, db: AsyncSession = Depends(get_db)):
    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict() #提前把 data 转换为字典，避免在 update_book 函数中调用 model_dump() 方法，避免在另一个代码里引用这里的BookUpdate类，有可能导致循环引用
    return await book_service.update_book(book_id, payload, db)

#需求：删除选定书籍ID的内容
@router.delete("/book/delete_book/{book_id:int}")
async def delete_book(book_id: int, db: AsyncSession = Depends(get_db)):
    return await book_service.delete_book(book_id, db)