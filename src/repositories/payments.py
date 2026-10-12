from dataclasses import dataclass

from sqlalchemy import TextClause, text
from sqlalchemy.exc import SQLAlchemyError

from src.repositories.repository import Repository
from src.result import Result

TRUNCATE_PAYMENTS: TextClause = text(
    "TRUNCATE payments RESTART IDENTITY CASCADE"
)


@dataclass(slots=True, frozen=True)
class PaymentsRepository(Repository):

    def truncate(self) -> Result[None]:
        try:
            self._session.execute(TRUNCATE_PAYMENTS)
            return Result.success(None)

        except SQLAlchemyError as err:
            return Result.failure(f"{str(err)}")
