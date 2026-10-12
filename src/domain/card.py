from dataclasses import dataclass
from datetime import datetime, timezone
from re import Pattern, compile
from typing import Any, ClassVar, Optional, Self


@dataclass(slots=True, frozen=True)
class Card:

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> Optional[Self]:
        if (number := body.get("card_number")) is None:
            return None

        if (cvc := body.get("cvc")) is None:
            return None

        if (expiry := body.get("expiry")) is None:
            return None

        return cls(number, cvc, expiry)

    NUMBER_RE: ClassVar[Pattern] = compile(r"^\d{13,19}$")
    CVC_RE: ClassVar[Pattern] = compile(r"^\d{3,4}$")
    EXPIRY_RE: ClassVar[Pattern] = compile(r"^(0[1-9]|1[0-2])/(\d{2})$")

    number: str
    cvc: str
    expiry: str

    @property
    def last4(self) -> str:
        return self.number[-4:]

    def __post_init__(self) -> None:
        assert isinstance(self.number, str), "Expected number to be string"
        assert isinstance(self.cvc, str), "Expected cvc to be string"
        assert isinstance(self.expiry, str), "Expected expiry to be string"

    def _luhn(self) -> bool:
        """Luhn checksum: from the right, double every second digit (subtracting 9
            if that gives more than 9); the digit sum must be divisible by 10."""
        total = 0
        for position, char in enumerate(reversed(self.number)):
            digit = int(char)
            if position % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            total += digit
        return total % 10 == 0

    def validate(self) -> Optional[str]:
        """Returns an error message, or None if the (mocked) card looks valid -
           right shape, passes the Luhn checksum and not expired. Still no network
           check: it says nothing about whether the card really exists."""
        if not Card.NUMBER_RE.match(self.number):
            return "card_number must be 13-19 digits"

        if not self._luhn():
            return "card_number is not a valid card number"

        if not Card.CVC_RE.match(self.cvc):
            return "cvc must be 3 or 4 digits"

        if (match := Card.EXPIRY_RE.match(self.expiry)) is None:
            return "expiry must be in MM/YY format"

        month, year = int(match.group(1)), 2000 + int(match.group(2))
        now: datetime = datetime.now(timezone.utc)
        if (year, month) < (now.year, now.month):
            return "card has expired"

        return None
