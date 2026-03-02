# Tests

This directory contains tests organized by architectural layer.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── repositories/            # Repository layer tests
│   └── test_user_repository.py
├── services/                # Service layer tests
│   └── test_user_service.py
└── routes/                  # Route/API endpoint tests
    ├── test_health.py
    └── test_users.py
```

## Test Layers

### Repository Layer Tests (`tests/repositories/`)

Tests data access logic in isolation.

**What to test:**
- CRUD operations (create, read, update, delete)
- Query methods (get_by_email, search, filter, etc.)
- Data integrity and constraints
- Edge cases (null values, duplicates, etc.)

**Fixtures used:**
- `db_session` - Clean database session for each test
- Direct interaction with repository classes

**Example:**
```python
@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    repo = UserRepository(db_session)
    user = User(email="test@example.com", ...)
    created_user = await repo.create(user)
    await db_session.commit()
    assert created_user.id is not None
```

### Service Layer Tests (`tests/services/`)

Tests business logic and orchestration.

**What to test:**
- Business rules validation
- Transaction management
- Service method logic
- Error handling
- Interaction between repositories

**Fixtures used:**
- `db_session` - Database session
- `sample_user_data` - Test data fixtures
- Service class instantiation

**Example:**
```python
@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession, sample_user_data: dict):
    service = UserService(db_session)
    user_data = UserCreate(**sample_user_data)
    user = await service.create_user(user_data)
    assert user.is_verified is False
```

### Route Layer Tests (`tests/routes/`)

Tests HTTP API endpoints end-to-end.

**What to test:**
- HTTP status codes
- Request/response formats
- Authentication/authorization
- Error responses
- Full request-response cycle

**Fixtures used:**
- `client` - TestClient with overridden database dependency
- All layers integrated

**Example:**
```python
def test_create_user(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={"email": "test@example.com", ...}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
```

## Running Tests

### Run all tests
```bash
pytest
# or
make test
```

### Run specific layer
```bash
pytest tests/repositories/     # Repository tests only
pytest tests/services/         # Service tests only
pytest tests/routes/           # Route tests only
```

### Run specific test file
```bash
pytest tests/services/test_user_service.py
```

### Run specific test
```bash
pytest tests/services/test_user_service.py::test_create_user
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
# or
make test-cov
```

### Run with verbose output
```bash
pytest -v
```

### Run tests matching pattern
```bash
pytest -k "create_user"  # Run all tests with "create_user" in name
```

## Test Database

Tests use an in-memory SQLite database for fast execution:
- Each test gets a fresh database
- No need to clean up test data
- Fast and isolated

Configuration in `conftest.py`:
```python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
```

## Writing Tests

### Repository Layer

1. Import repository and models
2. Create repository instance with `db_session`
3. Test data operations directly
4. Commit when needed

```python
@pytest.mark.asyncio
async def test_example(db_session: AsyncSession):
    repo = UserRepository(db_session)
    # Test repository methods
    await db_session.commit()
```

### Service Layer

1. Import service and schemas
2. Create service instance with `db_session`
3. Test business logic
4. Service handles commits internally

```python
@pytest.mark.asyncio
async def test_example(db_session: AsyncSession):
    service = UserService(db_session)
    # Test service methods
```

### Route Layer

1. Use `client` fixture
2. Make HTTP requests
3. Assert responses

```python
def test_example(client: TestClient):
    response = client.post("/api/v1/endpoint", json={...})
    assert response.status_code == 200
```

## Best Practices

1. **Test isolation** - Each test should be independent
2. **Clear test names** - Use descriptive names (test_create_user_duplicate_email)
3. **Arrange-Act-Assert** - Structure tests clearly
4. **Use fixtures** - Reuse common setup with fixtures
5. **Test edge cases** - Test error conditions, not just happy path
6. **Mock external services** - Don't call real APIs in tests
7. **Fast tests** - Keep tests fast for quick feedback

## Fixtures

Available fixtures (defined in `conftest.py`):

- `event_loop` - Async event loop for test session
- `test_db_engine` - Test database engine
- `db_session` - Clean database session per test
- `client` - FastAPI TestClient with test database
- `sample_user_data` - Sample user data dictionary
- `sample_user_data_2` - Second sample user data

## Coverage

View coverage report:
```bash
make test-cov
# Opens htmlcov/index.html
```

Target: Maintain > 80% code coverage for all layers.
