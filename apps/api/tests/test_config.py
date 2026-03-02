from tests.conftest import TEST_DATABASE_URL


def test_uses_in_memory_database():
    assert "sqlite" in TEST_DATABASE_URL.lower(), "Tests should use SQLite for speed and isolation"
    assert (
        ":memory:" in TEST_DATABASE_URL
    ), "Tests should use in-memory database to avoid touching actual data"
    assert "postgresql" not in TEST_DATABASE_URL.lower(), "Tests should NOT use PostgreSQL database"


def test_database_url_isolation():
    from app.core.config import settings

    assert "postgresql" in settings.DATABASE_URL.lower(), "Application should use PostgreSQL"

    assert (
        settings.DATABASE_URL != TEST_DATABASE_URL
    ), "Test database must be different from application database"
