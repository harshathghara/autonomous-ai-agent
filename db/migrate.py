"""Run Alembic migrations programmatically (e.g. on API startup)."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def run_alembic_upgrade() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")
