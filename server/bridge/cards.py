"""Cards, hands and deals."""

from __future__ import annotations

import random
from dataclasses import dataclass

SEATS = ["N", "E", "S", "W"]
SUITS = ["S", "H", "D", "C"]  # display order: spades first
RANKS = "AKQJT98765432"
HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}


def next_seat(seat: str, steps: int = 1) -> str:
    return SEATS[(SEATS.index(seat) + steps) % 4]


def partner(seat: str) -> str:
    return next_seat(seat, 2)


def side(seat: str) -> str:
    return "NS" if seat in ("N", "S") else "EW"


@dataclass(frozen=True)
class Card:
    suit: str
    rank: str

    def __str__(self) -> str:
        return self.suit + self.rank


Hand = dict[str, list[str]]  # suit -> ranks, highest first


def full_deck() -> list[Card]:
    return [Card(s, r) for s in SUITS for r in RANKS]


def deal(rng: random.Random | None = None) -> dict[str, Hand]:
    rng = rng or random.Random()
    deck = full_deck()
    rng.shuffle(deck)
    hands: dict[str, Hand] = {}
    for i, seat in enumerate(SEATS):
        cards = deck[i * 13 : (i + 1) * 13]
        hands[seat] = {
            s: sorted((c.rank for c in cards if c.suit == s), key=RANKS.index)
            for s in SUITS
        }
    return hands


def hcp(hand: Hand) -> int:
    return sum(HCP.get(r, 0) for ranks in hand.values() for r in ranks)


def to_pbn(hands: dict[str, Hand], first: str = "N") -> str:
    """PBN deal string, e.g. 'N:AKQ.T98.. ...' (used by BEN and DDS later)."""
    parts = []
    for i in range(4):
        h = hands[next_seat(first, i)]
        parts.append(".".join("".join(h[s]) for s in SUITS))
    return f"{first}:" + " ".join(parts)


# Standard 16-board cycle for dealer and vulnerability.
_VUL_CYCLE = ["-", "NS", "EW", "ALL", "NS", "EW", "ALL", "-",
              "EW", "ALL", "-", "NS", "ALL", "-", "NS", "EW"]


def board_dealer(board: int) -> str:
    return SEATS[(board - 1) % 4]


def board_vulnerability(board: int) -> str:
    return _VUL_CYCLE[(board - 1) % 16]
