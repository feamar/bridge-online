from fastapi.testclient import TestClient

import bridge.table
import main

bridge.table.BOT_DELAY_SECONDS = 0


def test_two_players_bid_together():
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

        n.send_json({"type": "call", "call": "1NT"})
        # East passes automatically, then it is South's turn.
        while True:
            state = s.receive_json()["state"]
            if state["toAct"] == "S":
                break
        assert state["calls"] == ["1NT", "P"]
        s.send_json({"type": "call", "call": "3NT"})
        # West passes, North passes, East passes: auction over.
        while True:
            state = n.receive_json()["state"]
            if state["toAct"] == "N":
                break
        n.send_json({"type": "call", "call": "P"})
        while True:
            state = s.receive_json()["state"]
            if state["over"]:
                break
        assert state["calls"] == ["1NT", "P", "3NT", "P", "P", "P"]
        assert state["contract"] == {"level": 3, "strain": "NT", "declarer": "N", "doubled": ""}
        assert len(state["hands"]) == 4  # all hands shown after the auction


def test_unknown_token_is_rejected():
    client = TestClient(main.app)
    code = client.post("/api/tables", json={}).json()["table"]
    try:
        with client.websocket_connect(f"/ws/{code}?token=nope") as ws:
            ws.receive_json()
        assert False, "connection should have been closed"
    except Exception:
        pass
