"""Global pytest fixtures and test environment setup."""

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest


def _is_postgres_reachable(host: str = "127.0.0.1", port: int = 54329) -> bool:
    """Check if PostgreSQL port is accepting TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def _ensure_local_postgres() -> bool:
    """Ensure a local PostgreSQL container is running on port 54329."""
    if _is_postgres_reachable("127.0.0.1", 54329):
        return True

    if not shutil.which("docker"):
        return False

    # Try starting existing test_pg container
    res = subprocess.run(
        ["docker", "start", "test_pg"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        # Spin up a new test_pg container
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "test_pg",
                "-p",
                "54329:5432",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                "-e",
                "POSTGRES_USER=postgres",
                "-e",
                "POSTGRES_DB=postgres",
                "postgres:alpine",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    # Wait up to 10 seconds for PostgreSQL to accept connections
    for _ in range(20):
        time.sleep(0.5)
        if _is_postgres_reachable("127.0.0.1", 54329):
            return True

    return False


@pytest.fixture(scope="session", autouse=True)
def setup_postgres_session() -> None:
    """Session fixture ensuring PostgreSQL is available when needed."""
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
    )
    if "localhost:54329" in db_url or "127.0.0.1:54329" in db_url:
        _ensure_local_postgres()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Gracefully skip PostgreSQL integration tests if database cannot be reached."""
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:54329/postgres",
    )
    is_default_local = "localhost:54329" in db_url or "127.0.0.1:54329" in db_url

    if (
        is_default_local
        and not _is_postgres_reachable("127.0.0.1", 54329)
        and not _ensure_local_postgres()
    ):
        skip_pg = pytest.mark.skip(
            reason=(
                "PostgreSQL not reachable at localhost:54329. "
                "Start Docker or run 'docker run -d --name test_pg -p 54329:5432 postgres:alpine'."
            )
        )
        for item in items:
            fspath = Path(str(item.fspath))
            if "tests/integration" in str(fspath) or "test_release_seed" in item.name:
                item.add_marker(skip_pg)
