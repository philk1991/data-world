#!/usr/bin/env python3
"""
Binance WebSocket → Kafka producer.

Streams real-time trade ticks for BTC/USDT and ETH/USDT from Binance's public
WebSocket API (no authentication required) and publishes each trade as a JSON
message to the Kafka topic 'crypto.trades'.

Usage (run from data-ingestion/):
    python -m crypto.producer

Requires:
    pip install confluent-kafka websockets
    Kafka running on localhost:9092
    (brew install kafka && brew services start kafka)
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import websockets
from confluent_kafka import Producer

KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC = "crypto.trades"
SYMBOLS = ["btcusdt", "ethusdt"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _delivery_report(err, msg):
    if err:
        log.error("Delivery failed for %s: %s", msg.key(), err)


def _make_producer() -> Producer:
    return Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "client.id": "crypto-producer",
    })


def _parse_trade(raw: dict) -> dict | None:
    if raw.get("e") != "trade":
        return None
    return {
        "trade_id":    raw["t"],
        "symbol":      raw["s"],
        "price":       float(raw["p"]),
        "quantity":    float(raw["q"]),
        "buyer_maker": raw["m"],
        "trade_time":  datetime.fromtimestamp(raw["T"] / 1000, tz=timezone.utc).isoformat(),
        "event_time":  datetime.fromtimestamp(raw["E"] / 1000, tz=timezone.utc).isoformat(),
    }


async def stream_symbol(symbol: str, producer: Producer) -> None:
    url = f"wss://stream.binance.com:9443/ws/{symbol}@trade"
    while True:
        try:
            async with websockets.connect(url) as ws:
                log.info("Connected to %s stream", symbol.upper())
                async for raw_msg in ws:
                    trade = _parse_trade(json.loads(raw_msg))
                    if trade:
                        producer.produce(
                            TOPIC,
                            key=trade["symbol"],
                            value=json.dumps(trade),
                            callback=_delivery_report,
                        )
                        producer.poll(0)
        except Exception as e:
            log.warning("Stream error for %s: %s — reconnecting in 5s", symbol, e)
            await asyncio.sleep(5)


async def main() -> None:
    producer = _make_producer()
    log.info("Starting producer → Kafka topic '%s'", TOPIC)
    try:
        await asyncio.gather(*(stream_symbol(s, producer) for s in SYMBOLS))
    finally:
        producer.flush()


if __name__ == "__main__":
    asyncio.run(main())
