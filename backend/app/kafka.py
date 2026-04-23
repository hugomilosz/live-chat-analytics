from confluent_kafka import Producer
import json

producer = Producer({"bootstrap.servers": "127.0.0.1:9092"})


def send_message(message: dict) -> None:
    payload = json.dumps(message).encode("utf-8")

    while True:
        try:
            producer.produce("chat_raw", payload)
            producer.poll(0)
            return
        except BufferError:
            producer.poll(0.05)


def flush_producer(timeout: float = 5.0) -> int:
    return producer.flush(timeout)
