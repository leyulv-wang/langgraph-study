from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book

# 列出所有书籍
async def list_books(db: AsyncSession) -> list[dict]:
    # result = await db.execute(select(Book))
    # books = result.scalars().all() # 查询所有记录
    # books = result.scalars().first() # 查询第一条记录
    books = await db.get(Book, 2) # 根据id查询
    # 转换为字典列表，但是这一步可以省略，因为FastAPI会自动转换为JSON格式
    # return [
    #     {
    #         "id": book.id,
    #         "bookname": book.bookname,
    #         "author": book.author,
    #         "price": book.price,
    #         "publisher": book.publisher,
    #         "create_time": book.create_time,
    #         "update_time": book.update_time,
    #     }
    #     for book in books
    # ]
    return books

#根据路径参数书籍ID，查询数据
async def get_books_by_id(db: AsyncSession, book_id:int) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    return book

#需求： 根据条件查询书籍。 条件：价格大于等于20
async def get_books_by_price(db: AsyncSession, min_price: float = 20) -> list[Book]:
    result = await db.execute(select(Book).where(Book.price >= min_price))
    books = result.scalars().all()
    return books

#需求，用模糊查询
#添加返回类型注解
async def get_search_books(db: AsyncSession) -> list[Book]:
    #需求：查询以 曹 开头的书籍
    result = await db.execute(select(Book).where(Book.author.like("曹%")))

    # & | 运算符，分别表示 AND 和 OR
    #result = await db.execute(select(Book).where((Book.author.like("曹%") | Book.author.like("王%"))))

    #in_ 运算符，用于查询在指定列表中的记录
    #result = await db.execute(select(Book).where(Book.id.in_([1, 2, 3])))
    books = result.scalars().all()
    return books

#需求： 聚合查询
# 聚合查询,返回一个字典
# count() 函数用于统计记录数
# max() 函数用于查询最大值
# sum() 函数用于查询总和
# avg() 函数用于查询平均值
# min() 函数用于查询最小值
async def get_count(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.count(Book.id).label("count"), #这个label()方法用于给查询结果的字段起别名，是列名
            func.max(Book.price).label("max_price"),
            func.sum(Book.price).label("sum_price"),
            func.avg(Book.price).label("avg_price"),
            func.min(Book.price).label("min_price"),
        )
    )
    row = result.one() #这个表示查询结果只有一条记录，所以可以使用one()方法，row 是 SQLAlchemy 的 Row 对象 （像“带列名的元组”），不能直接返回
    return {
        "count": row.count,
        "max_price": row.max_price,
        "sum_price": row.sum_price,
        "avg_price": row.avg_price,
        "min_price": row.min_price,
    }
    # return row

#需求： 分页查询
async def get_books_by_page(db: AsyncSession, page: int = 1, page_size: int = 10) -> list[Book]:
    skip = (page - 1) * page_size
    result = await db.execute(select(Book).offset(skip).limit(page_size))
    books = result.scalars().all()
    return books

#需求： 增加书籍到数据库
async def add_book(db: AsyncSession, book_data: dict) -> Book:
    book_obj = Book(**book_data)
    db.add(book_obj)
    await db.commit()
    return book_obj

#需求，更新数据库
async def update_book(book_id: int, data: dict, db: AsyncSession) -> Book:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    for key, value in data.items():
        setattr(book, key, value) #自动更新数据库中的字段，动态的，不需要手动写死
    await db.commit()
    return book

#需求，删除选定书籍ID的内容
async def delete_book(book_id: int, db: AsyncSession):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    await db.delete(book)
    await db.commit()
    return {"message": "书籍删除成功"}  
