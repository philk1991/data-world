# data-ingestion

Python ingestion scripts for all three data sources. All commands run from the project root via [Task](https://taskfile.dev).

## Sources

### Spotify (batch)

Pulls top artists, top tracks, and recently played history from the [Spotify Web API](https://developer.spotify.com/documentation/web-api). Requires a Spotify Developer app and OAuth — a browser window opens on first run to authorise access; the token is cached for subsequent runs.

| Entry point | Destination | Task commands |
|---|---|---|
| `data-ingestion/ingest.py` | `data/spotify.duckdb` → `raw_spotify.*` | `task ingest`, `task ingest:no-cache-clear` |

See [data-ingestion/spotify/](spotify/) for OAuth setup and output table schemas.

### StatsBomb (batch)

Fetches free open football data (competitions, matches, events, lineups) from the [StatsBomb open-data GitHub repository](https://github.com/statsbomb/open-data). No authentication required. Ingestion is incremental — already-loaded matches are skipped.

| Entry point | Destination | Task command |
|---|---|---|
| `data-ingestion/ingest_statsbomb.py` | `data/spotify.duckdb` → `raw_statsbomb.*` | `task ingest:statsbomb` |

### Crypto — Binance (streaming)

Streams real-time trade ticks for BTC/USDT and ETH/USDT from the [Binance public WebSocket API](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams). No authentication required. Runs as two long-lived processes: a producer that pushes ticks into a Kafka topic, and a consumer that reads from Kafka and writes to DuckDB plus a live JSON sidecar.

| Component | Entry point | Destination | Task command |
|---|---|---|---|
| Producer | `data-ingestion/crypto/producer.py` | Kafka `crypto.trades` topic | `task crypto:producer` |
| Consumer | `data-ingestion/crypto/consumer.py` | `data/crypto_raw.duckdb` + `data/live_data.json` | `task crypto:consumer` |

See [data-ingestion/crypto/README.md](crypto/README.md) for Kafka setup and topic configuration.
