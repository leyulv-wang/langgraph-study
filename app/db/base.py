from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 基础模型类，包含创建时间和更新时间
# 所有模型类都继承自这个类，这个类是ORM（对象关系映射）模型类的基础类，是数据库表的映射类的基础类
class Base(DeclarativeBase):
    create_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), comment="创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime, insert_default=func.now(), onupdate=func.now(), comment="修改时间")
