from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .aggregation import ChatPipeline
from .models import ChatMessageIn
from .sample_data import random_message

import asyncio


app = FastAPI(title="Chat Analyser API")
pipeline = ChatPipeline()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

subscribers = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscribers.append(websocket)
    try:
        while True:
            # BLocks until a message is received/conenction drops
            await websocket.receive_text()
    except WebSocketDisconnect:
        subscribers.remove(websocket)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary():
    return pipeline.summary()

async def broadcast_summary():
    summary_data = pipeline.summary().model_dump()
    # Iterate over copy of the list
    for ws in subscribers.copy():
        try:
            await ws.send_json(summary_data)
        except Exception as e:
            print(f"WebSocket Error: {e}")
            subscribers.remove(ws)


@app.post("/api/messages")
async def post_message(message: ChatMessageIn):
    processed = pipeline.ingest(message.username, message.body)
    await broadcast_summary()

    return {"status": "accepted", "message": processed}


@app.post("/api/simulate")
async def simulate_messages(count: int = 12):
    inserted = []
    for _ in range(max(1, min(count, 100))):
        sample = random_message()
        inserted.append(pipeline.ingest(sample.username, sample.body))
    await broadcast_summary()
    
    return {"status": "accepted", "inserted": inserted, "summary": pipeline.summary()}
