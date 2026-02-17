"""
Utility for DB connection and query execution.
"""

import logging
import os
from typing import Dict, Type, Union

import pandas as pd
import psycopg2 as psycopg

logger = logging.getLogger("simpleorm.db_util")

ConnectionType: Type[psycopg.extensions.connection] = psycopg.extensions.connection


class DbUtil:
    connection: Type[psycopg.extensions.connection] = None

    def __init__(self, params: Dict = None):
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
        try:
            if default_schema:
                self.create_schema(default_schema)
                self.connection_params["options"] = f"-c search_path={default_schema}"

            self.connection = psycopg.connect(**self.connection_params)
        except Exception as error:
            logger.error("DB: Error creating connection", exc_info=True)
            raise RuntimeError("Failed to create DB Connection") from error

    def disconnect(self, do_commit: bool = False) -> None:
        try:
            if self.connection:
                if do_commit:
                    self.commit()
                self.connection.close()
        except BaseException:
            pass

    def commit(self) -> None:
        if not self.connection:
            raise RuntimeError("No connection found to commit")
        try:
            self.connection.commit()
        except Exception as error:
            logger.error("DB: Error committing", exc_info=True)
            raise

    def create_schema(self, schema: str) -> None:
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
