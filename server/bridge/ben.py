"""Client for the BEN bridge engine's REST API (gameapi, port 8085).

See https://github.com/lorserker/ben/blob/main/README-api.md. BEN runs as a
separate program; this module only talks HTTP to it.
"""

from __future__ import annotations

import logging

import httpx

from .auction import Auction
from .bots import Suggestion
from .cards import SUITS, Hand

log = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:8085"
# SAYC is BEN's standard five-card-major system, the closest to "5-kaart hoog".
DEFAULT_SYSTEM = "SAYC"


def to_ben_call(call: str) -> str:
    return {"P": "P", "X": "X", "XX": "XX"}.get(call, call.replace("NT", "N"))


def from_ben_call(call: str) -> str:
    call = call.upper()
    if call in ("PASS", "P", "--", "PA"):
        return "P"
    if call in ("X", "DB"):
        return "X"
    if call in ("XX", "RD"):
        return "XX"
    return call[:-1] + "NT" if call.endswith("N") else call


def hand_to_pbn(hand: Hand) -> str:
    return ".".join("".join(hand[s]) for s in SUITS)


class BenClient:
    def __init__(self, base_url: str = DEFAULT_URL, system: str = DEFAULT_SYSTEM,
                 timeout: float = 90.0, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.system = system
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)

    async def bid(self, seat: str, hand: Hand, auction: Auction, vulnerability: str) -> Suggestion:
        """BEN's bid for `seat` at this point of the auction. Raises on failure."""
        params = {
            "hand": hand_to_pbn(hand),
            "seat": seat,
            "dealer": auction.dealer,
            "vul": "" if vulnerability == "-" else vulnerability,
            "ctx": "-".join(to_ben_call(c) for c in auction.calls),
            "ourSystem": self.system,
            "theirSystem": self.system,
            "matchtype": "IMP",
        }
        r = await self._client.get("/bid", params=params)
        data = r.json()
        if r.status_code != 200 or "bid" not in data:
            raise RuntimeError(data.get("error") or data.get("message") or f"HTTP {r.status_code}")
        return Suggestion(from_ben_call(data["bid"]), data.get("explanation") or "")


class BenBidder:
    """Bidder for the bot seats. Falls back to passing when BEN is unreachable."""

    name = "BEN"

    def __init__(self, client: BenClient):
        self.client = client
        self.available = True

    async def suggest(self, seat, hand, auction, vulnerability) -> Suggestion:
        try:
            s = await self.client.bid(seat, hand, auction, vulnerability)
            if s.call not in auction.legal_calls():
                raise RuntimeError(f"illegal call {s.call}")
            self.available = True
            return s
        except Exception as e:  # noqa: BLE001 - any failure means: pass and report
            log.warning("BEN unavailable, passing instead: %s", e)
            self.available = False
            return Suggestion("P", "BEN was niet bereikbaar; noodgedwongen gepast.")
