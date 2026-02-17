# SimpleORM

A minimal PostgreSQL ORM built on Pydantic: define models with `Column` metadata, generate DDL, and run select/insert/update/delete with a small, explicit API. No session/engine layer—just a connection helper and model helpers that work with it.

## Features

- **Pydantic-based models** — Table models are Pydantic models; you get validation and serialization for free.
- **Declarative columns** — Use `Column(primary_key=True)`, `Column(unique=True, index=True)`, foreign keys, and optional DDL defaults.
- **Auto table names** — Class name is converted to snake_case (e.g. `UserProfile` → `user_profile`).
- **DDL generation** — `generate_ddl_query()` and `generate_index_ddl_queries()` produce PostgreSQL `CREATE TABLE` and `CREATE INDEX` from your model.
- **Simple connection** — `DbUtil` connects with params or env vars; no connection pooling or ORM session.
- **Explicit DQL/DML** — `select_one`, `select_many`, `insert`, `update`, `delete` take an optional `DbUtil`; they raise on failure and return values directly (no response wrapper).

## Requirements

- Python 3.8+
- PostgreSQL (tested with psycopg2)
- Dependencies: `pydantic>=2`, `pandas`, `psycopg2-binary`

## Installation

```bash
pip install simpleorm
```

## Quick start

```python
import datetime
from simpleorm import BaseTableModel, Column, DbUtil

class User(BaseTableModel):
    user_id: str = Column(primary_key=True)
    name: str = Column()
    email: str = Column(unique=True)
    created_at: datetime.datetime = Column(is_timezone_aware=True)

db = DbUtil()
db.connect()
user = User(user_id="1", name="Jane", email="jane@example.com", created_at=datetime.datetime.now())
user.insert(db_conn=db)
row = User.select_one(db_conn=db, and_condition_columns=["email"], and_condition_value=["jane@example.com"])
db.disconnect()
```

## Usage

### Defining models

Subclass `BaseTableModel` and declare fields with `Column()`. Only set the options you need:

```python
from simpleorm import BaseTableModel, Column, OnDeleteFkEnum

class Post(BaseTableModel):
    post_id: str = Column(primary_key=True)
    title: str = Column()
    author_id: str = Column(
        foreign_key_table="user",
        foreign_key_column="user_id",
        on_delete=OnDeleteFkEnum.CASCADE,
        index=True,
    )
    created_at: datetime.datetime = Column(is_timezone_aware=True, db_default="NOW()")
```

Supported `Column()` options: `default`, `db_default`, `primary_key`, `unique`, `nullable`, `index`, `index_name`, `index_type`, `index_ops`, `foreign_key_table`, `foreign_key_column`, `on_delete`, `is_timezone_aware`.

### Connection (DbUtil)

Create a `DbUtil` with explicit params or rely on environment variables:

- `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASS`, `DATABASE_PORT`

```python
db = DbUtil()
db.connect()                    # uses env vars
db.connect(default_schema="app")  # creates schema if needed, sets search_path
# ... run queries ...
db.disconnect(do_commit=True)
```

`connect()`, `commit()`, `create_schema()`, and `execute_query()` raise on failure; on success they return the result (or `None` where applicable).

### DDL

Generate `CREATE TABLE` and indexes from your model:

```python
ddl = User.generate_ddl_query()           # includes CREATE INDEX from Column(index=True)
index_only = User.generate_index_ddl_queries()
```

Run the DDL with `db.execute_query(ddl, commit=True)` (or your migration runner).

### Queries (DQL)

- **select_one** — Returns one model instance or `None`. Use `and_condition_columns` / `and_condition_value`, or `custom_condition_query` with `custom_query_inputs`, plus optional `order_by_columns` / `order_direction`.
- **select_many** — Same condition options, plus `group_by_columns`, `limit`, `offset`; returns a list of model instances.

You can pass an existing `DbUtil` or omit it to use a short-lived connection (created from env).

### Insert / update / delete (DML)

- **insert** (instance method) — Inserts the row; returns `{"query": str, "values": list}`. Use `update_on_conflict=True` for upsert; `do_not_execute=True` to only build query/values.
- **update** (instance method) — Updates by primary key by default, or by `condition_columns` / `condition_value`. Supports `increment_columns` / `increment_value` and `decrement_columns` / `decrement_value` for numeric fields.
- **delete** (class method) — Deletes rows matching `condition_columns` and `condition_value`; requires both.

All DML methods raise on failure; on success they return `None` except `insert`, which returns the query/values dict.

## API overview

| Component | Description |
|-----------|-------------|
| `DbUtil` | Connection helper: `connect()`, `disconnect()`, `commit()`, `create_schema()`, `execute_query()` |
| `BaseTableModel` | Base class for table models; DDL/DQL/DML class and instance methods |
| `Column(...)` | Pydantic Field with DB metadata for DDL and introspection |
| `ColumnMetadata` | Schema for column options (used internally) |
| `OnDeleteFkEnum` | CASCADE, SET_NULL, RESTRICT, NO_ACTION for foreign keys |

Introspection: `get_table_name()`, `get_columns()`, `get_primary_keys()`, `get_foreign_keys()`, `get_indexes()`, `get_column_breakdown()`, `table_dependencies()`.

## Development

```bash
git clone https://github.com/FayazRafeek/SimpleORM.git
cd SimpleORM
pip install -e ".[dev]"
```

Optional dev deps: `build`, `twine` for releasing.

## Publishing to PyPI

1. Create an account at [pypi.org](https://pypi.org) and an [API token](https://pypi.org/manage/account/token/).
2. `pip install build twine`
3. `python -m build`
4. `twine upload dist/*` (use `__token__` and your token as password, or `TWINE_USERNAME` / `TWINE_PASSWORD`).

To try first: `twine upload --repository testpypi dist/*`

## License

MIT
