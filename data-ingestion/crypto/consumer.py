#!/usr/bin/env python3
"""
Kafka → DuckDB consumer.

Reads trade messages from the 'crypto.trades' topic and appends them to
raw_crypto.raw_trades in DuckDB. Commits offsets after each batch write so
the consumer resumes cleanly after a restart without replaying old messages.

Usage (run from data-ingestion/):
    python -m crypto.consumer

Requires:
    pip install confluent-kafka duckdb python-dotenv
    Kafka running on localhost:9092
    (brew install kafka && brew services start kafka)
"""
import json
import logging
import os
import signal
from pathlib import Path

import duckdb
from confluent_kafka import Consumer, KafkaException
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC = "crypto.trades"
GROUP_ID = "crypto-consumer"
BATCH_SIZE = 100
POLL_TIMEOUT = 1.0

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "spotify.duckdb")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_running = True


def _handle_signal(sig, frame):
    global _running
    log.info("Shutdown signal received — draining and closing")
    _running = False


def _ensure_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw_crypto")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_crypto.raw_trades (
            trade_id    BIGINT,
            symbol      VARCHAR,
            price       DOUBLE,
            quantity    DOUBLE,
            buyer_maker BOOLEAN,
            trade_time  TIMESTAMPTZ,
            event_time  TIMESTAMPTZ,
            consumed_at TIMESTAMPTZ DEFAULT now()
        )
    """)


def _write_batch(conn: duckdb.DuckDBPyConnection, batch: list[dict]) -> None:
    conn.executemany("""
        INSERT INTO raw_crypto.raw_trades
            (trade_id, symbol, price, quantity, buyer_maker, trade_time, event_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        [
            t["trade_id"], t["symbol"], t["price"], t["quantity"],
            t["buyer_maker"], t["trade_time"], t["event_time"],
        ]
        for t in batch
    ])
    log.info("Wrote %d trades to raw_crypto.raw_trades", len(batch))


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    db_path = os.environ.get("DUCKDB_PATH", _DEFAULT_DB_PATH)
    conn = duckdb.connect(db_path)
    _ensure_table(conn)

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([TOPIC])
    log.info("Consuming from Kafka topic '%s' → DuckDB %s", TOPIC, db_path)

    batch: list[dict] = []

    try:
        while _running:
            msg = consumer.poll(POLL_TIMEOUT)

            if msg is None:
                if batch:
                    _write_batch(conn, batch)
                    consumer.commit()
                    batch = []
                continue

            if msg.error():
                raise KafkaException(msg.error())

            batch.append(json.loads(msg.value()))

            if len(batch) >= BATCH_SIZE:
                _write_batch(conn, batch)
                consumer.commit()
                batch = []
    finally:
        if batch:
            _write_batch(conn, batch)
            consumer.commit()
        consumer.close()
        conn.close()
        log.info("Consumer shut down cleanly")


if __name__ == "__main__":
    main()
