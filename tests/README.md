# LegiVellum Tests

## Running Tests

### Setup Test Environment

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Or install from requirements-dev.txt
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
# From project root
pytest

# With coverage report
pytest --cov=shared/legivellum --cov=components --cov-report=html

# Verbose output
pytest -v

# Run specific test file
pytest tests/test_validation.py

# Run specific test class
pytest tests/test_validation.py::TestPhaseValidation

# Run specific test
pytest tests/test_validation.py::TestPhaseValidation::test_accepted_phase_valid
```

## Test Structure

```
tests/
├── test_validation.py      # Receipt validation tests
├── test_models.py          # Pydantic model tests (TODO)
├── test_memorygate.py      # MemoryGate API tests (TODO)
├── test_asyncgate.py       # AsyncGate API tests (TODO)
└── test_delegate.py        # DeleGate API tests (TODO)
```

## Writing Tests

### Unit Tests
Test individual functions and validation logic:
- Phase constraint validation
- Routing invariant checks
- Field size limits
- ULID generation

### Integration Tests (TODO)
Test API endpoints with test database:
- Receipt storage and retrieval
- Task queue operations
- Plan generation
- Worker coordination

### Test Database
Integration tests will use a separate test database:
```bash
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum_test
```

## Coverage Goals

- Shared library (validation, models): >90%
- API endpoints: >80%
- Background workers: >70%

## CI/CD Integration (TODO)

Tests will run automatically on:
- Pull requests
- Main branch commits
- Release tags

```yaml
# Example GitHub Actions
- name: Run tests
  run: pytest --cov --cov-report=xml
```

## Current Status

✅ Validation tests implemented
⏳ API integration tests pending
⏳ End-to-end workflow tests pending
