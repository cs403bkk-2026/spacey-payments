from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field

from src.database import Postgres
from src.services.services import Services


class NestedTransactionError(RuntimeError):
    """Raised when uow.transaction() is called inside an existing transaction block."""

    def __init__(self) -> None:
        super().__init__("Nested transactions are strictly prohibited")


@dataclass(slots=True)
class UnitOfWork:
    _postgres: Postgres = field(init=False, default_factory=Postgres.get)
    _session_active: bool = field(init=False, default=False)

    @contextmanager
    def transaction(self) -> Generator[Services, None, None]:
        if self._session_active:
            raise NestedTransactionError()

        with self._postgres.get_session() as session:
            self._session_active = True
            services: Services = Services(session)
            try:
                yield services

                if session.is_active:
                    session.commit()

            except Exception:
                session.rollback()
                self._session_active = False
                raise

            finally:
                self._session_active = False
                services.invalidate()
