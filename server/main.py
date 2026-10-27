"""Web server: serves the app and runs the practice tables.

Start with:  python -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bridge.auction import IllegalCall
from bridge.bots import PassBidder
from bridge.table import TableRegistry

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Bridge Online")
tables = TableRegistry(PassBidder)


class JoinRequest(BaseModel):
    name: str = ""


@app.post("/api/tables")
async def create_table(req: JoinRequest):
    table = tables.create()
    seat, token = table.join(req.name)
    return {"table": table.id, "seat": seat, "token": token}


@app.post("/api/tables/{code}/join")
async def join_table(code: str, req: JoinRequest):
    table = tables.get(code)
    if table is None:
        raise HTTPException(404, "Tafel niet gevonden.")
    try:
        seat, token = table.join(req.name)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"table": table.id, "seat": seat, "token": token}


@app.websocket("/ws/{code}")
async def play(ws: WebSocket, code: str, token: str):
    table = tables.get(code)
    seat = table.seat_for_token(token) if table else None
    if seat is None:
        await ws.close(code=4404)
        return
    await ws.accept()

    async def push():
        await ws.send_json({"type": "state", "state": table.view(seat)})

    table.listeners.add(push)
    try:
        await push()
        # A fresh table may start with a bot as dealer.
        asyncio.create_task(table.run_bots())
        while True:
            msg = await ws.receive_json()
            try:
                if msg.get("type") == "call":
                    await table.call(seat, str(msg.get("call", "")))
                elif msg.get("type") == "next":
                    if table.board.auction.is_over:
                        await table.next_board()
            except (IllegalCall, ValueError) as e:
                await ws.send_json({"type": "error", "message": str(e) or "Ongeldig bod."})
    except WebSocketDisconnect:
        pass
    finally:
        table.listeners.discard(push)


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
