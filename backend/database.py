"""SQLAlchemy engine + get_db() dependency (SQLite: data/state/jobs.db)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config_loader import PROJECT_ROOT, load_config


class Base(DeclarativeBase):
    pass


def _jobs_db_url() -> str:
    db_path = PROJECT_ROOT / load_config()["paths"]["state_db"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


engine = create_engine(
    _jobs_db_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create any ORM-managed tables that don't exist yet (e.g. episode_configs)."""
    # Import models so they register on Base.metadata before create_all.
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
