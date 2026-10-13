from contextlib import contextmanager
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import ClassVar, Generator, Optional, Self

from sqlalchemy import Engine, TextClause, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


MIGRATIONS_DIR: Path = Path(__file__).resolve().parent.parent / "migrations"

# Any constant works; it only has to be the same for every app instance.
MIGRATION_LOCK_KEY: int = 4031
LOCK: TextClause = text("SELECT pg_advisory_lock(:key)")
UNLOCK: TextClause = text("SELECT pg_advisory_unlock(:key)")
CREATE_SCHEMA_MIGRATIONS: TextClause = text(
    "CREATE TABLE IF NOT EXISTS schema_migrations ("
    "name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
)
SELECT_APPLIED: TextClause = text("SELECT name FROM schema_migrations")
INSERT_APPLIED: TextClause = text("INSERT INTO schema_migrations (name) VALUES (:name)")


@dataclass(slots=True, frozen=True)
class Postgres:
    URL_KEY: ClassVar[str] = "DATABASE_URL"
    LOCAL_URL: ClassVar[str] = "postgresql://spacey:spacey@localhost:5432/spacey"
    _instance: ClassVar[Optional[Self]] = None

    @classmethod
    def init(cls) -> None:
        engine: Engine = create_engine(
            (database_url := getenv(Postgres.URL_KEY, Postgres.LOCAL_URL)),
            pool_pre_ping=True
        )
        session_factory: sessionmaker[Session] = sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False
        )

        Postgres._instance = cls(
            _database_url=database_url,
            _engine=engine,
            _session_factory=session_factory
        )

    @classmethod
    def get(cls) -> Self:
        if cls._instance is None:
            cls.init()

        instance = cls._instance
        assert instance is not None
        return instance

    _database_url: str
    _engine: Engine
    _session_factory: sessionmaker[Session]

    def migrate(self, directory: Path = MIGRATIONS_DIR) -> list[str]:
        """Applies directory/*.sql in filename order, once each, every file in
        its own transaction. An advisory lock keeps two starting instances from
        applying the same file. Returns the names applied by this call."""
        applied_now: list[str] = []
        with self._engine.connect() as connection:
            connection.execute(LOCK, {"key": MIGRATION_LOCK_KEY})
            connection.commit()
            try:
                connection.execute(CREATE_SCHEMA_MIGRATIONS)
                applied: set[str] = set(connection.scalars(SELECT_APPLIED))
                connection.commit()

                for path in sorted(directory.glob("*.sql")):
                    if path.name in applied:
                        continue
                    connection.exec_driver_sql(path.read_text())
                    connection.execute(INSERT_APPLIED, {"name": path.name})
                    connection.commit()
                    applied_now.append(path.name)
            finally:
                connection.rollback()
                connection.execute(UNLOCK, {"key": MIGRATION_LOCK_KEY})
                connection.commit()

        return applied_now

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
