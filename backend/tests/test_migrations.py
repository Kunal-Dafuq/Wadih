import pytest
from alembic.config import Config
from alembic import command
from app.core.config import settings


def test_alembic_migrations():
    """Verify that Alembic migrations run cleanly to head."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    # Check that upgrade head runs without error
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        pytest.fail(f"Alembic upgrade failed: {e}")
