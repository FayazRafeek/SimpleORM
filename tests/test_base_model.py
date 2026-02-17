"""Tests for simpleorm.base_model."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from simpleorm.base_model import (
    BaseTableModel,
    Column,
    ColumnMetadata,
    OnDeleteFkEnum,
)
from simpleorm.db_util import DbUtil


class TestOnDeleteFkEnum:
    """Tests for OnDeleteFkEnum."""

    def test_enum_values(self):
        """Test enum values."""
        assert OnDeleteFkEnum.CASCADE.value == "CASCADE"
        assert OnDeleteFkEnum.SET_NULL.value == "SET NULL"
        assert OnDeleteFkEnum.RESTRICT.value == "RESTRICT"
        assert OnDeleteFkEnum.NO_ACTION.value == "NO ACTION"


class TestColumnMetadata:
    """Tests for ColumnMetadata."""

    def test_default_values(self):
        """Test default metadata values."""
        meta = ColumnMetadata()
        assert meta.index is False
        assert meta.nullable is True
        assert meta.primary_key is False
        assert meta.unique is False

    def test_custom_values(self):
        """Test custom metadata values."""
        meta = ColumnMetadata(
            primary_key=True,
            unique=True,
            index=True,
            nullable=False,
            db_default="NOW()",
        )
        assert meta.primary_key is True
        assert meta.unique is True
        assert meta.index is True
        assert meta.nullable is False
        assert meta.db_default == "NOW()"


class TestColumn:
    """Tests for Column function."""

    def test_column_basic(self):
        """Test basic column creation."""
        field = Column(default="test")
        assert field.default == "test"
        assert hasattr(field, "json_schema_extra")
        assert isinstance(field.json_schema_extra, dict)
        assert "column_metadata" in field.json_schema_extra

    def test_column_with_metadata(self):
        """Test column with metadata."""
        field = Column(primary_key=True, unique=True, index=True)
        metadata = ColumnMetadata(**field.json_schema_extra["column_metadata"])
        assert metadata.primary_key is True
        assert metadata.unique is True
        assert metadata.index is True
        assert metadata.nullable is False  # primary_key forces nullable=False

    def test_column_foreign_key(self):
        """Test column with foreign key."""
        field = Column(
            foreign_key_table="user",
            foreign_key_column="user_id",
            on_delete=OnDeleteFkEnum.CASCADE,
        )
        metadata = ColumnMetadata(**field.json_schema_extra["column_metadata"])
        assert metadata.foreign_key_table == "user"
        assert metadata.foreign_key_column == "user_id"
        assert metadata.on_delete == OnDeleteFkEnum.CASCADE


class TestBaseTableModel:
    """Tests for BaseTableModel."""

    def test_classname_to_table_name(self):
        """Test class name to table name conversion."""
        assert BaseTableModel.classname_to_table_name("User") == "user"
        assert BaseTableModel.classname_to_table_name("UserProfile") == "user_profile"
        assert BaseTableModel.classname_to_table_name("APIKey") == "a_p_i_key"

    def test_get_db_type(self):
        """Test Python type to PostgreSQL type mapping."""
        assert BaseTableModel.get_db_type(str) == "TEXT"
        assert BaseTableModel.get_db_type(int) == "INTEGER"
        assert BaseTableModel.get_db_type(float) == "numeric"
        assert BaseTableModel.get_db_type(bool) == "BOOLEAN"
        assert BaseTableModel.get_db_type(dict) == "JSONB"

    def test_get_db_type_datetime(self):
        """Test datetime type mapping with timezone awareness."""
        meta_tz = ColumnMetadata(is_timezone_aware=True)
        meta_no_tz = ColumnMetadata(is_timezone_aware=False)
        assert (
            BaseTableModel.get_db_type(datetime.datetime, meta_tz) == "TIMESTAMPTZ"
        )
        assert (
            BaseTableModel.get_db_type(datetime.datetime, meta_no_tz) == "TIMESTAMP"
        )

    def test_get_db_type_optional(self):
        """Test Optional type mapping."""
        from typing import Optional

        assert BaseTableModel.get_db_type(Optional[str]) == "TEXT"
        assert BaseTableModel.get_db_type(Optional[int]) == "INTEGER"

    def test_get_db_type_list(self):
        """Test List type mapping."""
        from typing import List

        assert BaseTableModel.get_db_type(List[str]) == "TEXT[]"
        assert BaseTableModel.get_db_type(List[int]) == "INTEGER[]"
        assert BaseTableModel.get_db_type(List[dict]) == "JSONB"

    def test_format_value(self):
        """Test value formatting for SQL."""
        assert BaseTableModel.format_value("test") == "test"
        assert BaseTableModel.format_value(123) == "123"
        assert BaseTableModel.format_value(True) is True
        assert BaseTableModel.format_value(None) is None

    def test_format_value_dict(self):
        """Test dict formatting to JSON."""
        import json

        value = {"key": "value"}
        result = BaseTableModel.format_value(value)
        assert result == json.dumps(value)

    def test_format_value_list_of_dicts(self):
        """Test list of dicts formatting to JSON."""
        import json

        value = [{"a": 1}, {"b": 2}]
        result = BaseTableModel.format_value(value)
        assert result == json.dumps(value)

    def test_format_value_timedelta(self):
        """Test timedelta formatting."""
        delta = datetime.timedelta(days=1, hours=2, minutes=3, seconds=4)
        result = BaseTableModel.format_value(delta)
        assert "1 days" in result
        assert "02:03:04" in result


class TestModelDefinition:
    """Tests for model definition and introspection."""

    class User(BaseTableModel):
        user_id: str = Column(primary_key=True)
        name: str = Column()
        email: str = Column(unique=True, index=True)
        age: int = Column(nullable=True)
        created_at: datetime.datetime = Column(is_timezone_aware=True)

    class Post(BaseTableModel):
        post_id: str = Column(primary_key=True)
        title: str = Column()
        author_id: str = Column(
            foreign_key_table="user",
            foreign_key_column="user_id",
            on_delete=OnDeleteFkEnum.CASCADE,
            index=True,
        )

    def test_get_table_name(self):
        """Test table name generation."""
        assert self.User.get_table_name() == "user"
        assert self.Post.get_table_name() == "post"

    def test_get_columns(self):
        """Test column name retrieval."""
        columns = self.User.get_columns()
        assert "user_id" in columns
        assert "name" in columns
        assert "email" in columns
        assert "age" in columns
        assert "created_at" in columns

    def test_get_primary_keys(self):
        """Test primary key retrieval."""
        pks = self.User.get_primary_keys()
        assert pks == ["user_id"]

    def test_get_foreign_keys(self):
        """Test foreign key retrieval."""
        fks = self.Post.get_foreign_keys()
        assert len(fks) == 1
        assert fks[0]["column"] == "author_id"
        assert fks[0]["ref_table"] == "user"
        assert fks[0]["ref_column"] == "user_id"

    def test_get_indexes(self):
        """Test index retrieval."""
        indexes = self.User.get_indexes()
        assert len(indexes) == 1
        assert indexes[0]["column"] == "email"
        assert "idx_user_email" in indexes[0]["name"]

    def test_get_column_breakdown(self):
        """Test column breakdown."""
        breakdown = self.User.get_column_breakdown()
        assert len(breakdown) == 5
        user_id_col = next(c for c in breakdown if c["name"] == "user_id")
        assert user_id_col["is_primary_key"] is True
        assert user_id_col["nullable"] is False

    def test_generate_ddl_query(self):
        """Test DDL query generation."""
        ddl = self.User.generate_ddl_query()
        assert "CREATE TABLE" in ddl
        assert "user" in ddl.lower()
        assert "user_id" in ddl
        assert "PRIMARY KEY" in ddl
        assert "UNIQUE" in ddl

    def test_generate_ddl_query_with_foreign_key(self):
        """Test DDL query generation with foreign key."""
        ddl = self.Post.generate_ddl_query()
        assert "FOREIGN KEY" in ddl
        assert "REFERENCES user" in ddl
        assert "ON DELETE CASCADE" in ddl

    def test_generate_index_ddl_queries(self):
        """Test index DDL generation."""
        index_ddls = self.User.generate_index_ddl_queries()
        assert len(index_ddls) == 1
        assert "CREATE INDEX" in index_ddls[0]
        assert "email" in index_ddls[0]

    def test_table_dependencies(self):
        """Test table dependency detection."""
        deps = self.Post.table_dependencies()
        assert "user" in deps
        assert "post" not in deps


class TestModelDQL:
    """Tests for DQL methods (select_one, select_many)."""

    class User(BaseTableModel):
        user_id: str = Column(primary_key=True)
        name: str = Column()
        email: str = Column()

    @patch("simpleorm.base_model.DbUtil")
    def test_select_one_found(self, mock_db_util_class):
        """Test select_one returns model instance when found."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"user_id": "1", "name": "Test", "email": "test@example.com"}]
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        result = self.User.select_one(
            db_conn=mock_db,
            and_condition_columns=["email"],
            and_condition_value=["test@example.com"],
        )

        assert result is not None
        assert result.user_id == "1"
        assert result.name == "Test"
        assert result.email == "test@example.com"

    @patch("simpleorm.base_model.DbUtil")
    def test_select_one_not_found(self, mock_db_util_class):
        """Test select_one returns None when not found."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = []
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        result = self.User.select_one(
            db_conn=mock_db,
            and_condition_columns=["email"],
            and_condition_value=["nonexistent@example.com"],
        )

        assert result is None

    @patch("simpleorm.base_model.DbUtil")
    def test_select_many(self, mock_db_util_class):
        """Test select_many returns list of model instances."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [
            {"user_id": "1", "name": "Test1", "email": "test1@example.com"},
            {"user_id": "2", "name": "Test2", "email": "test2@example.com"},
        ]
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        results = self.User.select_many(db_conn=mock_db)

        assert len(results) == 2
        assert results[0].user_id == "1"
        assert results[1].user_id == "2"

    @patch("simpleorm.base_model.DbUtil")
    def test_select_many_empty(self, mock_db_util_class):
        """Test select_many returns empty list when no results."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = []
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        results = self.User.select_many(db_conn=mock_db)

        assert results == []

    @patch("simpleorm.base_model.DbUtil")
    def test_select_one_with_order_by(self, mock_db_util_class):
        """Test select_one with order_by."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"user_id": "1", "name": "Test", "email": "test@example.com"}]
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        result = self.User.select_one(
            db_conn=mock_db,
            order_by_columns=["created_at"],
            order_direction="DESC",
        )

        assert result is not None
        query_call = mock_db.execute_query.call_args[1]["query"]
        assert "ORDER BY" in query_call
        assert "DESC" in query_call


