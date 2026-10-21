from dagster import OpExecutionContext, job, op

import dagster_data_world.constants  # noqa: F401 — adds data-ingestion/ to sys.path
from dagster_data_world.resources import LakeResource
from lake import maintain_lake


@op(description="Compact the lake, expire snapshots older than 7 days and delete unreferenced files")
def maintain_lake_op(context: OpExecutionContext, lake: LakeResource) -> None:
    with lake.get_connection() as conn:
        stats = maintain_lake(conn, retain="7 days")
    for key, before in stats["before"].items():
        context.log.info(f"{key}: {before} -> {stats['after'][key]}")


@job(description="Weekly DuckLake maintenance (see data-ingestion/lake.py maintain_lake)")
def lake_maintenance_job():
    maintain_lake_op()
