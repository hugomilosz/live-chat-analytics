# Chat Analyser

Chat Analyser is a real-time moderation analytics tool for live chat. It ingests chat messages via a message broker, normalises noisy text, groups repeated or similar messages, and streams live signals to a dashboard for moderators and streamers via WebSockets.

## Features

- ingest structured chat messages with `username` and `body`
- highly durable message queuing using a Redpanda (Kafka) broker
- real-time dashboard updates via WebSockets
- normalise Unicode text and common typo patterns
- recognise keyboard-adjacent typo variants during clustering
- group near-duplicate messages into spam clusters
- group related messages into shared topic phrases without forcing them into the same spam cluster

### Pipeline

1. The backend API receives a chat message.
2. The API instantly publishes the message to the `chat_raw` Kafka topic in Redpanda.
3. A background consumer (running asynchronously inside the FastAPI event loop) pulls the message.
4. The message is normalised:
   - lowercased
   - Unicode normalised
   - repeated punctuation reduced
   - common typo variants corrected
5. The message is matched to an existing spam cluster if it is similar enough to recent examples.
   - token overlap is typo-aware
   - nearby-key substitutions and transpositions are treated as similar
6. The system updates aggregate state:
   - recent message count
   - active users
   - likely spam clusters using message similarity
   - topic groups based on shared subject phrases
   - top topic terms
7. The backend broadcasts the updated state to all connected frontend clients via WebSockets.

## Dashboard signals

- `Spam Clusters` are for near-duplicate messages such as `this game sux`, `this game suxx`, and `this gaem sucks`.
- `Topic Groups` are broader subject buckets such as `this game` or `stream audio`. Messages can share a topic group even when they are not duplicates, for example `this game is bad` and `this game is good`.

## Tech stack

- FastAPI
- Redpanda (Kafka) & `confluent-kafka`
- WebSockets
- Pydantic
- React
- Vite

## Project structure

```text
backend/
  app/
    aggregation.py
    consumer.py
    kafka.py
    main.py
    models.py
    normalisation.py
    sample_data.py
    state.py
  requirements.txt
frontend/
  src/
    App.jsx
    main.jsx
    styles.css
  index.html
  package.json
  vite.config.js
```

## Run locally

### 1. Start the Message Broker (Redpanda)

You must have Docker running.

```bash
docker run -d \
  --name redpanda \
  -p 9092:9092 \
  docker.redpanda.com/redpandadata/redpanda:latest \
  redpanda start \
    --overprovisioned \
    --smp 1 \
    --memory 1G \
    --reserve-memory 0M \
    --node-id 0 \
    --check=false \
    --kafka-addr PLAINTEXT://0.0.0.0:9092 \
    --advertise-kafka-addr PLAINTEXT://127.0.0.1:9092
```

### 2. Start the Backend

Starting Uvicorn will simultaneously boot up the HTTP API, the WebSocket server, and the background Kafka consumer.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend API: `http://127.0.0.1:8000`
Interactive Docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Run tests

```bash
cd backend
source .venv/bin/activate
pytest tests -q
```

## API

### `GET /health`

Simple health check.

### `GET /api/summary`

Returns the current dashboard summary.

### `POST /api/messages`

Accepts a single chat message and publishes it to the Kafka broker:

```json
{
  "username": "demo_user",
  "body": "this project is awesome!!!"
}
```

### `POST /api/simulate?count=15`

Loads sample chat messages into the pipeline for testing the dashboard.
