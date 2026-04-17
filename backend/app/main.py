from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import ChatMessageIn
from .sample_data import random_message
from .kafka import send_message
from .state import pipeline
from .consumer import run as start_kafka_consumer

broadcast_event = asyncio.Event()

async def broadcaster_loop():
    while True:
        # Wait until the consumer pings and reset
        await broadcast_event.wait()
        broadcast_event.clear()
        
        # Wait in case other messages arrive right after and broadcast
        await asyncio.sleep(0.2)
        if subscribers:
            await broadcast_summary()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting background Kafka consumer...")
    consumer_task = asyncio.create_task(start_kafka_consumer(broadcast_event.set))
    broadcaster_task = asyncio.create_task(broadcaster_loop())
    yield
    print("Stopping background Kafka consumer...")
    consumer_task.cancel()
    broadcaster_task.cancel()

    await asyncio.gather(
        consumer_task,
        broadcaster_task,
        return_exceptions=True
    )

app = FastAPI(title="Chat Analyser API", lifespan=lifespan)

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
            # Blocks until a message is received/conenction drops
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
    summary_data = pipeline.summary().model_dump(mode='json')
    # Iterate over copy of the list
    for ws in subscribers.copy():
        try:
            await ws.send_json(summary_data)
        except Exception as e:
            print(f"WebSocket Error: {e}")
            subscribers.remove(ws)


@app.post("/api/messages")
async def post_message(message: ChatMessageIn):
    send_message(message.model_dump())
    return {"status": "accepted"}


@app.post("/api/simulate")
async def simulate_messages(count: int = 12):
    inserted = []
    for _ in range(max(1, min(count, 100))):
        sample = random_message()
        inserted.append(pipeline.ingest(sample.username, sample.body))
    await broadcast_summary()
    
    return {"status": "accepted", "inserted": inserted, "summary": pipeline.summary()}
