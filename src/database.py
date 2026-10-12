from contextlib import contextmanager
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import ClassVar, Generator, Optional, Self

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.logger import logger


@dataclass(slots=True, frozen=True)
class Postgres:
    URL_KEY: ClassVar[str] = "DATABASE_URL"
    LOCAL_URL: ClassVar[str] = "postgresql://spacey:spacey@localhost:5432/spacey"
    _instance: ClassVar[Optional[Self]] = None

    @classmethod
    def init(cls) -> None:
        database_url = getenv(Postgres.URL_KEY, Postgres.LOCAL_URL)
        url = make_url(database_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        engine: Engine = create_engine(
            url,
            pool_pre_ping=True
        )
        session_factory: sessionmaker[Session] = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False
        )

        try:
            run_migrations(engine)
        except SQLAlchemyError:
            engine.dispose()
            logger.error("startup outcome=database_unreachable")
            raise SystemExit(
                "Could not connect to the database or apply migrations (check DATABASE_URL)."
            ) from None

        Postgres._instance = cls(
            _database_url=database_url,
            _engine=engine,
            _session_factory=session_factory
        )

    @classmethod
    def get(cls) -> Self:
        if Postgres._instance is None:
            Postgres.init()

        return Postgres._instance

    _database_url: str
    _engine: Engine
    _session_factory: sessionmaker[Session]

    def close(self) -> None:
        self._engine.dispose()

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session: Session = self._session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def run_migrations(engine: Engine) -> None:
    """Apply numbered SQL files once; commit enum changes before the next file."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = set(connection.execute(text("SELECT name FROM schema_migrations")).scalars())
    directory = Path(__file__).resolve().parent.parent / "migrations"
    for path in sorted(directory.glob("*.sql")):
        if path.name in applied:
            continue
        with engine.begin() as connection:
            connection.exec_driver_sql(path.read_text())
            connection.execute(
                text("INSERT INTO schema_migrations (name) VALUES (:name)"),
                {"name": path.name},
            )
        logger.info("migration applied name=%s", path.name)
