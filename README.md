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
- Dependencies: `pydantic>=2`, `psycopg2-binary`

## Installation

```bash
pip install simpleorm
```

## Quick Start

```python
import datetime
from simpleorm import BaseTableModel, Column, DbUtil

# Define your model
class User(BaseTableModel):
    user_id: str = Column(primary_key=True)
    name: str = Column()
    email: str = Column(unique=True)
    created_at: datetime.datetime = Column(is_timezone_aware=True)

# Connect to database
db = DbUtil()
db.connect()

# Create table (run once)
ddl = User.generate_ddl_query()
db.execute_query(ddl, commit=True)

# Insert a user
user = User(
    user_id="1",
    name="Jane Doe",
    email="jane@example.com",
    created_at=datetime.datetime.now()
)
user.insert(db_conn=db)

# Query users
found_user = User.select_one(
    db_conn=db,
    and_condition_columns=["email"],
    and_condition_value=["jane@example.com"]
)
print(found_user.name)  # "Jane Doe"

# Clean up
db.disconnect()
```

## Usage Guide

### Defining Models

Subclass `BaseTableModel` and declare fields with `Column()`. Only set the options you need:

```python
from simpleorm import BaseTableModel, Column, OnDeleteFkEnum

class Post(BaseTableModel):
    post_id: str = Column(primary_key=True)
    title: str = Column()
    content: str = Column(nullable=True)
    author_id: str = Column(
        foreign_key_table="user",
        foreign_key_column="user_id",
        on_delete=OnDeleteFkEnum.CASCADE,
        index=True,
    )
    created_at: datetime.datetime = Column(
        is_timezone_aware=True,
        db_default="NOW()"
    )
    views: int = Column(default=0)
```

**Supported `Column()` options:**
- `default` - Python default value
- `db_default` - SQL default (e.g., `"NOW()"`, `"CURRENT_TIMESTAMP"`)
- `primary_key` - Primary key constraint
- `unique` - Unique constraint
- `nullable` - Allow NULL (default: `True`, except for primary keys)
- `index` - Create an index
- `index_name` - Custom index name
- `index_type` - Index type (e.g., `"btree"`, `"gin"`, `"gist"`)
- `index_ops` - Index operator class
- `foreign_key_table` - Referenced table name
- `foreign_key_column` - Referenced column name
- `on_delete` - Foreign key ON DELETE action (`OnDeleteFkEnum.CASCADE`, `SET_NULL`, etc.)
- `is_timezone_aware` - Use `TIMESTAMPTZ` instead of `TIMESTAMP`

### Database Connection

Create a `DbUtil` with explicit parameters or rely on environment variables:

**Using environment variables:**
```bash
export DATABASE_HOST=localhost
export DATABASE_NAME=mydb
export DATABASE_USER=postgres
export DATABASE_PASS=password
export DATABASE_PORT=5432
```

```python
db = DbUtil()
db.connect()
```

**Using explicit parameters:**
```python
db = DbUtil({
    "host": "localhost",
    "database": "mydb",
    "user": "postgres",
    "password": "password",
    "port": "5432"
})
db.connect()
```

**With schema:**
```python
db.connect(default_schema="app")  # Creates schema if needed, sets search_path
```

**Cleanup:**
```python
db.disconnect(do_commit=True)  # Commits before closing
```

### Creating Tables

Generate and execute DDL from your models:

```python
# Generate CREATE TABLE statement
ddl = User.generate_ddl_query()
print(ddl)
# CREATE TABLE IF NOT EXISTS user (
#     user_id TEXT NOT NULL,
#     name TEXT,
#     email TEXT UNIQUE,
#     created_at TIMESTAMPTZ DEFAULT NOW(),
#     PRIMARY KEY (user_id)
# );
# CREATE INDEX IF NOT EXISTS idx_user_email ON user USING btree (email);

# Execute it
db.execute_query(ddl, commit=True)

# Or generate indexes separately
index_ddls = User.generate_index_ddl_queries()
for index_ddl in index_ddls:
    db.execute_query(index_ddl, commit=True)
```

### Querying Data (DQL)

**Select one row:**
```python
user = User.select_one(
    db_conn=db,
    and_condition_columns=["email"],
    and_condition_value=["jane@example.com"]
)
# Returns User instance or None
```

**Select multiple rows:**
```python
users = User.select_many(
    db_conn=db,
    and_condition_columns=["created_at"],
    and_condition_value=[datetime.datetime(2024, 1, 1)],
    order_by_columns=["created_at"],
    order_direction="DESC",
    limit=10
)
# Returns list of User instances
```

**Custom WHERE clause:**
```python
user = User.select_one(
    db_conn=db,
    custom_condition_query="email = %s AND created_at > %s",
    custom_query_inputs=["jane@example.com", datetime.datetime(2024, 1, 1)]
)
```

**OR conditions:**
```python
users = User.select_many(
    db_conn=db,
    or_condition_columns=["status"],
    or_condition_value=["active", "pending"]
)
```

**Without passing db_conn:**
```python
# Creates a temporary connection from environment variables
user = User.select_one(
    and_condition_columns=["email"],
    and_condition_value=["jane@example.com"]
)
```

### Inserting Data (DML)

**Basic insert:**
```python
user = User(
    user_id="2",
    name="John Doe",
    email="john@example.com",
    created_at=datetime.datetime.now()
)
user.insert(db_conn=db)  # Commits by default
```

**Upsert (insert or update on conflict):**
```python
user.insert(
    db_conn=db,
    update_on_conflict=True,
    column_to_update_on_conflict=["name", "email"]  # Optional: specify which columns to update
)
```

