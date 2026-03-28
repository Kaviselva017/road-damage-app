import os
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
ALEMBIC_INI_PATH = BASE_DIR / "alembic.ini"
DEFAULT_DB_PATH = BASE_DIR / "road_damage.db"

load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def assert_schema_current():
    if not ALEMBIC_INI_PATH.exists():
        return

    alembic_cfg = Config(str(ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_head = script.get_current_head()

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_revision = context.get_current_revision()

    if current_revision != expected_head:
        raise RuntimeError(
            f"Database schema is not up to date. Expected Alembic revision {expected_head}, "
            f"found {current_revision or 'none'}. Run `python -m alembic -c backend/alembic.ini upgrade head`."
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
