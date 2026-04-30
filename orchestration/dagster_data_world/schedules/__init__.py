from dagster import ScheduleDefinition
from dagster_data_world.jobs import spotify_pipeline_job, statsbomb_pipeline_job

spotify_daily_schedule = ScheduleDefinition(
    name="spotify_daily",
    job=spotify_pipeline_job,
    cron_schedule="0 6 * * *",  # 06:00 every day
)

statsbomb_weekly_schedule = ScheduleDefinition(
    name="statsbomb_weekly",
    job=statsbomb_pipeline_job,
    cron_schedule="0 2 * * 0",  # 02:00 every Sunday
)
