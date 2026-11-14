# Contributing to Edu MCP

Thank you for your interest in contributing to **Edu MCP**!

## Development Setup

```bash
git clone https://github.com/jujukingg/edu-mcp.git
cd edu-mcp
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/unit -v --cov-fail-under=0
```

## Adding or Improving a Platform Provider

All school platform providers live under `src/edu_mcp/providers/` and implement the `SchoolProvider` protocol in `src/edu_mcp/providers/base.py`, returning the shared immutable Pydantic DTOs from `src/edu_mcp/models.py`.

1. Keep credentials out of logs and error messages.
2. Add unit tests with mocked HTTP/client responses in `tests/unit/test_providers.py` (never commit real `.env` files or tokens).
3. Update `README.md` and `README.fr.md` if you add new environment variables or tools.
4. Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