**Get query without executing:**
```python
result = user.insert(db_conn=db, do_not_execute=True)
print(result["query"])   # INSERT INTO user ...
print(result["values"])  # ['2', 'John Doe', ...]
```

### Updating Data

**Update by primary key:**
```python
user.name = "Jane Smith"
user.email = "jane.smith@example.com"
user.update(db_conn=db)  # Uses primary key for WHERE clause
```

**Update with custom condition:**
```python
user.update(
    db_conn=db,
    condition_columns=["status"],
    condition_value=["inactive"]
)
```

**Increment/decrement numeric fields:**
```python
user.update(
    db_conn=db,
    increment_columns=["views"],
    increment_value=[1]
)

user.update(
    db_conn=db,
    decrement_columns=["credits"],
    decrement_value=[10]
)
```

### Deleting Data

```python
User.delete(
    db_conn=db,
    condition_columns=["user_id"],
    condition_value=["1"]
)
```

### Model Introspection

```python
# Get table name
User.get_table_name()  # "user"

# Get column names
User.get_columns()  # ["user_id", "name", "email", "created_at"]

# Get primary keys
User.get_primary_keys()  # ["user_id"]

# Get foreign keys
User.get_foreign_keys()  # [{"column": "author_id", "ref_table": "user", ...}]

# Get indexes
User.get_indexes()  # [{"name": "idx_user_email", "column": "email", ...}]

# Get detailed column breakdown
User.get_column_breakdown()  # Full metadata for each column

# Get table dependencies
Post.table_dependencies()  # ["user"] (tables this depends on)
```

### Utility Methods

```python
user = User(...)

# Generate UUID
user_id = user.gen_uid()  # "550e8400-e29b-41d4-a716-446655440000"

# Convert to dict
user_dict = user.to_dict()  # {"user_id": "1", "name": "Jane", ...}

# Convert to JSON
user_json = user.to_json()  # '{"user_id":"1","name":"Jane",...}'
```

## API Reference

| Component | Description |
|-----------|-------------|
| `DbUtil` | Connection helper: `connect()`, `disconnect()`, `commit()`, `create_schema()`, `execute_query()` |
| `BaseTableModel` | Base class for table models; DDL/DQL/DML class and instance methods |
| `Column(...)` | Pydantic Field with DB metadata for DDL and introspection |
| `ColumnMetadata` | Schema for column options (used internally) |
| `OnDeleteFkEnum` | CASCADE, SET_NULL, RESTRICT, NO_ACTION for foreign keys |

**Class methods (DDL):**
- `generate_ddl_query(recreate=False)` - Generate CREATE TABLE statement
- `generate_index_ddl_queries(include_if_not_exists=True)` - Generate CREATE INDEX statements
- `get_table_name()` - Get snake_case table name
- `get_columns()` - Get list of column names
- `get_primary_keys()` - Get list of primary key columns
- `get_foreign_keys()` - Get list of foreign key definitions
- `get_indexes()` - Get list of index definitions
- `get_column_breakdown()` - Get detailed column metadata
- `table_dependencies()` - Get list of dependent tables

**Class methods (DQL):**
- `select_one(...)` - Select one row, returns model instance or None
- `select_many(...)` - Select multiple rows, returns list of model instances
- `delete(...)` - Delete rows matching condition

**Instance methods (DML):**
- `insert(...)` - Insert this instance
- `update(...)` - Update this instance

**Instance methods (utilities):**
- `gen_uid()` - Generate UUID string
- `to_dict()` - Convert to dictionary
- `to_json()` - Convert to JSON string

## Examples

### Complete Example

```python
import datetime
from simpleorm import BaseTableModel, Column, DbUtil, OnDeleteFkEnum

# Define models
class User(BaseTableModel):
    user_id: str = Column(primary_key=True)
    username: str = Column(unique=True, index=True)
    email: str = Column(unique=True)
    created_at: datetime.datetime = Column(is_timezone_aware=True, db_default="NOW()")

class Post(BaseTableModel):
    post_id: str = Column(primary_key=True)
    title: str = Column()
    content: str = Column(nullable=True)
    author_id: str = Column(
        foreign_key_table="user",
        foreign_key_column="user_id",
        on_delete=OnDeleteFkEnum.CASCADE,
        index=True
    )
    created_at: datetime.datetime = Column(is_timezone_aware=True, db_default="NOW()")
    views: int = Column(default=0)

# Setup database
db = DbUtil()
db.connect()

# Create tables
db.execute_query(User.generate_ddl_query(), commit=True)
db.execute_query(Post.generate_ddl_query(), commit=True)

# Create user
user = User(
    user_id="1",
    username="jane_doe",
    email="jane@example.com"
)
user.insert(db_conn=db)

# Create post
post = Post(
    post_id="1",
    title="Hello World",
    content="My first post",
    author_id="1"
)
post.insert(db_conn=db)

# Query posts by author
posts = Post.select_many(
    db_conn=db,
    and_condition_columns=["author_id"],
    and_condition_value=["1"],
    order_by_columns=["created_at"],
    order_direction="DESC"
)

# Update views
post.views = 10
post.update(db_conn=db)

# Increment views
post.update(
    db_conn=db,
    increment_columns=["views"],
    increment_value=[1]
)

# Find user by email
user = User.select_one(
    db_conn=db,
    and_condition_columns=["email"],
    and_condition_value=["jane@example.com"]
)

db.disconnect()
```

## License

MIT

## Links

- **GitHub**: https://github.com/FayazRafeek/SimpleORM
