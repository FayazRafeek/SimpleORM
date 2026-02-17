# SimpleORM

A simple ORM library.

## Installation

```bash
pip install simpleorm
```

## Usage

```python
import simpleorm

print(simpleorm.__version__)
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
