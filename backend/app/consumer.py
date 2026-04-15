import json
import asyncio
from confluent_kafka import Consumer
from .state import pipeline

consumer = Consumer({
    "bootstrap.servers": "127.0.0.1:9092",
    "group.id": "chat-analyser",
    "auto.offset.reset": "earliest"
})

consumer.subscribe(["chat_raw"])

async def run(broadcast_callback): 
    while True:
        msg = await asyncio.to_thread(consumer.poll, 1.0)
        
        if msg is None:
            continue
        if msg.error():
            continue

        data = json.loads(msg.value().decode())
        print(f"Consumer received message from: {data['username']}")

        pipeline.ingest(data["username"], data["body"])

        await broadcast_callback()