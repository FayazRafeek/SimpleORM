"""
Pydantic-based table models with PostgreSQL DDL, DQL, and DML helpers.

Define models by subclassing :class:`BaseTableModel` and using :func:`Column`
for field metadata (primary keys, indexes, foreign keys, etc.). Table names
are derived from class names (PascalCase -> snake_case). Use :class:`DbUtil`
for connections; model methods accept an optional ``db_conn`` or create one
from environment variables.
"""

import datetime
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, get_args, get_origin

import uuid
from pydantic import BaseModel, ConfigDict, Field

from simpleorm.db_util import DbUtil

logger = logging.getLogger("simpleorm.base_model")

T = TypeVar("T", bound="BaseTableModel")


class OnDeleteFkEnum(Enum):
    """Foreign key ON DELETE action for PostgreSQL."""

    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    RESTRICT = "RESTRICT"
    NO_ACTION = "NO ACTION"


class ColumnMetadata(BaseModel):
    """
    Metadata for a table column (stored in Pydantic Field metadata).
    Used by :func:`Column` and by :class:`BaseTableModel` for DDL and introspection.
    """

    db_default: Optional[Any] = None
    index: Optional[bool] = False
    index_name: Optional[str] = None
    index_type: Optional[str] = None
    index_ops: Optional[str] = None
    nullable: Optional[bool] = True
    primary_key: Optional[bool] = False
    unique: Optional[bool] = False
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None
    is_timezone_aware: Optional[bool] = False
    on_delete: Optional[OnDeleteFkEnum] = None


def Column(
    default: Optional[Any] = None,
    db_default: Optional[Any] = None,
    index: Optional[bool] = False,
    index_name: Optional[str] = None,
    index_type: Optional[str] = None,
    index_ops: Optional[str] = None,
    nullable: Optional[bool] = True,
    primary_key: Optional[bool] = False,
    unique: Optional[bool] = False,
    foreign_key_table: Optional[str] = None,
    foreign_key_column: Optional[str] = None,
    is_timezone_aware: Optional[bool] = False,
    on_delete: Optional[OnDeleteFkEnum] = None,
) -> Any:
    """
    Declare a table column with optional DB metadata (primary key, index, FK, etc.).

    Returns a Pydantic :class:`Field` with metadata consumed by :class:`BaseTableModel`
    for :meth:`BaseTableModel.generate_ddl_query` and introspection. Example::

        class User(BaseTableModel):
            user_id: str = Column(primary_key=True)
            email: str = Column(unique=True, index=True)
            created_at: datetime.datetime = Column(is_timezone_aware=True)
    """
    metadata_dict = ColumnMetadata(
        db_default=db_default,
        index=index,
        index_name=index_name,
        index_type=index_type,
        index_ops=index_ops,
        nullable=False if primary_key else nullable,
        primary_key=primary_key,
        unique=unique,
        foreign_key_table=foreign_key_table,
        foreign_key_column=foreign_key_column,
        is_timezone_aware=is_timezone_aware,
        on_delete=on_delete,
    ).model_dump(exclude_unset=True)
    return Field(default=default, json_schema_extra={"column_metadata": metadata_dict})


