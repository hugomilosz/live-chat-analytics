from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, SUMMARY_BROADCAST_DEBOUNCE_SECONDS
from .models import ChatMessageIn
from .sample_data import random_message
from .kafka import flush_producer, send_message
from .state import pipeline
from .consumer import run as start_kafka_consumer

broadcast_event = asyncio.Event()
subscribers: list[WebSocket] = []


async def broadcaster_loop():
    while True:
        await broadcast_event.wait()
        broadcast_event.clear()

        # Batch messages so the dashboard gets one update.
        await asyncio.sleep(SUMMARY_BROADCAST_DEBOUNCE_SECONDS)
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
        return_exceptions=True,
    )
    await asyncio.to_thread(flush_producer)


app = FastAPI(title="Chat Analyser API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    subscribers.append(websocket)
    try:
        while True:
            # Keep the connection open until the client disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in subscribers:
            subscribers.remove(websocket)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary():
    return pipeline.summary()


async def broadcast_summary():
    summary_data = pipeline.summary().model_dump(mode="json")
    for ws in subscribers.copy():
        try:
            await ws.send_json(summary_data)
        except Exception as error:
            print(f"WebSocket Error: {error}")
            if ws in subscribers:
                subscribers.remove(ws)


def queue_message(message: ChatMessageIn | dict[str, Any]) -> dict[str, Any]:
    payload = message if isinstance(message, dict) else message.model_dump()
    send_message(payload)
    return payload


@app.post("/api/messages")
async def post_message(message: ChatMessageIn):
    queue_message(message)
    return {"status": "accepted"}


@app.post("/api/simulate")
async def simulate_messages(count: int = 12):
    queued = []
    for _ in range(max(1, min(count, 100))):
        sample = random_message()
        queued.append(queue_message(sample))

    return {"status": "accepted", "inserted": queued}
