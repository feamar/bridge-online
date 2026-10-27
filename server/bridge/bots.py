"""Bidders for the computer-controlled seats (East and West).

Step 1 ships a bot that always passes. The BEN engine plugs in later through
the same interface.
"""

from __future__ import annotations

from typing import Protocol

from .auction import Auction
from .cards import Hand


class Bidder(Protocol):
    async def choose_call(
        self, seat: str, hand: Hand, auction: Auction, vulnerability: str
    ) -> str: ...


class PassBidder:
    async def choose_call(self, seat, hand, auction, vulnerability) -> str:
        return "P"
