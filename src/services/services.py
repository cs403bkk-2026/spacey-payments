from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from src.services.health import HealthService
from src.services.payment import PaymentService


class InvalidSessionError(RuntimeError):
    """Raised when user tries to use Api class after its been invalidated"""

    def __init__(self) -> None:
        super().__init__("Session is no longer valid!")


@dataclass(slots=True, init=True)
class Services:
    _session: Optional[Session]
    _payment: Optional[PaymentService] = field(init=False, default=None)
    _health: Optional[HealthService] = field(init=False, default=None)

    @property
    def session(self) -> Session:
        if self._session is None:
            raise InvalidSessionError()

        return self._session

    @property
    def payments(self) -> PaymentService:
        if self._payment is None:
            self._payment = PaymentService(self.session)

        return self._payment

    @property
    def health(self) -> HealthService:
        if self._health is None:
            self._health = HealthService(self.session)

        return self._health

    def invalidate(self) -> None:
        self._payment = None
        self._health = None
        self._session = None
