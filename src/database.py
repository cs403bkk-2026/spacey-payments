from contextlib import contextmanager
from dataclasses import dataclass
from os import getenv
from typing import ClassVar, Generator, Optional, Self

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


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
