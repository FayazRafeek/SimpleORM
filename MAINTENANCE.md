# Maintenance Guide

This document is for maintainers of SimpleORM. It covers publishing, versioning, and maintaining the package.

## Table of Contents

- [Publishing to PyPI](#publishing-to-pypi)
- [Version Management](#version-management)
- [Release Process](#release-process)
- [Testing Before Release](#testing-before-release)
- [Troubleshooting](#troubleshooting)

## Publishing to PyPI

### Initial Setup (One-time)

1. **Create PyPI account**
   - Go to [pypi.org](https://pypi.org) and create an account
   - Verify your email address

2. **Create API token**
   - Go to [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)
   - Click "Add API token"
   - Token name: `SimpleORM GitHub Actions`
   - Scope: "Entire account" (or project-specific: `simpleorm`)
   - Copy the token (starts with `pypi-`) - you won't see it again!

3. **Add GitHub Secret**
   - Go to repo → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: paste your PyPI API token
   - Click "Add secret"

4. **(Optional) TestPyPI setup**
   - Create account at [test.pypi.org](https://test.pypi.org)
   - Create API token at [test.pypi.org/manage/account/token/](https://test.pypi.org/manage/account/token/)
   - Add GitHub secret: `TEST_PYPI_API_TOKEN`

### Publishing a New Version

#### Method 1: GitHub Release (Recommended)

1. **Update version in `pyproject.toml`**
   ```toml
   version = "0.1.1"  # Increment version
   ```

2. **Commit and push**
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.1.1"
   git push origin main
   ```

3. **Create GitHub Release**
   - Go to repo → Releases → "Create a new release"
   - Tag: `v0.1.1` (must match version in pyproject.toml, prefixed with 'v')
   - Release title: `v0.1.1` or descriptive title
   - Description: Release notes (what changed)
   - Click "Publish release"
   - GitHub Actions workflow runs automatically

4. **Verify**
   - Check Actions tab for workflow completion
   - Visit https://pypi.org/project/simpleorm/ to see new version
   - Test: `pip install --upgrade simpleorm`

#### Method 2: Manual Workflow Dispatch

1. **Update version in `pyproject.toml`** (same as above)

2. **Commit and push** (same as above)

3. **Trigger workflow manually**
   - Go to Actions → "Publish to PyPI"
   - Click "Run workflow"
   - Version: `0.1.1` (must match pyproject.toml)
   - Check "Publish to TestPyPI first" if testing
   - Click "Run workflow"

### Testing on TestPyPI First

Before publishing to production PyPI, test on TestPyPI:

1. Use manual workflow dispatch with "Publish to TestPyPI first" checked
2. Or manually:
   ```bash
   python -m build
   twine upload --repository testpypi dist/*
   ```
   - Username: `__token__`
   - Password: your TestPyPI API token

3. Test installation:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ simpleorm
   ```

## Version Management

Follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Version Checklist

- [ ] Update `version` in `pyproject.toml`
- [ ] Update `__version__` in `simpleorm/__init__.py` (if used)
- [ ] Update CHANGELOG.md (if maintained)
- [ ] Commit version bump
- [ ] Create release tag matching version

## Release Process

### Pre-Release Checklist

- [ ] All tests pass: `pytest tests/`
- [ ] Code is linted/formatted
- [ ] Documentation is updated
- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG updated (if maintained)
- [ ] No sensitive data in code

### Release Steps

1. **Final checks**
   ```bash
   pytest tests/ -v
   python -m build
   twine check dist/*
   ```

2. **Create release**
   - Use GitHub Release (Method 1 above)
   - Or manual workflow dispatch (Method 2)

3. **Monitor workflow**
   - Watch Actions tab for completion
   - Check for errors

4. **Post-release**
   - Verify package on PyPI
   - Test installation: `pip install simpleorm==<version>`
   - Update any external documentation

## Testing Before Release

### Local Testing

```bash
# Install in editable mode
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Build package locally
python -m build

# Check package
twine check dist/*

# Test installation from local build
pip install dist/simpleorm-*.whl
```

### TestPyPI Testing

Always test on TestPyPI before production:

1. Publish to TestPyPI (see above)
2. Install from TestPyPI
3. Run your test suite against TestPyPI version
4. Verify all functionality works

## Troubleshooting

### Workflow Fails

**Error: "Package already exists"**
- Version already published - increment version in `pyproject.toml`

**Error: "Invalid API token"**
- Check GitHub secret `PYPI_API_TOKEN` is correct
- Verify token hasn't expired
- Ensure token scope includes the project

**Error: "Build failed"**
- Check `pyproject.toml` syntax
- Ensure all dependencies are listed
- Verify Python version compatibility

### Package Not Appearing on PyPI

- Wait a few minutes (PyPI indexing delay)
- Check Actions logs for errors
- Verify workflow completed successfully
- Check PyPI project page directly

### Version Conflicts

- PyPI doesn't allow re-uploading same version
- If you need to fix a release, increment version
- Consider yanking a bad release: https://pypi.org/help/#yanked

## Manual Publishing (Fallback)

If GitHub Actions fails, publish manually:

```bash
# Install tools
pip install build twine

# Build
python -m build

# Check
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*
# Username: __token__
# Password: <TestPyPI token>

# Upload to PyPI
twine upload dist/*
# Username: __token__
# Password: <PyPI token>
```

## Updating Dependencies

When updating dependencies in `pyproject.toml`:

1. Test locally: `pip install -e ".[dev]"`
2. Run tests: `pytest tests/`
3. Update version (patch bump)
4. Release new version

## Security

- **Never commit API tokens** to the repository
- Use GitHub Secrets for all sensitive data
- Rotate tokens periodically
- Use project-specific tokens when possible (not account-wide)

## Useful Links

- [PyPI Help](https://pypi.org/help/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Semantic Versioning](https://semver.org/)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
