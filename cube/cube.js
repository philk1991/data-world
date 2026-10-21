// Cube configuration options: https://cube.dev/docs/config
//
// Cube reads the dbt marts from the DuckLake (Postgres catalog + Parquet files),
// not a .duckdb file. The driver opens an in-memory DuckDB, loads the ducklake and
// postgres extensions (CUBEJS_DB_DUCKDB_EXTENSIONS in .env), then runs initSql on
// every connection: attach the lake READ_ONLY and make it the default catalog so the
// model's unqualified `marts.*` names resolve. The lake locks per commit, so this can
// run alongside dbt builds and ingest jobs.
const path = require('path');
const { DuckDBDriver } = require('@cubejs-backend/duckdb-driver');

// Same defaults as data-ingestion/lake.py. DuckLake rejects any spelling of the
// data path other than the absolute one it was created with, so normalise it.
const catalog = process.env.LAKE_CATALOG || 'postgres:dbname=data_world_lake host=localhost';
const dataPath = path.resolve(process.env.LAKE_DATA_PATH || path.join(__dirname, '..', 'data', 'lake')) + '/';

/** @type{ import('@cubejs-backend/server-core').CreateOptions } */
module.exports = {
  driverFactory: () => new DuckDBDriver({
    databasePath: ':memory:',
    // IF NOT EXISTS: initSql runs per connection, and a failing ATTACH would skip the USE.
    initSql: `ATTACH IF NOT EXISTS 'ducklake:${catalog}' AS lake (DATA_PATH '${dataPath}', READ_ONLY); USE lake;`,
  }),
};
