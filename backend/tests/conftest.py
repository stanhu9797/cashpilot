import os
import sys
from pathlib import Path

# Isolated test database and no AI key, so tests never cost money or touch real data
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "test.db")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["AI_PROVIDER"] = "anthropic"
os.environ["UPLOAD_DIR"] = str(Path(__file__).parent / "test_uploads")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def fresh_db():
    db_file = Path(__file__).parent / "test.db"
    if db_file.exists():
        db_file.unlink()
    from app.database import init_db

    init_db()
    yield
    from app.database import engine

    engine.dispose()
    if db_file.exists():
        db_file.unlink()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app import ratelimit

    ratelimit.reset()
    yield
