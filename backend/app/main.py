from __future__ import annotations

from fastapi import FastAPI, WebSocket
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
            # push when data changes
            await asyncio.sleep(1000)
    except:
        subscribers.remove(websocket)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary():
    return pipeline.summary()


@app.post("/api/messages")
async def post_message(message: ChatMessageIn):
    processed = pipeline.ingest(message.username, message.body)
    for ws in subscribers:
        try:
            await ws.send_json(pipeline.summary())
        except:
            subscribers.remove(ws)

    return {"status": "accepted", "message": processed}


@app.post("/api/simulate")
async def simulate_messages(count: int = 12):
    inserted = []
    for _ in range(max(1, min(count, 100))):
        sample = random_message()
        inserted.append(pipeline.ingest(sample.username, sample.body))
    for ws in subscribers:
        try:
            await ws.send_json(pipeline.summary())
        except:
            subscribers.remove(ws)
    return {"status": "accepted", "inserted": inserted, "summary": pipeline.summary()}
