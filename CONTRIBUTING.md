# Contributing to Azure Deploy CLI

## Prerequisites

- Python 3.11 or higher
- `uv` (Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

## Development Setup

**Create and activate a virtual environment:**

```bash
source setup.sh -i
```

This will:
- Create a `.venv` virtual environment using `uv` with Python 3.11
- Install all dependencies (base + dev)
- Print activation instructions

**Manual setup without setup.sh:**

```bash
uv venv -p 3.11 .venv
source .venv/bin/activate
uv sync --all-extras
```

## Managing Dependencies

This project uses `uv` for dependency management with pinned versions in `pyproject.toml` for reproducibility.

### Tips for pip users transitioning to uv

| Task | pip | uv |
|------|-----|-----|
| **Install dependencies** | `pip install -r requirements.txt` | `uv sync` |
| **Add a package** | `pip install package-name` | `uv pip install package-name` |
| **Create venv** | `python -m venv venv` | `uv venv` |
| **Freeze dependencies** | `pip freeze > requirements.txt` | `uv pip freeze` or `uv.lock` |
| **Update lock file** | Manual via pip freeze | `uv sync` (automatic) |
| **Specify Python version** | N/A | `uv venv -p 3.11` |
| **Install dev deps** | `pip install -r requirements-dev.txt` | `uv sync --all-extras` |

### Adding New Dependencies

```bash
# Add to production dependencies
uv pip install package-name

# Add to dev dependencies
uv pip install --group dev package-name

# Update lock file and sync
uv sync
```

Then update `pyproject.toml` to include the new dependency with its pinned version (run `uv pip freeze` to get the exact version).

## Build and Test Commands

```bash
make install-dev    # Install with dev tools
make build          # Run lint + type-check + test
make lint           # Code linting with ruff
make format         # Auto-format code
make type-check     # Type checking with mypy
make test           # Run tests with pytest
make test-cov       # Run tests with coverage report
make clean          # Remove build artifacts
```

## Version Management and Changelog

This project uses a dual-tool approach for versioning and releases:

- **[setuptools-scm](https://setuptools-scm.readthedocs.io/)** - Automatic versioning based on git tags (dynamic at build time)
- **[commitizen](https://commitizen-tools.github.io/commitizen/)** - Version bumping and tagging with semantic versioning
- **[git-cliff](https://git-cliff.org/)** - Automatic changelog generation from conventional commits

### Release Workflow

1. **Create a commit** using [Conventional Commits](https://www.conventionalcommits.org/) format (e.g., `feat: add feature`, `fix: resolve bug`)
   - Optionally use `make commit` for interactive conventional commit creation with `commitizen`
2. **git-cliff** automatically generates changelog from commits since last tag
3. **commitizen** bumps version and creates git tag
4. **New version is committed** alongside updated CHANGELOG
5. **Git tag** triggers PyPI publishing and GitHub Release

**No manual version or changelog updates are needed** — all are generated automatically.

### Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

**Examples:**
- `feat: add support for cosmos-db roles`
- `fix: correct azure identity authentication`
- `docs: update ACA deployment example`
- `chore: upgrade dependencies`

### Making a Release

```bash
# Ensure all changes are committed
git status

# Create a conventional commit
make commit

# Commitizen will:
# - Bump version (major/minor/patch)
# - Create git tag
# - Update CHANGELOG
# - Commit changes

# Push changes and tag
git push origin main --tags
```

The CI/CD pipeline will automatically:
- Build the package
- Run tests
- Publish to PyPI
- Create a GitHub Release

## Pre-commit Hooks

Pre-commit hooks are automatically installed during development setup and enforce code quality standards:

```bash
# Manually run pre-commit on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files
```

## Scripting and Output Handling

This CLI is designed for both interactive use and automated scripting. To support this, it separates output streams:

- **`stderr`**: All human-readable logs, progress indicators, and error messages
- **`stdout`**: All machine-readable output (e.g., revision names, IDs)

When developing features that produce output:
- Use `sys.stderr` for logging and user-facing messages
- Use `sys.stdout` for machine-readable output only
- This allows scripts to cleanly capture output while still seeing logs

## License

Mozilla Public License 2.0 - See LICENSE file for details
