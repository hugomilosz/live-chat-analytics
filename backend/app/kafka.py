from confluent_kafka import Producer
import json

from .config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_CHAT_RAW

producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})


def send_message(message: dict) -> None:
    payload = json.dumps(message).encode("utf-8")

    while True:
        try:
            producer.produce(KAFKA_TOPIC_CHAT_RAW, payload)
            producer.poll(0)
            return
        except BufferError:
            producer.poll(0.05)


def flush_producer(timeout: float = 5.0) -> int:
    return producer.flush(timeout)
