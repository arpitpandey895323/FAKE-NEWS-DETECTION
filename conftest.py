# conftest.py for pytest fixtures

import pytest

@pytest.fixture(scope="session")
def test_database_setup():
    # Set up test database
    db = connect_to_test_db()
    yield db
    # Teardown code
    db.close()