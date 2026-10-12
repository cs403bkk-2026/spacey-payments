from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(slots=True, frozen=True)
class Repository:
    _session: Session
