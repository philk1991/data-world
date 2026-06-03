# Payments Streaming Pipeline

Near-real-time payment accept/reject analytics. Two Kafka topics → DuckDB → dbt.

A practice build for the design problem: *"payments arrive on one topic; rejections
arrive on a second topic up to 10 minutes later. Build a dbt model feeding a
near-real-time dashboard of accepted vs rejected counts and $ amounts over time."*

## Architecture

```
synthetic producer  →  Kafka (local)        →  DuckDB (raw_payments)   →  dbt-payments
  (producer.py)        payments.requests        raw_requests              payment_status
                       payments.rejected        raw_rejections            payments_by_minute
```

The hard part is the **late-arriving rejection**: when a payment first appears we
cannot know its outcome. A payment is `pending` until either a rejection lands or
the 10-minute grace window elapses (→ `accepted`). dbt resolves this with an
incremental model plus a bounded look-back window — see `dbt/models/marts/payments/`.

## Prerequisites

### 1–2. Install and start Kafka

```bash
brew install kafka
brew services start kafka     # KRaft mode, runs on localhost:9092
```

### 3. Create the two topics

```bash
kafka-topics --create --topic payments.requests \
  --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1

kafka-topics --create --topic payments.rejected \
  --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1

kafka-topics --list --bootstrap-server localhost:9092
```

### 4. Install Python dependencies

```bash
pip install confluent-kafka
```

## Running the pipeline

Run the producer and consumer in separate terminals.

### Terminal 1 — Producer (synthetic payments → Kafka)

```bash
task payments:producer
# or: cd data-ingestion && python -m payments.producer
```

Emits ~20 payments/s to `payments.requests`; ~15% are rejected, with the rejection
published to `payments.rejected` after a random 0–10 minute delay.

### Terminal 2 — Consumer (Kafka → DuckDB)

```bash
task payments:consumer
# or: cd data-ingestion && python -m payments.consumer
```

Routes each topic into `raw_payments.raw_requests` / `raw_payments.raw_rejections`
in `data/payments_raw.duckdb`. Append-only; commits offsets after each batch —
safe to restart. Stop either process with `Ctrl+C`.

## Running dbt transforms

```bash
task dbt:payments:build      # run + test staging views + marts
# or:
task dbt:payments:run
task dbt:payments:test
```

The marts are **incremental**. Re-run after a minute to watch `pending` payments
settle into `accepted` / `rejected` as the grace window closes and late rejections
arrive — the look-back window re-resolves the recent tail on each run.

## Schema layout

| Schema             | Tables                              | Written by   |
|--------------------|-------------------------------------|--------------|
| `raw_payments`     | `raw_requests`, `raw_rejections`    | consumer.py  |
| `staging_payments` | `stg_payments__requests`, `stg_payments__rejections` | dbt-payments |
| `marts`            | `payment_status`, `payments_by_minute` | dbt-payments |

## Inspecting the data

```bash
# Raw landing
duckdb data/payments_raw.duckdb "select count(*) from raw_payments.raw_requests"

# Outcome distribution (after dbt build) — expect a small pending tail
duckdb data/spotify.duckdb "select status, count(*) from marts.payment_status group by 1"

# The dashboard serving query
duckdb data/spotify.duckdb \
  "select * from marts.payments_by_minute order by request_minute desc limit 20"
```
