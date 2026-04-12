from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .aggregation import ChatPipeline
from .models import ChatMessageIn
from .sample_data import random_message


app = FastAPI(title="Chat Analyser API")
pipeline = ChatPipeline()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/summary")
def get_summary():
    return pipeline.summary()


@app.post("/api/messages")
def post_message(message: ChatMessageIn):
    processed = pipeline.ingest(message.username, message.body)
    return {"status": "accepted", "message": processed}


@app.post("/api/simulate")
def simulate_messages(count: int = 12):
    inserted = []
    for _ in range(max(1, min(count, 100))):
        sample = random_message()
        inserted.append(pipeline.ingest(sample.username, sample.body))
    return {"status": "accepted", "inserted": inserted, "summary": pipeline.summary()}
