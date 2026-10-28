import asyncio

import httpx

from bridge.auction import Auction
from bridge.ben import BenBidder, BenClient, from_ben_call, hand_to_pbn, to_ben_call

HAND = {"S": list("AK97543"), "H": ["K"], "D": list("T3"), "C": list("AK7")}


def test_call_conversion():
    assert [to_ben_call(c) for c in ["P", "X", "XX", "1NT", "4S"]] == ["P", "X", "XX", "1N", "4S"]
    assert [from_ben_call(c) for c in ["PASS", "X", "XX", "3N", "2H"]] == ["P", "X", "XX", "3NT", "2H"]
    assert hand_to_pbn(HAND) == "AK97543.K.T3.AK7"


def make_client(handler):
    return BenClient("http://ben", transport=httpx.MockTransport(handler))


def test_bid_request_and_response():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(request.url.params)
        return httpx.Response(200, json={"bid": "4S", "who": "NN", "explanation": "Game in schoppen"})

    auction = Auction("N", ["1NT", "P"])
    s = asyncio.run(make_client(handler).bid("S", HAND, auction, "EW"))
    assert (s.call, s.explanation) == ("4S", "Game in schoppen")
    assert seen["hand"] == "AK97543.K.T3.AK7"
    assert (seen["seat"], seen["dealer"], seen["vul"], seen["ctx"]) == ("S", "N", "EW", "1N-P")
    assert seen["ourSystem"] == "SAYC"


def test_bidder_falls_back_to_pass_when_ben_is_down():
    def handler(request):
        raise httpx.ConnectError("refused")

    bidder = BenBidder(make_client(handler))
    s = asyncio.run(bidder.suggest("E", HAND, Auction("N", ["1H"]), "-"))
    assert s.call == "P" and bidder.available is False


def test_bidder_rejects_illegal_engine_call():
    bidder = BenBidder(make_client(lambda r: httpx.Response(200, json={"bid": "1C"})))
    s = asyncio.run(bidder.suggest("E", HAND, Auction("N", ["1H"]), "-"))
    assert s.call == "P"
