# YAML Conventions

## Purpose

dbt YAML is the primary source of context for AI agents working with this project. Column tests and
descriptions already exist — this convention adds a `meta:` block to every model that encodes the
things an agent cannot infer from schema or lineage alone.

---

## Meta schema

All fields live under `meta:` at the model level (not column level).

```yaml
models:
  - name: <model_name>
    description: <existing description>
    meta:
      grain: <required>
      purpose: <required>
      business_question: <required for marts only>
      seasonality: <optional>
      relationships:
        decomposes_into:       # required for marts + intermediate
          - "<model>: <explanation>"
        correlates_with:       # optional
          - "<model>: <explanation>"
        leads_to:              # optional
          - "<model>: <explanation>"
```

### Required by layer

| Field | Staging | Intermediate | Marts |
|---|---|---|---|
| `grain` | ✓ | ✓ | ✓ |
| `purpose` | ✓ | ✓ | ✓ |
| `business_question` | — | — | ✓ |
| `relationships.decomposes_into` | — | ✓ | ✓ |
| `seasonality` | optional | optional | optional |
| `relationships.correlates_with` | optional | optional | optional |

---

## Field definitions

### `grain`
What one row in this model represents. Must name the column(s) forming the natural key.

```yaml
# Good — names the actual columns
grain: one row per (artist_id, time_range)
grain: one row per match_id
grain: one row per (symbol, candle_open_time) at 1-minute resolution

# Bad — too vague
grain: one row per record
grain: trade-level data
```

### `purpose`
Why this model exists — what it *does*, not what it *contains*. 1–2 sentences.

```yaml
# Good — describes the transformation
purpose: Pivot artist rankings from three source rows per artist into a single
  comparison row, enabling side-by-side period analysis.

purpose: Clean and type raw Spotify top artist data, renaming columns and
  casting ingested_at for downstream consumption.

# Bad — describes the content, not the purpose
purpose: Contains artist rankings with columns for each time period.
```

### `business_question`
The specific question a person would ask this model. Written as a real question, not a description.
Marts only.

```yaml
# Good — sounds like something a human would ask
business_question: Which artists am I consistently into vs. recent obsessions?
business_question: What did hourly price action look like for charting?

# Bad — sounds like documentation
business_question: Provides artist ranking analysis across time periods.
```

### `seasonality`
Known data patterns — explain *why* they exist, not just that they exist.

```yaml
# Good — explains the cause
seasonality: Limited to the 50 most recent plays per ingest run. History beyond
  that window is lost unless the ingest runs frequently.

seasonality: Volume spikes during US market open (9am EST) and EU market open
  (9am GMT / 2pm CET). Weekend volume is significantly lower.

# Bad — states the obvious
seasonality: Data updates daily.
```

### `relationships`

**`decomposes_into`** — the upstream models this model is built from. Format: `"<model>: <explanation>"`

```yaml
decomposes_into:
  - "stg_top_artists: three rows per artist (one per time_range) before pivot"
  - "stg_sb_events: source of all event counts via conditional aggregation"
```

**`correlates_with`** — related models at the same conceptual level or grain.

```yaml
correlates_with:
  - "top_tracks_by_period: same three-period ranking structure applied to tracks"
  - "ohlcv_1m: 1h candles roll up from 1m candles"
```

**`leads_to`** — downstream models that depend on this one (optional, use when not obvious from lineage).

```yaml
leads_to:
  - "ohlcv_1h: rolled up from 1m candles in the same mart"
```

---

## Complete examples

### Staging model
```yaml
- name: stg_crypto_trades
  description: >
    Staged crypto trade ticks from Binance. One row per trade.
  meta:
    grain: one row per (symbol, trade_id)
    purpose: Clean and type raw Binance trade ticks, adding notional_value
      (price × quantity) and casting timestamps to TIMESTAMPTZ.
    seasonality: Volume spikes during US market open (9am EST) and EU market
      open (9am GMT). Weekend volume is significantly lower.
```

### Mart model
```yaml
- name: top_artists_by_period
  description: >
    One row per artist showing rankings across all three Spotify time periods.
  meta:
    grain: one row per artist_id
    purpose: Pivot artist rankings from three source rows per artist into a
      single comparison row, enabling side-by-side period analysis.
    business_question: Which artists am I consistently into vs. recent obsessions?
    seasonality: Rankings reflect a point-in-time snapshot from the last ingest.
      Short-term ranks shift quickly; long-term ranks are stable.
    relationships:
      decomposes_into:
        - "stg_top_artists: three rows per artist (one per time_range) before pivot"
      correlates_with:
        - "top_tracks_by_period: same three-period structure applied to tracks"
```
