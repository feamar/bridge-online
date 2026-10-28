"""Bidders for the computer-controlled seats (East and West)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .auction import Auction
from .cards import Hand


@dataclass
class Suggestion:
    call: str
    explanation: str = ""


class Bidder(Protocol):
    name: str
    available: bool

    async def suggest(
        self, seat: str, hand: Hand, auction: Auction, vulnerability: str
    ) -> Suggestion: ...


class PassBidder:
    """Always passes. Used when no engine is configured."""

    name = "Pas-robot"
    available = True

    async def suggest(self, seat, hand, auction, vulnerability) -> Suggestion:
        return Suggestion("P")
