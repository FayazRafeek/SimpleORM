"""
PostgreSQL connection and query execution utilities.

This module provides :class:`DbUtil` for managing connections and running
parameterized SQL. Connection parameters can be passed explicitly or read
from environment variables (e.g. ``DATABASE_HOST``, ``DATABASE_NAME``).
"""

import logging
import os
from typing import Dict, Type, Union

import pandas as pd
import psycopg2 as psycopg

logger = logging.getLogger("simpleorm.db_util")

ConnectionType: Type[psycopg.extensions.connection] = psycopg.extensions.connection


class DbUtil:
    """
    PostgreSQL connection manager and query executor.

    Uses psycopg2 under the hood. Parameters not provided in ``params``
    fall back to environment variables: ``DATABASE_HOST``, ``DATABASE_NAME``,
    ``DATABASE_USER``, ``DATABASE_PASS``, ``DATABASE_PORT``.

    On success, methods return the result (or None); on failure they log
    and raise (e.g. :exc:`RuntimeError`).
    """

    connection: Type[psycopg.extensions.connection] = None

    def __init__(self, params: Dict = None):
        """
        Build connection params from ``params`` and env (e.g. DATABASE_*).
        """
        params = params or {}
        self.connection_params = {
            "host": params.get("host") or os.getenv("DATABASE_HOST"),
            "database": params.get("database") or os.getenv("DATABASE_NAME"),
            "user": params.get("user") or os.getenv("DATABASE_USER"),
            "password": params.get("password") or os.getenv("DATABASE_PASS"),
            "port": params.get("port") or os.getenv("DATABASE_PORT"),
        }
        self.connection = None

    def connect(self, default_schema: str = None) -> None:
        """
        Open a connection. If ``default_schema`` is set, create the schema
        if needed and set the connection's search_path. Raises on failure.
        """
        try:
            if default_schema:
                self.create_schema(default_schema)
                self.connection_params["options"] = f"-c search_path={default_schema}"

            self.connection = psycopg.connect(**self.connection_params)
        except Exception as error:
            logger.error("DB: Error creating connection", exc_info=True)
            raise RuntimeError("Failed to create DB Connection") from error

    def disconnect(self, do_commit: bool = False) -> None:
        """
        Close the connection. If ``do_commit`` is True, commit before closing.
        """
        try:
            if self.connection:
                if do_commit:
                    self.commit()
                self.connection.close()
        except BaseException:
            pass

    def commit(self) -> None:
        """
        Commit the current transaction. Raises if there is no connection or commit fails.
        """
        if not self.connection:
            raise RuntimeError("No connection found to commit")
        try:
            self.connection.commit()
        except Exception as error:
            logger.error("DB: Error committing", exc_info=True)
            raise

    def create_schema(self, schema: str) -> None:
        """
        Create schema ``schema`` (IF NOT EXISTS). Connects first if needed. Raises on failure.
        """
        try:
            if not self.connection:
                self.connect()

            with self.connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

            self.connection.commit()
        except Exception as error:
            if self.connection:
                self.connection.rollback()
            logger.error("DB: Failed to create schema %s", schema, exc_info=True)
            raise RuntimeError(f"Failed to create Schema: {schema}") from error

    def execute_query(
        self,
        query: str,
        table_name: str = None,
        as_pd: bool = False,
        data: tuple = None,
        table_schema: str = None,
        commit: bool = False,
        no_fetch: bool = False,
        get_column_names: bool = False,
        hide_query_execution_log: bool = True,
    ) -> Union[None, list, pd.DataFrame]:
        """
        Execute a query with optional parameters and return format options.

        Args:
            query: SQL string; use ``%s`` placeholders when passing ``data``.
            data: Tuple of values for placeholders (parameterized execution).
            table_schema: If connection is not open, connect with this as default_schema.
            commit: If True, commit after execution.
            no_fetch: If True, do not fetch results (e.g. INSERT/UPDATE); returns None.
            as_pd: If True, return result as a :class:`pandas.DataFrame`.
            get_column_names: If True, return list of dicts (column name -> value).
            hide_query_execution_log: If False, log the executed query.

        Returns:
            Rows as list, list of dicts, or DataFrame per options; None if no_fetch.
        Raises:
            Exception: On execution or commit failure.
        """
        if not self.connection:
            self.connect(table_schema)

        try:
            with self.connection.cursor() as cursor:
                if data is not None:
                    cursor.execute(query, data)
                else:
                    cursor.execute(query)

                if not hide_query_execution_log:
                    logger.info("Query executed: %s", cursor.query.decode("utf-8"))

                if commit:
                    self.commit()

                if no_fetch:
                    return None

                result = cursor.fetchall()

                if as_pd:
                    column_names = [desc[0] for desc in cursor.description]
                    return pd.DataFrame(result, columns=column_names)

                if get_column_names:
                    column_names = [desc[0] for desc in cursor.description]
                    return [dict(zip(column_names, row)) for row in result]

                return result

        except Exception as error:
            logger.error("DB: Error executing query", exc_info=True)
            raise
