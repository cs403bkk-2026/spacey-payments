from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.result import Result


@dataclass(slots=True)
class HealthService:
    _session: Session

    def check(self) -> Result[None]:
        try:
            query: Select[int] = select(1)
            self._session.execute(query)
            return Result.success()

        except SQLAlchemyError:
            self._session.rollback()
            return Result.failure("database unreachable")
