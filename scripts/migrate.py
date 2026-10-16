"""Bring the database schema up to date; safe to run on every start.

Databases created with create_tables.py (before Alembic was used) have the
tables but no alembic_version row, so a plain `alembic upgrade head` would try
to create them again and fail. Such databases are first stamped with the
revision their tables match, then upgraded normally.
"""

import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db import engine  # noqa: E402

INIT_REVISION = "65f4f736e748"        # sessions, messages
MCP_REVISION = "1b15b0ed2a7c"         # + mcp_servers


def main() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    # Serverless Postgres (Neon) may take a few seconds to wake up; retry briefly.
    for attempt in range(1, 4):
        try:
            tables = set(inspect(engine).get_table_names())
            break
        except OperationalError as error:
            if attempt == 3:
                raise
            print(f"Database not reachable yet ({str(error.orig).strip().splitlines()[0][:80]}); retrying…")
            time.sleep(3 * attempt)

    if "alembic_version" not in tables and "sessions" in tables:
        revision = MCP_REVISION if "mcp_servers" in tables else INIT_REVISION
        print(f"Existing schema without Alembic history: stamping {revision}")
        command.stamp(config, revision)

    command.upgrade(config, "head")
    print("Database schema is up to date.")


if __name__ == "__main__":
    main()
