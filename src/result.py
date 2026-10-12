from dataclasses import dataclass
from typing import Optional, Self


@dataclass(slots=True, frozen=True)
class Result[T]:

    @classmethod
    def success(cls, value: Optional[T] = None) -> Self:
        return cls(value, "", True)

    @classmethod
    def failure(cls, reason: str) -> Self:
        return cls(None, reason, False)

    _value: Optional[T]
    reason: str
    _ok: bool

    @property
    def failed(self) -> bool:
        return not self._ok

    @property
    def successful(self) -> bool:
        return self._ok

    @property
    def value(self) -> T:
        assert self._ok, f"Result failed: {self.reason}"
        return self._value
