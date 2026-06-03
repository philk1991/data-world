#!/usr/bin/env python3
"""
Kafka → DuckDB consumer (two topics).

Subscribes to both 'payments.requests' and 'payments.rejected' and appends each
message to the matching table in data/payments_raw.duckdb:

    raw_payments.raw_requests    (payment_id, amount, requested_at, consumed_at)
    raw_payments.raw_rejections  (payment_id, rejected_at, consumed_at)

Both tables are append-only — dedup and the request/rejection join happen in dbt.
No JSON sidecar (this build has no streaming dashboard); the dbt mart is the
serving layer.

Usage (run from data-ingestion/):
    python -m payments.consumer
"""
import json
import logging
import os
import signal
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from confluent_kafka import Consumer, KafkaException
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

KAFKA_BOOTSTRAP = "localhost:9092"
REQUESTS_TOPIC  = "payments.requests"
REJECTED_TOPIC  = "payments.rejected"
GROUP_ID        = "payments-consumer"
BATCH_SIZE      = 100
POLL_TIMEOUT    = 1.0

_DEFAULT_PAYMENTS_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "payments_raw.duckdb")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_running = True


def _handle_signal(sig, frame):
    global _running
    log.info("Shutdown signal received — draining")
    _running = False


def _ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_payments")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_payments.raw_requests (
            payment_id   VARCHAR,
            amount       DOUBLE,
            requested_at TIMESTAMPTZ,
            consumed_at  TIMESTAMPTZ DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_payments.raw_rejections (
            payment_id   VARCHAR,
            rejected_at  TIMESTAMPTZ,
            consumed_at  TIMESTAMPTZ DEFAULT now()
        )
    """)


def _flush_db(db_path: str, requests: list[dict], rejections: list[dict]) -> None:
    """Write both batches to DuckDB. Connection opened and closed each call."""
    conn = duckdb.connect(db_path)
    _ensure_schema(conn)
    if requests:
        conn.executemany(
            "INSERT INTO raw_payments.raw_requests (payment_id, amount, requested_at) VALUES (?, ?, ?)",
            [[r["payment_id"], r["amount"], r["requested_at"]] for r in requests],
        )
    if rejections:
        conn.executemany(
            "INSERT INTO raw_payments.raw_rejections (payment_id, rejected_at) VALUES (?, ?)",
            [[r["payment_id"], r["rejected_at"]] for r in rejections],
        )
    conn.close()
    log.info("Wrote %d requests, %d rejections to DuckDB", len(requests), len(rejections))


def main() -> None:
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    db_path = os.environ.get("PAYMENTS_DB_PATH", _DEFAULT_PAYMENTS_DB_PATH)

    consumer = Consumer({
        "bootstrap.servers":  KAFKA_BOOTSTRAP,
        "group.id":           GROUP_ID,
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([REQUESTS_TOPIC, REJECTED_TOPIC])
    log.info("Consuming '%s' + '%s' → %s", REQUESTS_TOPIC, REJECTED_TOPIC, db_path)

    requests: list[dict]   = []
    rejections: list[dict] = []

    def _drain() -> None:
        nonlocal requests, rejections
        if requests or rejections:
            _flush_db(db_path, requests, rejections)
            consumer.commit()
            requests, rejections = [], []

    try:
        while _running:
            msg = consumer.poll(POLL_TIMEOUT)

            if msg is None:
                _drain()
                continue

            if msg.error():
                raise KafkaException(msg.error())

            record = json.loads(msg.value())
            if msg.topic() == REQUESTS_TOPIC:
                requests.append(record)
            else:
                rejections.append(record)

            if len(requests) + len(rejections) >= BATCH_SIZE:
                _drain()
    finally:
        _drain()
        consumer.close()
        log.info("Consumer shut down cleanly")


if __name__ == "__main__":
    main()
