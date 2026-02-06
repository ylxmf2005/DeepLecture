# Test Structure

This test suite follows Clean Architecture principles with a two-dimensional organization:

```
tests/
├── conftest.py           # Global fixtures (worker isolation, settings override)
├── fixtures/             # Reusable fake implementations
│   ├── __init__.py
│   └── fakes.py          # In-memory port implementations
├── unit/                 # No I/O, no network, deterministic
│   ├── domain/           # Entity and error tests
│   ├── use_cases/        # Business logic tests with fakes
│   ├── infrastructure/   # Pure function tests (decorators, etc.)
│   └── presentation/     # Request validation tests
├── integration/          # Local I/O with tmp, external services mocked
│   ├── use_cases/        # Real use cases with fake adapters
│   ├── infrastructure/   # Repository tests with tmp files
│   └── presentation/     # Flask test client tests
└── e2e/                  # Real services (skipped by default)
    ├── subtitle/         # Real ASR tests
    ├── llm/              # Real LLM tests
    └── tts/              # Real TTS tests
```

## Test Categories

| Marker | Allowed | Forbidden |
|--------|---------|-----------|
| `unit` | Pure functions, fakes | Disk, network, subprocess |
| `integration` | tmp_path I/O, mocks | Real external services |
| `e2e` | Real services | - (explicit opt-in) |

## Running Tests

```bash
# All unit + integration (parallel)
pytest -n auto -m "unit or integration"

# Only unit tests
pytest -n auto -m unit

# Only integration tests
pytest -n auto -m integration

# E2E tests (single worker, explicit)
pytest -n 1 -m e2e
```

## Fixture Strategy

1. **Worker Isolation**: Each pytest-xdist worker gets its own temp directory
2. **Settings Override**: `test_settings` fixture patches `get_settings()`
3. **Container Reset**: `reset_container` fixture clears singleton cache
4. **Fake Ports**: In-memory implementations in `tests/fixtures/fakes.py`

## Task Reliability Tests

Task state persistence and SSE transport reliability:

| Test File | Category | Coverage |
|-----------|----------|----------|
| `integration/infrastructure/repositories/test_sqlite_task_storage.py` | integration | SQLite task CRUD, startup reconciliation, TTL cleanup |
| `unit/presentation/sse/test_events.py` | unit | SSE frame format (`id:`, `retry:`, `data:`) |
| `unit/infrastructure/workers/test_task_queue_async.py` | unit | TaskManager persistence write-through, startup recovery |
| `integration/presentation/api/test_task_stream.py` | integration | Stream endpoint snapshot + reconciliation-on-connect |
