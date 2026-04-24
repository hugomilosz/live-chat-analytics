import json
import asyncio
from confluent_kafka import Consumer

from .config import (
    KAFKA_AUTO_OFFSET_RESET,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_TOPIC_CHAT_RAW,
)
from .state import pipeline

consumer = Consumer({
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "group.id": KAFKA_CONSUMER_GROUP,
    "auto.offset.reset": KAFKA_AUTO_OFFSET_RESET,
})

consumer.subscribe([KAFKA_TOPIC_CHAT_RAW])

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