class BaseTableModel(BaseModel, extra="allow"):
    """
    Base class for table models: Pydantic models with PostgreSQL DDL/DQL/DML helpers.

    Subclass and define fields with :func:`Column`. Table name is inferred from
    the class name (e.g. ``UserProfile`` -> ``user_profile``). Use class methods
    for DDL (generate_ddl_query, generate_index_ddl_queries), DQL (select_one,
    select_many), and DML (delete); use instance methods for insert/update.
    """

    model_config = ConfigDict(ser_json_timedelta="iso8601")
    _is_backlogged_table: bool = False

    @classmethod
    def is_backlogged_table(cls) -> bool:
        """Return whether this table is marked as backlogged (e.g. not in releases)."""
        return cls._is_backlogged_table

    @staticmethod
    def format_value(value: Any) -> Any:
        """Format a Python value for SQL (e.g. timedelta -> interval string, dict -> JSON)."""
        if isinstance(value, str):
            return f"{value}"
        elif isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                return json.dumps(value)
            return value
        elif isinstance(value, datetime.timedelta):
            days = value.days
            seconds = value.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days} days {hours:02}:{minutes:02}:{seconds:02}"
        elif isinstance(value, dict):
            return json.dumps(value)
        elif isinstance(value, bool):
            return value
        elif value is None:
            return None
        return str(value)

    @staticmethod
    def classname_to_table_name(classname: str) -> str:
        """Convert PascalCase class name to snake_case table name."""
        table_name = classname[0].lower()
        for char in classname[1:]:
            if char.isupper():
                table_name += "_"
            table_name += char.lower()
        return table_name

    @staticmethod
    def get_db_type(
        python_type: Any, metadata: Optional[ColumnMetadata] = None
    ) -> str:
        """Map a Python type (including Optional, List, Dict) to a PostgreSQL type name."""
        type_mapping = {
            str: "TEXT",
            int: "INTEGER",
            float: "numeric",
            datetime.datetime: (
                "TIMESTAMPTZ"
                if metadata and metadata.is_timezone_aware
                else "TIMESTAMP"
            ),
            datetime.date: "DATE",
            datetime.time: "TIME",
            datetime.timedelta: "INTERVAL",
            bool: "BOOLEAN",
            dict: "JSONB",
        }

        origin = get_origin(python_type)
        if origin is Union:
            args = get_args(python_type)
            non_none_type = next((arg for arg in args if arg is not type(None)), None)
            if non_none_type:
                return BaseTableModel.get_db_type(non_none_type, metadata)

        if origin is list:
            args = get_args(python_type)
            if len(args) != 1:
                return "JSONB"
            item_type = args[0]
            sub_origin = get_origin(item_type) or item_type
            if sub_origin is dict:
                return "JSONB"
            item_db_type = type_mapping.get(sub_origin, "TEXT")
            return f"{item_db_type}[]" if item_db_type != "JSONB" else "JSONB"

        if origin is dict:
            return "JSONB"

        return type_mapping.get(python_type, "TEXT")

    @classmethod
    def get_table_name(cls) -> str:
        """Return the table name for this model (snake_case from class name)."""
        return cls.classname_to_table_name(cls.__name__)

    @classmethod
    def get_columns(cls) -> List[str]:
        """Return the list of column names."""
        return list(cls.__annotations__.keys())

    @classmethod
    def get_primary_keys(cls) -> List[str]:
        primary_keys = []
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])
                if metadata.primary_key:
                    primary_keys.append(name)
        return primary_keys

    @classmethod
    def get_foreign_keys(cls) -> List[Dict[str, str]]:
        """Return list of dicts with keys: column, ref_table, ref_column."""
        foreign_keys = []
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])
                if metadata.foreign_key_table is not None:
                    foreign_keys.append(
                        {
                            "column": name,
                            "ref_table": metadata.foreign_key_table,
                            "ref_column": metadata.foreign_key_column or "",
                        }
                    )
        return foreign_keys

    @classmethod
    def get_indexes(cls) -> List[Dict[str, Any]]:
        """Return list of index definitions: name, column, type, table."""
        indexes = []
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])
                if metadata.index:
                    index_name = (
                        metadata.index_name or f"idx_{cls.get_table_name()}_{name}"
                    )
                    indexes.append(
                        {
                            "name": index_name,
                            "column": name,
                            "type": metadata.index_type or "btree",
                            "table": cls.get_table_name(),
                        }
                    )
        return indexes

    @classmethod
    def get_column_breakdown(cls) -> List[Dict[str, Any]]:
        """Return per-column metadata: name, type, nullable, default, ref_table, indexes, etc."""
        column_breakdown = []
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            metadata = None
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])
            column_breakdown.append(
                {
                    "name": name,
                    "type": cls.get_db_type(cls.__annotations__[name], metadata),
                    "nullable": metadata.nullable if metadata else False,
                    "default": metadata.db_default if metadata else None,
                    "ref_table": metadata.foreign_key_table if metadata else None,
                    "ref_column": metadata.foreign_key_column if metadata else None,
                    "on_delete": (
                        metadata.on_delete.value
                        if metadata and metadata.on_delete
                        else None
                    ),
                    "is_timezone_aware": (
                        metadata.is_timezone_aware if metadata else False
                    ),
                    "is_primary_key": metadata.primary_key if metadata else False,
                    "is_indexed": metadata.index if metadata else False,
                    "index_name": metadata.index_name if metadata else None,
                    "index_type": metadata.index_type if metadata else None,
                }
            )
        return column_breakdown

    @classmethod
    def generate_ddl_query(cls, recreate: bool = False) -> str:
        """
        Generate CREATE TABLE (and CREATE INDEX) DDL for this model.
        If recreate is True, omit IF NOT EXISTS. Includes indexes from Column metadata.
        """
        columns = []
        primary_keys = []
        foreign_keys = []

        for name in cls.__annotations__:
            constraints = []
            field_info = cls.model_fields[name]
            metadata = None
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])

            db_type = cls.get_db_type(cls.__annotations__[name], metadata)

            if metadata is not None:
                if metadata.primary_key:
                    primary_keys.append(name)
                    constraints.append("NOT NULL")
                if metadata.unique:
                    constraints.append("UNIQUE")
                SQL_FUNCTIONS = {
                    "CURRENT_TIMESTAMP",
                    "NOW()",
                    "CURRENT_DATE",
                    "CURRENT_TIME",
                }
                if metadata.db_default is not None:
                    db_default = metadata.db_default
                    if (
                        isinstance(db_default, str)
                        and db_default.upper() in SQL_FUNCTIONS
                    ):
                        constraints.append(f"DEFAULT {db_default}")
                    elif isinstance(db_default, str):
                        constraints.append(f"DEFAULT '{db_default}'")
                    else:
                        constraints.append(f"DEFAULT {db_default}")
                if metadata.nullable:
                    constraints.append("NULL")
                elif not metadata.primary_key:
                    constraints.append("NOT NULL")
                if metadata.foreign_key_table is not None:
                    fk_query = f"FOREIGN KEY ({name}) REFERENCES {metadata.foreign_key_table} ({metadata.foreign_key_column})"
                    if metadata.on_delete:
                        fk_query += f" ON DELETE {metadata.on_delete.value}"
                    foreign_keys.append(fk_query)

            columns.append(f"{name} {db_type} {' '.join(constraints)}")

        primary_key_str = (
            f", PRIMARY KEY ({', '.join(primary_keys)})" if primary_keys else ""
        )
        foreign_key_str = ", ".join(foreign_keys)
        query = f"CREATE TABLE {'IF NOT EXISTS ' if not recreate else ''}{cls.classname_to_table_name(cls.__name__)} ("
        query += ",".join(columns) + primary_key_str
        if foreign_keys:
            query += f", {foreign_key_str}"
        query += ");"

        for index_ddl in cls.generate_index_ddl_queries():
            query += f"\n{index_ddl}"

        return query

    @classmethod
    def generate_index_ddl_queries(
        cls, include_if_not_exists: bool = True
    ) -> List[str]:
        """Generate CREATE INDEX statements for all columns with index=True."""
        index_queries = []
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            metadata = None
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])

            if metadata is not None and metadata.index:
                index_name = metadata.index_name or f"idx_{cls.get_table_name()}_{name}"
                index_type = metadata.index_type or "btree"
                if_not_exists = "IF NOT EXISTS " if include_if_not_exists else ""
                if metadata.index_ops:
                    index_sql = f"CREATE INDEX {if_not_exists}{index_name} ON {cls.get_table_name()} USING {index_type} ({name} {metadata.index_ops});"
                else:
                    index_sql = f"CREATE INDEX {if_not_exists}{index_name} ON {cls.get_table_name()} USING {index_type} ({name});"
                index_queries.append(index_sql)
        return index_queries

    @classmethod
    def table_dependencies(cls) -> List[str]:
        """Return table names this model depends on via foreign keys (excluding self)."""
        dependencies = []
        table_name = cls.get_table_name()
        for name in cls.__annotations__:
            field_info = cls.model_fields[name]
            if (
                hasattr(field_info, "json_schema_extra")
                and isinstance(field_info.json_schema_extra, dict)
                and "column_metadata" in field_info.json_schema_extra
            ):
                metadata = ColumnMetadata(**field_info.json_schema_extra["column_metadata"])
                if (
                    metadata.foreign_key_table is not None
                    and metadata.foreign_key_table != table_name
                ):
                    dependencies.append(metadata.foreign_key_table)
        return dependencies

    @classmethod
    def select_one(
        cls: Type[T],
        db_conn: DbUtil = None,
        select_columns: List[str] = None,
        and_condition_columns: List[str] = None,
        and_condition_value: List[Any] = None,
        custom_condition_query: str = None,
        custom_query_inputs: List[Any] = None,
        or_condition_columns: List[str] = None,
        or_condition_value: List[Any] = None,
        order_by_columns: List[str] = None,
        order_direction: str = "ASC",
    ) -> Optional[T]:
        """
        Select at most one row; returns a model instance or None.
        Supports and_condition_*, or_condition_*, custom_condition_query, order_by.
        """
        db_created_here = False
        if db_conn is None:
            db_conn = DbUtil()
            db_conn.connect()
            db_created_here = True

        try:
            if select_columns is None:
                select_columns = ["*"]

            condition_str_grps: List[str] = []
            condition_value: List[Any] = []

            if custom_condition_query is not None:
                condition_str_grps.append(custom_condition_query)
                condition_value += custom_query_inputs or []
            else:
                if (
                    and_condition_columns is not None
                    and and_condition_value is not None
                ):
                    condition_str_grps.append(
                        "("
                        + " AND ".join(
                            [f"{c} = %s" for c in and_condition_columns]
                        )
                        + ")"
                    )
                    condition_value += and_condition_value
                if or_condition_columns is not None and or_condition_value is not None:
                    condition_str_grps.append(
                        "("
                        + " OR ".join(
                            [f"{c} = %s" for c in or_condition_columns]
                        )
                        + ")"
                    )
                    condition_value += or_condition_value

            query = f"SELECT {', '.join(select_columns)} FROM {cls.get_table_name()}"
            if condition_str_grps:
                query += " WHERE " + " AND ".join(condition_str_grps)
            if order_by_columns is not None:
                query += f" ORDER BY {', '.join(order_by_columns)} {order_direction}"
            query += " LIMIT 1;"

            result = db_conn.execute_query(
                query=query,
                data=tuple(condition_value) if condition_value else None,
                get_column_names=True,
            )

            if result and len(result) > 0:
                return cls(**result[0])
            return None

        except Exception as e:
            logger.error("Error in select_one: %s", e, exc_info=True)
            raise
        finally:
            if db_created_here:
                db_conn.disconnect()

    @classmethod
    def select_many(
        cls: Type[T],
        db_conn: DbUtil = None,
        select_columns: List[str] = None,
        and_condition_columns: List[str] = None,
        and_condition_value: List[Any] = None,
        custom_condition_query: str = None,
        custom_query_inputs: List[Any] = None,
        or_condition_columns: List[str] = None,
        or_condition_value: List[Any] = None,
        order_by_columns: List[str] = None,
        order_direction: str = "ASC",
        group_by_columns: List[str] = None,
        limit: int = None,
        offset: int = None,
    ) -> List[T]:
        """
        Select multiple rows; returns a list of model instances.
        Supports and/or/custom conditions, group_by, order_by, limit, offset.
        """
        db_created_here = False
        if db_conn is None:
            db_conn = DbUtil()
            db_conn.connect()
            db_created_here = True

        try:
            if select_columns is None:
                select_columns = ["*"]

            condition_str_grps: List[str] = []
            condition_value: List[Any] = []

            if custom_condition_query is not None:
                condition_str_grps.append(custom_condition_query)
                condition_value += custom_query_inputs or []
            else:
                if (
                    and_condition_columns is not None
                    and and_condition_value is not None
                ):
                    condition_str_grps.append(
                        "("
                        + " AND ".join(
                            [f"{c} = %s" for c in and_condition_columns]
                        )
                        + ")"
                    )
                    condition_value += and_condition_value
                if or_condition_columns is not None and or_condition_value is not None:
                    condition_str_grps.append(
                        "("
                        + " OR ".join(
                            [f"{c} = %s" for c in or_condition_columns]
                        )
                        + ")"
                    )
                    condition_value += or_condition_value

            query = f"SELECT {', '.join(select_columns)} FROM {cls.get_table_name()}"
            if condition_str_grps:
                query += " WHERE " + " AND ".join(condition_str_grps)
            if group_by_columns is not None:
                query += f" GROUP BY {', '.join(group_by_columns)}"
            if order_by_columns is not None:
                query += f" ORDER BY {', '.join(order_by_columns)} {order_direction}"
            if limit is not None:
                query += f" LIMIT {limit}"
            if offset is not None:
                query += f" OFFSET {offset}"
            query += ";"

            result = db_conn.execute_query(
                query=query,
                data=tuple(condition_value) if condition_value else None,
                get_column_names=True,
            )

            if result and len(result) > 0:
                return [cls(**dict(row)) for row in result]
            return []

        except Exception as e:
            logger.error("Error in select_many: %s", e, exc_info=True)
            raise
        finally:
            if db_created_here:
                db_conn.disconnect()

    @classmethod
    def delete(
        cls,
        db_conn: DbUtil = None,
        self_commit: bool = True,
        condition_columns: List[str] = None,
        condition_value: List[Any] = None,
    ) -> None:
        """
        Delete rows matching condition_columns = condition_value.
        If no condition given, raises ValueError. Commits if self_commit is True.
        """
        db_created_here = False
        if db_conn is None:
            db_conn = DbUtil()
            db_conn.connect()
            db_created_here = True

        try:
            if condition_columns is None or condition_value is None:
                raise ValueError("Condition columns and values are required")

            condition_str = " AND ".join([f"{c} = %s" for c in condition_columns])
            query = f"DELETE FROM {cls.get_table_name()} WHERE {condition_str};"

            db_conn.execute_query(
                query=query,
                data=tuple(condition_value),
                commit=self_commit,
                no_fetch=True,
            )
        except Exception as e:
            logger.error("Error in delete: %s", e, exc_info=True)
            raise
        finally:
            if db_created_here:
                db_conn.disconnect(do_commit=self_commit)

    def insert(
        self,
        db_conn: DbUtil = None,
        self_commit: bool = True,
        update_on_conflict: bool = False,
        column_to_update_on_conflict: List[str] = None,
        do_not_execute: bool = False,
    ) -> Dict[str, Any]:
        """
        Insert this instance. Returns {"query": str, "values": list}.
        update_on_conflict: use ON CONFLICT (pk) DO UPDATE for upsert.
        do_not_execute: only build and return query/values.
        """
        db_created_here = False
        if db_conn is None:
            db_conn = DbUtil()
            db_conn.connect()
            db_created_here = True

        try:
            set_only_items = self.model_dump(exclude_unset=True, mode="json")
            columns = []
            values = []

            for name, value in set_only_items.items():
                columns.append(name)
                values.append(self.__class__.format_value(value))

            placeholders = ", ".join(["%s" for _ in values])
            query = f"INSERT INTO {self.__class__.get_table_name()} ({', '.join(columns)}) VALUES ({placeholders})"

            if update_on_conflict:
                primary_keys = self.__class__.get_primary_keys()
                columns_to_update = [
                    c
                    for c in columns
                    if c not in primary_keys
                    and (
                        column_to_update_on_conflict is None
                        or c in (column_to_update_on_conflict or [])
                    )
                ]
                if columns_to_update:
                    query += " ON CONFLICT (" + ", ".join(primary_keys) + ") DO UPDATE SET "
                    query += ", ".join(
                        f"{c} = EXCLUDED.{c}" for c in columns_to_update
                    )

            query += ";"

            if not do_not_execute:
                db_conn.execute_query(
                    query=query,
                    data=tuple(values),
                    commit=self_commit,
                    no_fetch=True,
                )

            return {"query": query, "values": values}

        except Exception as e:
            logger.error("Error in insert: %s", e, exc_info=True)
            raise
        finally:
            if db_created_here:
                db_conn.disconnect(do_commit=self_commit)

    def update(
        self,
        db_conn: DbUtil = None,
        self_commit: bool = True,
        condition_columns: List[str] = None,
        condition_value: List[Any] = None,
        increment_columns: List[str] = None,
        increment_value: List[Union[int, float]] = None,
        decrement_columns: List[str] = None,
        decrement_value: List[Union[int, float]] = None,
    ) -> None:
        """
        Update row(s). By default condition is primary key = current instance values.
        increment_columns / decrement_columns apply numeric +/- (CASE WHEN NULL THEN value ELSE col +/- value).
        """
        db_created_here = False
        if db_conn is None:
            db_conn = DbUtil()
            db_conn.connect()
            db_created_here = True

        try:
            primary_keys = self.__class__.get_primary_keys()
            set_only_items = self.model_dump(exclude_unset=True, mode="json")

            columns = []
            values = []

            for name, value in set_only_items.items():
                if name not in primary_keys:
                    columns.append(name)
                    values.append(self.__class__.format_value(value))

            a_query = [f"{c} = %s" for c in columns]
            i_queries = []
            d_queries = []

            if increment_columns is not None and increment_value is not None:
                for column, value in zip(increment_columns, increment_value):
                    i_queries.append(
                        f"{column} = CASE WHEN {column} IS NULL THEN %s ELSE {column} + %s END"
                    )
                    values.append(value)
                    values.append(value)

            if decrement_columns is not None and decrement_value is not None:
                for column, value in zip(decrement_columns, decrement_value):
                    d_queries.append(
                        f"{column} = CASE WHEN {column} IS NULL THEN 0 ELSE {column} - %s END"
                    )
                    values.append(value)

            set_clause = ", ".join(a_query + i_queries + d_queries)

            if condition_columns is None or condition_value is None:
                condition_str = " AND ".join(
                    f"{c} = %s" for c in primary_keys
                )
                condition_value = [getattr(self, c) for c in primary_keys]
            else:
                condition_str = " AND ".join(
                    f"{c} = %s" for c in condition_columns
                )

            query = f"UPDATE {self.__class__.get_table_name()} SET {set_clause} WHERE {condition_str};"

            db_conn.execute_query(
                query=query,
                data=tuple(values + list(condition_value)),
                commit=self_commit,
                no_fetch=True,
            )
        except Exception as e:
            logger.error("Error in update: %s", e, exc_info=True)
            raise
        finally:
            if db_created_here:
                db_conn.disconnect(do_commit=self_commit)

    def gen_uid(self) -> str:
        """Return a new UUID string (e.g. for primary keys)."""
        return str(uuid.uuid4())

    def to_dict(self) -> dict:
        """Return model as dict with only set fields."""
        return self.model_dump(exclude_unset=True)

    def to_json(self) -> str:
        """Return model as JSON string (only set fields)."""
        return self.model_dump_json(exclude_unset=True)
