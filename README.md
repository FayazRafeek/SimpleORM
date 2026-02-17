# SimpleORM

A simple ORM library.

## Installation

```bash
pip install simpleorm
```

## Usage

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

## Development

```bash
pip install -e ".[dev]"
```

## Publishing to PyPI

1. Create an account at [pypi.org](https://pypi.org) and create a [API token](https://pypi.org/manage/account/token/).
2. Install build tools: `pip install build twine`
3. Build: `python -m build`
4. Upload: `twine upload dist/*` (use `__token__` as username and your API token as password, or set `TWINE_USERNAME` / `TWINE_PASSWORD`).

For Test PyPI first: `twine upload --repository testpypi dist/*`

## License

MIT
