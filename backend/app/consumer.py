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

async def run(trigger_update):
    try:
        while True:
            msg = await asyncio.to_thread(consumer.poll, 0.1)
            
            if msg is None:
                continue
            if msg.error():
                continue

            data = json.loads(msg.value().decode())

            pipeline.ingest(data["username"], data["body"])

            trigger_update()
    except asyncio.CancelledError:
        pass
    finally:
        consumer.close()
