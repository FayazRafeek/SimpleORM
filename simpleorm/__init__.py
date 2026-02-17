"""
SimpleORM: a minimal PostgreSQL ORM with Pydantic models and explicit DbUtil connections.

Example::

    from simpleorm import DbUtil, BaseTableModel, Column
    class User(BaseTableModel):
        user_id: str = Column(primary_key=True)
        name: str = Column()
    db = DbUtil()
    db.connect()
    user = User(user_id="1", name="Jane")
    user.insert(db_conn=db)
"""

__version__ = "0.1.0"

from simpleorm.base_model import (
    BaseTableModel,
    Column,
    ColumnMetadata,
    OnDeleteFkEnum,
)
from simpleorm.db_util import DbUtil

__all__ = [
    "DbUtil",
    "BaseTableModel",
    "Column",
    "ColumnMetadata",
    "OnDeleteFkEnum",
    "__version__",
]
