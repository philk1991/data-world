#!/usr/bin/env python3
"""
Kafka → DuckDB consumer.

Reads trade messages from the 'crypto.trades' topic and appends them to
raw_crypto.raw_trades in DuckDB. After each batch it also writes
data/live_data.json so the dashboard can read live prices and recent trades
without ever touching the DuckDB file (avoiding lock conflicts).

Usage (run from data-ingestion/):
    python -m crypto.consumer
"""
import json
import logging
import os
import signal
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from confluent_kafka import Consumer, KafkaException
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC           = "crypto.trades"
GROUP_ID        = "crypto-consumer"
BATCH_SIZE      = 100
POLL_TIMEOUT    = 1.0

_DEFAULT_CRYPTO_DB_PATH  = str(Path(__file__).parent.parent.parent / "data" / "crypto_raw.duckdb")
_DEFAULT_LIVE_JSON_PATH  = str(Path(__file__).parent.parent.parent / "data" / "live_data.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_running = True

# In-memory state for the live JSON sidecar
_latest: dict[str, dict]  = {}          # symbol → most recent trade
_counts: dict[str, int]   = defaultdict(int)
_volumes: dict[str, float] = defaultdict(float)
_recent: deque            = deque(maxlen=40)


def _handle_signal(sig, frame):
    global _running
    log.info("Shutdown signal received — draining")
    _running = False


def _flush_db(db_path: str, batch: list[dict]) -> None:
    """Write batch to DuckDB. Connection is opened and closed each call."""
    conn = duckdb.connect(db_path)
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
    conn.executemany("""
        INSERT INTO raw_crypto.raw_trades
            (trade_id, symbol, price, quantity, buyer_maker, trade_time, event_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        [t["trade_id"], t["symbol"], t["price"], t["quantity"],
         t["buyer_maker"], t["trade_time"], t["event_time"]]
        for t in batch
    ])
    conn.close()
    log.info("Wrote %d trades to DuckDB", len(batch))


def _flush_json(json_path: str, batch: list[dict]) -> None:
    """Update in-memory state and atomically overwrite live_data.json."""
    for t in batch:
        sym = t["symbol"]
        _latest[sym] = t
        _counts[sym]  += 1
        _volumes[sym] += t["quantity"]
        _recent.appendleft(t)

    prices = [
        {
            "symbol":       sym,
            "price":        _latest[sym]["price"],
            "updated_at":   _latest[sym]["trade_time"],
            "total_trades": _counts[sym],
            "total_volume": round(_volumes[sym], 6),
        }
        for sym in sorted(_latest)
    ]

    trades = [
        {
            "trade_id":    t["trade_id"],
            "symbol":      t["symbol"],
            "price":       t["price"],
            "quantity":    t["quantity"],
            "notional":    round(t["price"] * t["quantity"], 2),
            "buyer_maker": t["buyer_maker"],
            "trade_time":  t["trade_time"],
        }
        for t in _recent
    ]

    payload = json.dumps({"prices": prices, "trades": trades})
    tmp = json_path + ".tmp"
    with open(tmp, "w") as f:
        f.write(payload)
    os.replace(tmp, json_path)  # atomic on POSIX


def main() -> None:
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    db_path   = os.environ.get("CRYPTO_DB_PATH",  _DEFAULT_CRYPTO_DB_PATH)
    json_path = os.environ.get("LIVE_JSON_PATH",  _DEFAULT_LIVE_JSON_PATH)

    consumer = Consumer({
        "bootstrap.servers":  KAFKA_BOOTSTRAP,
        "group.id":           GROUP_ID,
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([TOPIC])
    log.info("Consuming '%s' → DuckDB + %s", TOPIC, json_path)

    batch: list[dict] = []

    try:
        while _running:
            msg = consumer.poll(POLL_TIMEOUT)

            if msg is None:
                if batch:
                    _flush_db(db_path, batch)
                    _flush_json(json_path, batch)
                    consumer.commit()
                    batch = []
                continue

            if msg.error():
                raise KafkaException(msg.error())

            batch.append(json.loads(msg.value()))

            if len(batch) >= BATCH_SIZE:
                _flush_db(db_path, batch)
                _flush_json(json_path, batch)
                consumer.commit()
                batch = []
    finally:
        if batch:
            _flush_db(db_path, batch)
            _flush_json(json_path, batch)
            consumer.commit()
        consumer.close()
        log.info("Consumer shut down cleanly")


if __name__ == "__main__":
    main()
