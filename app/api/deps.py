from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.book import list_books, get_books_by_price as svc_get_books_by_price, get_books_by_id as svc_get_books_by_id, get_search_books as svc_get_search_books, get_count as svc_get_count, get_books_by_page as svc_get_books_by_page

router = APIRouter(tags=["deps"])

#实现代码的复用
async def common_parameters(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, le=60),
) -> dict:
    return {"skip": skip, "limit": limit}


