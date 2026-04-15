from confluent_kafka import Producer
import json

producer = Producer({"bootstrap.servers": "127.0.0.1:9092"})

def send_message(message: dict):
    producer.produce("chat_raw", json.dumps(message).encode("utf-8"))
    producer.flush()