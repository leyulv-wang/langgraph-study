from sqlalchemy import String, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
# 书籍模型类
# 继承自基础模型类 Base
class Book(Base):
    __tablename__ = "book"

    id: Mapped[int] = mapped_column(primary_key=True, comment="书籍id") #主键会自动递增
    bookname: Mapped[str] = mapped_column(String(255), comment="书名")
    author: Mapped[str] = mapped_column(String(255), comment="作者")
    price: Mapped[float] = mapped_column(Float, comment="价格")
    publisher: Mapped[str] = mapped_column(String(255), comment="出版社")
