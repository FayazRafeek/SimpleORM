"""Tests for simpleorm.db_util."""

from unittest.mock import MagicMock, patch

import pytest
import psycopg2

from simpleorm.db_util import DbUtil


class TestDbUtil:
    """Tests for DbUtil class."""

    def test_init_with_params(self):
        """Test initialization with explicit parameters."""
        params = {
            "host": "localhost",
            "database": "testdb",
            "user": "testuser",
            "password": "testpass",
            "port": "5432",
        }
        db = DbUtil(params=params)
        assert db.connection_params["host"] == "localhost"
        assert db.connection_params["database"] == "testdb"
        assert db.connection_params["user"] == "testuser"
        assert db.connection_params["password"] == "testpass"
        assert db.connection_params["port"] == "5432"
        assert db.connection is None

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization falls back to environment variables."""
        monkeypatch.setenv("DATABASE_HOST", "envhost")
        monkeypatch.setenv("DATABASE_NAME", "envdb")
        monkeypatch.setenv("DATABASE_USER", "envuser")
        monkeypatch.setenv("DATABASE_PASS", "envpass")
        monkeypatch.setenv("DATABASE_PORT", "5433")

        db = DbUtil()
        assert db.connection_params["host"] == "envhost"
        assert db.connection_params["database"] == "envdb"
        assert db.connection_params["user"] == "envuser"
        assert db.connection_params["password"] == "envpass"
        assert db.connection_params["port"] == "5433"

    def test_init_params_override_env(self, monkeypatch):
        """Test explicit params override environment variables."""
        monkeypatch.setenv("DATABASE_HOST", "envhost")
        db = DbUtil(params={"host": "paramhost"})
        assert db.connection_params["host"] == "paramhost"

    @patch("simpleorm.db_util.psycopg.connect")
    def test_connect_success(self, mock_connect):
        """Test successful connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        db.connect()

        assert db.connection == mock_conn
        mock_connect.assert_called_once()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_connect_with_schema(self, mock_connect):
        """Test connection with default schema creates schema and sets search_path."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        db.connect(default_schema="app")

        assert mock_conn.cursor.called
        mock_cursor.execute.assert_called_with("CREATE SCHEMA IF NOT EXISTS app")
        assert db.connection_params["options"] == "-c search_path=app"
        assert db.connection == mock_conn

    @patch("simpleorm.db_util.psycopg.connect")
    def test_connect_failure(self, mock_connect):
        """Test connection failure raises RuntimeError."""
        mock_connect.side_effect = psycopg2.OperationalError("Connection failed")

        db = DbUtil(params={"host": "localhost", "database": "test"})
        with pytest.raises(RuntimeError, match="Failed to create DB Connection"):
            db.connect()

    def test_disconnect_with_commit(self):
        """Test disconnect with commit."""
        mock_conn = MagicMock()
        db = DbUtil()
        db.connection = mock_conn

        db.disconnect(do_commit=True)

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_disconnect_without_commit(self):
        """Test disconnect without commit."""
        mock_conn = MagicMock()
        db = DbUtil()
        db.connection = mock_conn

        db.disconnect(do_commit=False)

        mock_conn.commit.assert_not_called()
        mock_conn.close.assert_called_once()

    def test_disconnect_no_connection(self):
        """Test disconnect when no connection exists."""
        db = DbUtil()
        db.disconnect()
        assert db.connection is None

    def test_commit_success(self):
        """Test successful commit."""
        mock_conn = MagicMock()
        db = DbUtil()
        db.connection = mock_conn

        db.commit()

        mock_conn.commit.assert_called_once()

    def test_commit_no_connection(self):
        """Test commit raises when no connection exists."""
        db = DbUtil()
        with pytest.raises(RuntimeError, match="No connection found"):
            db.commit()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_create_schema_success(self, mock_connect):
        """Test successful schema creation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        db.create_schema("test_schema")

        mock_cursor.execute.assert_called_with("CREATE SCHEMA IF NOT EXISTS test_schema")
        mock_conn.commit.assert_called_once()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_create_schema_failure(self, mock_connect):
        """Test schema creation failure raises RuntimeError."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError("Schema error")
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        with pytest.raises(RuntimeError, match="Failed to create Schema"):
            db.create_schema("test_schema")

        mock_conn.rollback.assert_called_once()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_basic(self, mock_connect):
        """Test basic query execution."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "test2")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        result = db.execute_query("SELECT * FROM test")

        assert result == [(1, "test"), (2, "test2")]
        mock_cursor.execute.assert_called_once_with("SELECT * FROM test")

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_with_params(self, mock_connect):
        """Test query execution with parameters."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        result = db.execute_query("SELECT * FROM test WHERE id = %s", data=(1,))

        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = %s", (1,))

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_as_pd(self, mock_connect):
        """Test query execution returning pandas DataFrame."""
        import pandas as pd

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "test2")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        result = db.execute_query("SELECT * FROM test", as_pd=True)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ["id", "name"]

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_get_column_names(self, mock_connect):
        """Test query execution returning list of dicts."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "test"), (2, "test2")]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        result = db.execute_query("SELECT * FROM test", get_column_names=True)

        assert result == [{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}]

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_no_fetch(self, mock_connect):
        """Test query execution without fetching results."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        result = db.execute_query("INSERT INTO test VALUES (1)", no_fetch=True)

        assert result is None
        mock_cursor.fetchall.assert_not_called()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_with_commit(self, mock_connect):
        """Test query execution with commit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        db.execute_query("INSERT INTO test VALUES (1)", commit=True)

        mock_conn.commit.assert_called_once()

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_auto_connect(self, mock_connect):
        """Test query execution auto-connects if no connection exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        db.execute_query("SELECT 1", table_schema="app")

        assert mock_connect.call_count >= 1

    @patch("simpleorm.db_util.psycopg.connect")
    def test_execute_query_failure(self, mock_connect):
        """Test query execution failure raises exception."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError("SQL error")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db = DbUtil(params={"host": "localhost", "database": "test"})
        with pytest.raises(psycopg2.ProgrammingError):
            db.execute_query("INVALID SQL")
