import duckdb as duckdb_lib
from dagster import RunRequest, SensorEvaluationContext, sensor

from dagster_data_world.constants import CRYPTO_DUCKDB_PATH
from dagster_data_world.jobs import crypto_dbt_job


@sensor(job=crypto_dbt_job, minimum_interval_seconds=300)
def crypto_new_data_sensor(context: SensorEvaluationContext):
    """Polls crypto_raw.duckdb every 5 minutes.

    Triggers the crypto dbt job whenever new trade rows have landed from the
    Kafka consumer. The cursor tracks the last known row count so only genuine
    growth causes a run.
    """
    try:
        conn = duckdb_lib.connect(CRYPTO_DUCKDB_PATH, read_only=True)
        count: int = conn.execute(
            "SELECT COUNT(*) FROM raw_crypto.raw_trades"
        ).fetchone()[0]
        conn.close()
    except Exception as e:
        context.log.warning(f"Could not query crypto_raw.duckdb: {e}")
        return

    last_count = int(context.cursor) if context.cursor else 0
    if count > last_count:
        context.update_cursor(str(count))
        context.log.info(f"New trades detected ({last_count} → {count}), triggering dbt run")
        yield RunRequest(run_key=str(count))
