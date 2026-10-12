from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.payments import PaymentsRepository


@dataclass(slots=True)
class PaymentService:
    _session: Session
    _repository: Optional[PaymentsRepository] = field(init=False, default=None)

    @property
    def repository(self) -> PaymentsRepository:
        if self._repository is None:
            self._repository = PaymentsRepository(self._session)

        return self._repository
