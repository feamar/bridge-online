from fastapi.testclient import TestClient

import bridge.table
import main
from bridge.bots import Suggestion
from bridge.table import TableRegistry

bridge.table.BOT_DELAY_SECONDS = 0


class FakeBen:
    """Stands in for BEN: the bots pass; as advisor it opens 2NT and passes otherwise."""

    name = "BEN"
    available = True

    async def suggest(self, seat, hand, auction, vulnerability):
        return Suggestion("P", "Geen bijzonderheden")

    async def bid(self, seat, hand, auction, vulnerability):
        return Suggestion("2NT" if not auction.calls[1:] else "P", "Uitnodiging")


def receive_until(ws, predicate):
    while True:
        msg = ws.receive_json()
        if msg["type"] == "state" and predicate(msg["state"]):
            return msg["state"]


def test_two_players_bid_together_and_get_review():
    fake = FakeBen()
    main.tables = TableRegistry(lambda: fake, fake)
    client = TestClient(main.app)
    host = client.post("/api/tables", json={"name": "Frank"}).json()
    guest = client.post(f"/api/tables/{host['table']}/join", json={"name": "Tobias"}).json()
    assert (host["seat"], guest["seat"]) == ("N", "S")
    assert client.post(f"/api/tables/{host['table']}/join", json={}).status_code == 409

    code = host["table"]
    with client.websocket_connect(f"/ws/{code}?token={host['token']}") as n, \
         client.websocket_connect(f"/ws/{code}?token={guest['token']}") as s:
        state = n.receive_json()["state"]
        assert state["board"] == 1 and state["dealer"] == "N"
        assert list(state["hands"]) == ["N"]  # only your own hand is visible
        assert state["toAct"] == "N"
        assert state["ai"] == {"name": "BEN", "available": True}

        n.send_json({"type": "call", "call": "1NT"})
        state = receive_until(s, lambda st: st["toAct"] == "S")
        assert state["calls"] == ["1NT", "P"]
        assert state["explanations"] == {"1": "Geen bijzonderheden"}
        s.send_json({"type": "call", "call": "3NT"})
        receive_until(n, lambda st: st["toAct"] == "N")
        n.send_json({"type": "call", "call": "P"})
        state = receive_until(s, lambda st: st["over"] and st["review"]["benStatus"] == "done")

        assert state["calls"] == ["1NT", "P", "3NT", "P", "P", "P"]
        assert state["contract"] == {"level": 3, "strain": "NT", "declarer": "N", "doubled": ""}
        assert len(state["hands"]) == 4  # all hands shown after the auction
        review = state["review"]
        assert review["dd"]["contract"]["tricks"] is not None
        assert [(r["call"], r["ben"], r["same"]) for r in review["ben"]] == [
            ("1NT", "2NT", False),
            ("3NT", "P", False),
            ("P", "P", True),
        ]

        n.send_json({"type": "next"})
        state = receive_until(n, lambda st: st["board"] == 2)
        assert state["review"] is None and state["calls"] == []


def test_unknown_token_is_rejected():
    client = TestClient(main.app)
    code = client.post("/api/tables", json={}).json()["table"]
    try:
        with client.websocket_connect(f"/ws/{code}?token=nope") as ws:
            ws.receive_json()
        assert False, "connection should have been closed"
    except Exception:
        pass


def test_config_endpoint():
    assert TestClient(main.app).get("/api/config").json()["ai"] in ("BEN", "Pas-robot")
