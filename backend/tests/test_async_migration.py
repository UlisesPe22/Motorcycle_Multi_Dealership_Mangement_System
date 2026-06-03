"""
test_async_migration.py — Verifies the full async migration is correct.

Run from the backend/ directory:
    pytest tests/test_async_migration.py -v

Requires a running PostgreSQL instance (credentials from .env / docker-compose).
"""

import asyncio
import inspect
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession


# ======================================================================== #
# Fixtures                                                                  #
# ======================================================================== #

@pytest.fixture
async def ac():
    """Function-scoped async HTTP client. Each test gets a fresh client and event loop."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client


# ======================================================================== #
# Test 1 — DB session is genuinely async                                    #
# ======================================================================== #

async def test_db_session_is_async():
    from database import get_db
    session = None
    async for s in get_db():
        session = s
        break
    assert session is not None, "get_db() yielded nothing"
    assert isinstance(session, AsyncSession), (
        f"Expected AsyncSession, got {type(session).__name__}"
    )


# ======================================================================== #
# Test 2 — GET /health                                                      #
# ======================================================================== #

async def test_health(ac):
    response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ======================================================================== #
# Test 3 — GET /motorcycles/                                                #
# ======================================================================== #

async def test_motorcycles_list(ac):
    response = await ac.get("/motorcycles/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ======================================================================== #
# Test 4 — GET /clients/                                                    #
# ======================================================================== #

async def test_clients_list(ac):
    response = await ac.get("/clients/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ======================================================================== #
# Test 5 — GET /reservations/clients                                        #
# ======================================================================== #

async def test_reservations_clients(ac):
    response = await ac.get("/reservations/clients")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ======================================================================== #
# Test 6 — GET /reservations/dealerships                                    #
# ======================================================================== #

async def test_reservations_dealerships(ac):
    response = await ac.get("/reservations/dealerships")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ======================================================================== #
# Test 7 — GET /reservations/models                                         #
# ======================================================================== #

async def test_reservations_models(ac):
    response = await ac.get("/reservations/models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ======================================================================== #
# Test 8 — All route handlers with db param are async                       #
# ======================================================================== #

def test_all_db_handlers_are_async():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from main import app

    failures = []
    for route in app.routes:
        if hasattr(route, "endpoint"):
            endpoint = route.endpoint
            sig = inspect.signature(endpoint)
            if "db" in sig.parameters:
                if not asyncio.iscoroutinefunction(endpoint):
                    failures.append(
                        f"{endpoint.__name__} at {route.path} has db but is not async"
                    )

    assert not failures, "Sync handlers found:\n" + "\n".join(failures)


# ======================================================================== #
# Test 9 — database.py uses create_async_engine                             #
# ======================================================================== #

def test_database_uses_async_engine():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import database
    source = inspect.getsource(database)
    assert "create_async_engine" in source, "create_async_engine not found in database.py"
    # Confirm old sync engine is gone (after stripping the async variant from the check)
    source_without_async = source.replace("create_async_engine", "")
    assert "create_engine" not in source_without_async, (
        "Sync create_engine still present in database.py"
    )


# ======================================================================== #
# Test 10 — asyncpg is importable                                           #
# ======================================================================== #

def test_asyncpg_importable():
    import asyncpg
    assert asyncpg is not None
    assert hasattr(asyncpg, "connect"), "asyncpg does not look like a valid package"
