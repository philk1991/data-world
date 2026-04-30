from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from dagster_data_world.constants import DBT_PROJECT_DIR

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)
# manifest.json is pre-compiled via `task dbt:parse` (or any dbt run/build/compile).
# Run that task after adding or renaming models so Dagster picks up the changes.


class _DataWorldDbtTranslator(DagsterDbtTranslator):
    """Assigns each dbt model to a Dagster group based on its folder path.

    models/staging/spotify/* and models/marts/spotify/* → spotify_dbt
    models/staging/statsbomb/* and models/marts/statsbomb/* → statsbomb_dbt
    models/staging/crypto/* and models/marts/crypto/* → crypto_dbt
    """

    def get_group_name(self, dbt_resource_props: dict) -> str:
        path: str = dbt_resource_props.get("original_file_path", "")
        if "spotify" in path:
            return "spotify_dbt"
        if "statsbomb" in path:
            return "statsbomb_dbt"
        if "crypto" in path:
            return "crypto_dbt"
        return "dbt"


@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
    select="package:spotify",  # all user models; excludes the elementary package
    dagster_dbt_translator=_DataWorldDbtTranslator(),
)
def all_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
