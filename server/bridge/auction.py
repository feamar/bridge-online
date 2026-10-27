"""Auction rules: legal calls, end of bidding and the final contract.

Calls are strings: "P" (pass), "X" (double), "XX" (redouble) or a bid such as
"1C", "3NT". Strains in rank order are C, D, H, S, NT.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import next_seat, side

STRAINS = ["C", "D", "H", "S", "NT"]
BIDS = [f"{level}{strain}" for level in range(1, 8) for strain in STRAINS]


class IllegalCall(ValueError):
    pass


def is_bid(call: str) -> bool:
    return call in BIDS


@dataclass
class Contract:
    level: int
    strain: str
    declarer: str
    doubled: str  # "", "X" or "XX"

    def __str__(self) -> str:
        return f"{self.level}{self.strain}{self.doubled} {self.declarer}"


@dataclass
class Auction:
    dealer: str
    calls: list[str] = field(default_factory=list)

    @property
    def to_act(self) -> str:
        return next_seat(self.dealer, len(self.calls))

    def seat_of(self, index: int) -> str:
        return next_seat(self.dealer, index)

    @property
    def is_over(self) -> bool:
        n = len(self.calls)
        if n >= 4 and all(c == "P" for c in self.calls):
            return True
        return n >= 4 and any(is_bid(c) for c in self.calls) and self.calls[-3:] == ["P"] * 3

    def _last_non_pass(self) -> tuple[int, str] | None:
        for i in range(len(self.calls) - 1, -1, -1):
            if self.calls[i] != "P":
                return i, self.calls[i]
        return None

    def _last_bid_index(self) -> int | None:
        for i in range(len(self.calls) - 1, -1, -1):
            if is_bid(self.calls[i]):
                return i
        return None

    def legal_calls(self) -> list[str]:
        if self.is_over:
            return []
        legal = ["P"]
        last_bid = self._last_bid_index()
        start = 0 if last_bid is None else BIDS.index(self.calls[last_bid]) + 1
        last = self._last_non_pass()
        if last is not None:
            i, call = last
            opponents = side(self.seat_of(i)) != side(self.to_act)
            if opponents and is_bid(call):
                legal.append("X")
            if opponents and call == "X":
                legal.append("XX")
        return legal + BIDS[start:]

    def make_call(self, call: str) -> None:
        if call not in self.legal_calls():
            raise IllegalCall(call)
        self.calls.append(call)

    def contract(self) -> Contract | None:
        """Final contract, or None while bidding continues or when passed out."""
        if not self.is_over:
            return None
        last_bid = self._last_bid_index()
        if last_bid is None:
            return None
        bid = self.calls[last_bid]
        level, strain = int(bid[0]), bid[1:]
        declaring_side = side(self.seat_of(last_bid))
        declarer = next(
            self.seat_of(i)
            for i, c in enumerate(self.calls)
            if is_bid(c) and c[1:] == strain and side(self.seat_of(i)) == declaring_side
        )
        doubled = ""
        for c in self.calls[last_bid + 1 :]:
            if c in ("X", "XX"):
                doubled = c
        return Contract(level, strain, declarer, doubled)
