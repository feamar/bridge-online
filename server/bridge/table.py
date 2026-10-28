"""A practice table: two human partners (North and South) against two bots."""

from __future__ import annotations

import asyncio
import logging
import secrets
import string
from dataclasses import dataclass, field

from .auction import Auction
from .bots import Bidder
from .cards import Hand, board_dealer, board_vulnerability, deal, hcp
from .review import double_dummy

log = logging.getLogger(__name__)

HUMAN_SEATS = ("N", "S")
BOT_SEATS = ("E", "W")
BOT_DELAY_SECONDS = 0.6


@dataclass
class Board:
    number: int
    hands: dict[str, Hand]
    auction: Auction
    explanations: dict[int, str] = field(default_factory=dict)  # call index -> meaning
    review: dict | None = None

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
    advisor: object | None = None  # BenClient: what BEN would have bid in your seat
    tokens: dict[str, str] = field(default_factory=dict)  # seat -> secret token
    names: dict[str, str] = field(default_factory=dict)
    board: Board = field(default_factory=lambda: Board.new(1))
    listeners: set = field(default_factory=set)  # callables taking no args
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _tasks: set = field(default_factory=set)

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
            "explanations": b.explanations,
            "toAct": None if over else b.auction.to_act,
            "legal": b.auction.legal_calls() if b.auction.to_act == seat else [],
            "over": over,
            "contract": None if contract is None else {
                "level": contract.level,
                "strain": contract.strain,
                "declarer": contract.declarer,
                "doubled": contract.doubled,
            },
            "ai": {"name": self.bidder.name, "available": self.bidder.available},
            "review": b.review if over else None,
        }

    async def _notify(self) -> None:
        for listener in list(self.listeners):
            try:
                await listener()
            except Exception:
                self.listeners.discard(listener)  # connection went away

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def call(self, seat: str, call: str) -> None:
        async with self.lock:
            if self.board.auction.to_act != seat:
                raise ValueError("Je bent niet aan de beurt.")
            self.board.auction.make_call(call)
        await self._after_call(self.board)
        await self.run_bots()

    async def _after_call(self, board: Board) -> None:
        if board.auction.is_over:
            board.review = {"dd": None, "ben": [], "benStatus": "pending" if self.advisor else "off"}
            self._spawn(self._review(board))
        await self._notify()

    async def run_bots(self) -> None:
        """Let the bots bid until a human is to act or the auction is over."""
        while True:
            async with self.lock:
                a = self.board.auction
                if a.is_over or a.to_act not in BOT_SEATS:
                    return
                seat, board = a.to_act, self.board
                snapshot = Auction(a.dealer, list(a.calls))
            await asyncio.sleep(BOT_DELAY_SECONDS)
            suggestion = await self.bidder.suggest(
                seat, board.hands[seat], snapshot, board.vulnerability
            )
            async with self.lock:
                if self.board is not board or board.auction.calls != snapshot.calls:
                    return  # a new board was started, or another task already bid
                board.auction.make_call(suggestion.call)
                if suggestion.explanation:
                    board.explanations[len(board.auction.calls) - 1] = suggestion.explanation
            await self._after_call(board)

    async def _review(self, board: Board) -> None:
        a = board.auction
        try:
            board.review["dd"] = await asyncio.to_thread(
                double_dummy, board.hands, a.dealer, board.vulnerability, a.contract()
            )
        except Exception:
            log.exception("double-dummy analysis failed")
        await self._notify()

        if self.advisor is None:
            return
        for i, call in enumerate(a.calls):
            seat = a.seat_of(i)
            if seat not in HUMAN_SEATS:
                continue
            if self.board is not board:
                return
            try:
                s = await self.advisor.bid(
                    seat, board.hands[seat], Auction(a.dealer, a.calls[:i]), board.vulnerability
                )
            except Exception as e:
                log.warning("BEN review failed: %s", e)
                board.review["benStatus"] = "unavailable"
                await self._notify()
                return
            board.review["ben"].append({
                "index": i, "seat": seat, "call": call,
                "ben": s.call, "explanation": s.explanation, "same": s.call == call,
            })
            await self._notify()
        board.review["benStatus"] = "done"
        await self._notify()

    async def next_board(self) -> None:
        async with self.lock:
            if not self.board.auction.is_over:
                return
            self.board = Board.new(self.board.number + 1)
        await self._notify()
        await self.run_bots()


class TableRegistry:
    def __init__(self, bidder_factory, advisor=None):
        self._tables: dict[str, Table] = {}
        self._bidder_factory = bidder_factory
        self._advisor = advisor

    def create(self) -> Table:
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(4))
            if code not in self._tables:
                break
        table = Table(code, self._bidder_factory(), self._advisor)
        self._tables[code] = table
        return table

    def get(self, code: str) -> Table | None:
        return self._tables.get(code.upper())