class TestModelDML:
    """Tests for DML methods (insert, update, delete)."""

    class User(BaseTableModel):
        user_id: str = Column(primary_key=True)
        name: str = Column()
        email: str = Column()

    @patch("simpleorm.base_model.DbUtil")
    def test_insert(self, mock_db_util_class):
        """Test insert method."""
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        user = self.User(user_id="1", name="Test", email="test@example.com")
        result = user.insert(db_conn=mock_db)

        assert "query" in result
        assert "values" in result
        assert "INSERT INTO" in result["query"]
        mock_db.execute_query.assert_called_once()

    @patch("simpleorm.base_model.DbUtil")
    def test_insert_update_on_conflict(self, mock_db_util_class):
        """Test insert with update_on_conflict."""
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        user = self.User(user_id="1", name="Test", email="test@example.com")
        result = user.insert(db_conn=mock_db, update_on_conflict=True)

        assert "ON CONFLICT" in result["query"]
        assert "DO UPDATE SET" in result["query"]

    @patch("simpleorm.base_model.DbUtil")
    def test_insert_do_not_execute(self, mock_db_util_class):
        """Test insert with do_not_execute."""
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        user = self.User(user_id="1", name="Test", email="test@example.com")
        result = user.insert(db_conn=mock_db, do_not_execute=True)

        mock_db.execute_query.assert_not_called()
        assert "query" in result

    @patch("simpleorm.base_model.DbUtil")
    def test_update(self, mock_db_util_class):
        """Test update method."""
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        user = self.User(user_id="1", name="Test", email="test@example.com")
        user.name = "Updated"
        user.update(db_conn=mock_db)

        query_call = mock_db.execute_query.call_args[1]["query"]
        assert "UPDATE" in query_call
        assert "user" in query_call.lower()

    @patch("simpleorm.base_model.DbUtil")
    def test_update_with_increment(self, mock_db_util_class):
        """Test update with increment."""
        class Counter(BaseTableModel):
            id: str = Column(primary_key=True)
            count: int = Column()

        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        counter = Counter(id="1", count=5)
        counter.update(
            db_conn=mock_db,
            increment_columns=["count"],
            increment_value=[10],
        )

        query_call = mock_db.execute_query.call_args[1]["query"]
        assert "count +" in query_call or "count = CASE" in query_call

    @patch("simpleorm.base_model.DbUtil")
    def test_delete(self, mock_db_util_class):
        """Test delete method."""
        mock_db = MagicMock()
        mock_db.execute_query = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()

        self.User.delete(
            db_conn=mock_db,
            condition_columns=["user_id"],
            condition_value=["1"],
        )

        query_call = mock_db.execute_query.call_args[1]["query"]
        assert "DELETE FROM" in query_call
        assert "user" in query_call.lower()

    @patch("simpleorm.base_model.DbUtil")
    def test_delete_requires_condition(self, mock_db_util_class):
        """Test delete raises ValueError without condition."""
        mock_db = MagicMock()
        mock_db_util_class.return_value = mock_db
        mock_db.connect = MagicMock()
        with pytest.raises(ValueError, match="Condition columns and values are required"):
            self.User.delete(db_conn=mock_db, condition_columns=None, condition_value=None)

    def test_gen_uid(self):
        """Test UUID generation."""
        user = self.User(user_id="1", name="Test")
        uid = user.gen_uid()
        assert isinstance(uid, str)
        assert len(uid) == 36

    def test_to_dict(self):
        """Test to_dict method."""
        user = self.User(user_id="1", name="Test", email="test@example.com")
        result = user.to_dict()
        assert result["user_id"] == "1"
        assert result["name"] == "Test"
        assert result["email"] == "test@example.com"

    def test_to_json(self):
        """Test to_json method."""
        import json

        user = self.User(user_id="1", name="Test", email="test@example.com")
        result = user.to_json()
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["user_id"] == "1"
