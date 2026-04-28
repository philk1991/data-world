# Crypto Streaming Pipeline

Real-time trade data from Binance → Kafka → DuckDB → dbt OHLCV models.

## Architecture

```
Binance WebSocket  →  Kafka (local)  →  DuckDB (raw_crypto schema)  →  dbt-crypto
  (producer.py)       crypto.trades      raw_trades table               OHLCV marts
```

## Prerequisites

### 1. Install Kafka via Homebrew

```bash
brew install kafka
```

Kafka ships with KRaft mode enabled by default (no Zookeeper required).

### 2. Start Kafka

```bash
brew services start kafka
```

Kafka runs on `localhost:9092`. To stop it:

```bash
brew services stop kafka
```

### 3. Create the Kafka topic

```bash
kafka-topics --create \
  --topic crypto.trades \
  --bootstrap-server localhost:9092 \
  --partitions 2 \
  --replication-factor 1
```

Verify it was created:

```bash
kafka-topics --list --bootstrap-server localhost:9092
```

### 4. Install Python dependencies

From the project root:

```bash
pip install confluent-kafka websockets
```

## Running the pipeline

Run the producer and consumer in separate terminal windows.

### Terminal 1 — Producer (Binance → Kafka)

```bash
cd data-ingestion
python -m crypto.producer
```

Streams BTC/USDT and ETH/USDT trade ticks from Binance's public WebSocket.
No API key required. Reconnects automatically on disconnect.

### Terminal 2 — Consumer (Kafka → DuckDB)

```bash
cd data-ingestion
python -m crypto.consumer
```

Reads from the `crypto.trades` topic and appends rows to `raw_crypto.raw_trades`
in DuckDB. Commits offsets after each batch — safe to restart.

Stop either process with `Ctrl+C`.

## Running dbt transforms

Crypto models live inside the main `dbt/` project under `staging/crypto/` and `marts/crypto/`.

```bash
cd dbt
dbt run --select staging.crypto+ marts.crypto+    # build staging views + OHLCV tables
dbt test --select staging.crypto+ marts.crypto+   # run schema tests
```

The OHLCV mart models are incremental — each `dbt run` appends only new candles.

### dbt tasks (via Taskfile)

```bash
task dbt:crypto:run     # run all crypto models
task dbt:crypto:test    # test all crypto models
task dbt:crypto:build   # run + test
```

## Schema layout

| Schema           | Tables                          | Written by   |
|------------------|---------------------------------|--------------|
| `raw_crypto`     | `raw_trades`                    | consumer.py  |
| `staging_crypto` | `stg_crypto_trades`             | dbt-crypto   |
| `marts`          | `ohlcv_1m`, `ohlcv_1h`         | dbt-crypto   |

## Monitoring Kafka

Inspect messages in the topic:

```bash
kafka-console-consumer \
  --topic crypto.trades \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --max-messages 5
```

Check consumer group lag:

```bash
kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group crypto-consumer
```
