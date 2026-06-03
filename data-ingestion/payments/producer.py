#!/usr/bin/env python3
"""
Synthetic payments → Kafka producer (two topics).

Simulates a payment processor emitting two independent event streams, mirroring
the Paddle design problem:

    payments.requests   one event per payment attempt (payment_id, amount, requested_at)
    payments.rejected   a later event for the subset that get rejected
                        (payment_id, rejected_at) — arrives 0–10 minutes AFTER the request

A fraction of payments (REJECT_RATE) are rejected. Each rejection is scheduled
with a random delay drawn from [0, MAX_REJECT_DELAY_S], so the consumer/dbt layer
has to cope with rejections that land long after the original request — the whole
point of the exercise.

Usage (run from data-ingestion/):
    python -m payments.producer

Requires:
    pip install confluent-kafka
    Kafka running on localhost:9092
    Topics 'payments.requests' and 'payments.rejected' created (see README).
"""
import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

KAFKA_BOOTSTRAP = "localhost:9092"
REQUESTS_TOPIC  = "payments.requests"
REJECTED_TOPIC  = "payments.rejected"

PAYMENTS_PER_SECOND = 20          # synthetic request throughput
REJECT_RATE         = 0.15        # fraction of payments that get rejected
MAX_REJECT_DELAY_S  = 600         # rejection arrives up to 10 minutes late

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _delivery_report(err, msg):
    if err:
        log.error("Delivery failed for %s: %s", msg.key(), err)


def _make_producer() -> Producer:
    return Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "client.id": "payments-producer",
    })


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_request() -> dict:
    # Lognormal gives a realistic right-skewed payment distribution
    # (lots of small payments, a long tail of large ones).
    amount = round(random.lognormvariate(mu=3.2, sigma=1.0), 2)
    return {
        "payment_id":   str(uuid.uuid4()),
        "amount":       amount,
        "requested_at": _now_iso(),
    }


def _publish(producer: Producer, topic: str, key: str, value: dict) -> None:
    producer.produce(topic, key=key, value=json.dumps(value), callback=_delivery_report)
    producer.poll(0)


async def _schedule_rejection(producer: Producer, payment_id: str) -> None:
    """Wait a random late-arrival delay, then publish the rejection event."""
    delay = random.uniform(0, MAX_REJECT_DELAY_S)
    await asyncio.sleep(delay)
    _publish(producer, REJECTED_TOPIC, payment_id, {
        "payment_id":  payment_id,
        "rejected_at": _now_iso(),
    })
    log.info("Rejected %s after %.0fs", payment_id, delay)


async def main() -> None:
    producer = _make_producer()
    interval = 1.0 / PAYMENTS_PER_SECOND
    log.info(
        "Producing ~%d payments/s → '%s' (%.0f%% rejected, up to %ds late) → '%s'",
        PAYMENTS_PER_SECOND, REQUESTS_TOPIC, REJECT_RATE * 100,
        MAX_REJECT_DELAY_S, REJECTED_TOPIC,
    )
    try:
        while True:
            request = _make_request()
            _publish(producer, REQUESTS_TOPIC, request["payment_id"], request)

            if random.random() < REJECT_RATE:
                # Fire-and-forget — the rejection lands later, independently.
                asyncio.create_task(_schedule_rejection(producer, request["payment_id"]))

            await asyncio.sleep(interval)
    finally:
        producer.flush()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Producer stopped")
