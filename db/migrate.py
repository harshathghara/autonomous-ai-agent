"""Run Alembic migrations programmatically (e.g. on API startup)."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def run_alembic_upgrade() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    os.environ["_ALEMBIC_EMBEDDED"] = "1"
    try:
        command.upgrade(cfg, "head")
    finally:
        os.environ.pop("_ALEMBIC_EMBEDDED", None)
