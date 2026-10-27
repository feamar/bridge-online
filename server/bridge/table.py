"""A practice table: two human partners (North and South) against two bots."""

from __future__ import annotations

import asyncio
import secrets
import string
from dataclasses import dataclass, field

from .auction import Auction
from .bots import Bidder
from .cards import Hand, board_dealer, board_vulnerability, deal, hcp

HUMAN_SEATS = ("N", "S")
BOT_SEATS = ("E", "W")
BOT_DELAY_SECONDS = 0.6


@dataclass
class Board:
    number: int
    hands: dict[str, Hand]
    auction: Auction

    @property
    def vulnerability(self) -> str:
        return board_vulnerability(self.number)

    @classmethod
    def new(cls, number: int) -> "Board":
        return cls(number, deal(), Auction(board_dealer(number)))


@dataclass
class Table:
    id: str
    bidder: Bidder
    tokens: dict[str, str] = field(default_factory=dict)  # seat -> secret token
    names: dict[str, str] = field(default_factory=dict)
    board: Board = field(default_factory=lambda: Board.new(1))
    listeners: set = field(default_factory=set)  # callables taking no args
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def join(self, name: str, seat: str | None = None) -> tuple[str, str]:
        free = [s for s in HUMAN_SEATS if s not in self.tokens]
        if seat is None:
            if not free:
                raise ValueError("Deze tafel is vol.")
            seat = free[0]
        elif seat not in free:
            raise ValueError("Deze plaats is al bezet.")
        token = secrets.token_urlsafe(16)
        self.tokens[seat] = token
        self.names[seat] = name or ("Noord" if seat == "N" else "Zuid")
        return seat, token

    def seat_for_token(self, token: str) -> str | None:
        return next((s for s, t in self.tokens.items() if t == token), None)

    def view(self, seat: str) -> dict:
        """What the player in `seat` may see."""
        b = self.board
        over = b.auction.is_over
        contract = b.auction.contract()
        visible = list(b.hands) if over else [seat]
        return {
            "table": self.id,
            "seat": seat,
            "names": self.names,
            "board": b.number,
            "dealer": b.auction.dealer,
            "vulnerability": b.vulnerability,
            "hands": {s: b.hands[s] for s in visible},
            "hcp": {s: hcp(b.hands[s]) for s in visible},
            "calls": b.auction.calls,
            "toAct": None if over else b.auction.to_act,
            "legal": b.auction.legal_calls() if b.auction.to_act == seat else [],
            "over": over,
            "contract": None if contract is None else {
                "level": contract.level,
                "strain": contract.strain,
                "declarer": contract.declarer,
                "doubled": contract.doubled,
            },
        }

    async def _notify(self) -> None:
        for listener in list(self.listeners):
            try:
                await listener()
            except Exception:
                self.listeners.discard(listener)  # connection went away

    async def call(self, seat: str, call: str) -> None:
        async with self.lock:
            if self.board.auction.to_act != seat:
                raise ValueError("Je bent niet aan de beurt.")
            self.board.auction.make_call(call)
        await self._notify()
        await self.run_bots()

    async def run_bots(self) -> None:
        """Let the bots bid until a human is to act or the auction is over."""
        while True:
            async with self.lock:
                a = self.board.auction
                if a.is_over or a.to_act not in BOT_SEATS:
                    return
                seat, board = a.to_act, self.board
            await asyncio.sleep(BOT_DELAY_SECONDS)
            call = await self.bidder.choose_call(
                seat, board.hands[seat], board.auction, board.vulnerability
            )
            async with self.lock:
                if self.board is not board or board.auction.to_act != seat:
                    return  # a new board was started meanwhile
                board.auction.make_call(call)
            await self._notify()

    async def next_board(self) -> None:
        async with self.lock:
            self.board = Board.new(self.board.number + 1)
        await self._notify()
        await self.run_bots()


class TableRegistry:
    def __init__(self, bidder_factory):
        self._tables: dict[str, Table] = {}
        self._bidder_factory = bidder_factory

    def create(self) -> Table:
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(4))
            if code not in self._tables:
                break
        table = Table(code, self._bidder_factory())
        self._tables[code] = table
        return table

    def get(self, code: str) -> Table | None:
        return self._tables.get(code.upper())
