import { DuckDBInstance } from '@duckdb/node-api';
import { resolve } from 'path';

// The dashboard reads the DuckLake (Postgres catalog + Parquet files) through an
// in-memory DuckDB with the lake attached READ_ONLY. The lake locks per commit, so
// this can run alongside dbt builds and ingest jobs. Same defaults as
// data-ingestion/lake.py; DuckLake rejects any spelling of the data path other
// than the absolute one it was created with, so it's resolved here.
const LAKE_CATALOG = process.env.LAKE_CATALOG ?? 'postgres:dbname=data_world_lake host=localhost';
const LAKE_DATA_PATH =
  resolve(process.env.LAKE_DATA_PATH ?? resolve(process.cwd(), '../../data/lake')) + '/';

const ready = (async () => {
  const instance = await DuckDBInstance.create(':memory:');
  const conn = await instance.connect();
  await conn.run('INSTALL ducklake; LOAD ducklake; INSTALL postgres; LOAD postgres;');
  await conn.run(
    `ATTACH 'ducklake:${LAKE_CATALOG}' AS lake (DATA_PATH '${LAKE_DATA_PATH}', READ_ONLY)`
  );
  await conn.run('USE lake');
  await conn.run("SET search_path = 'lake.marts,lake.staging_spotify'");
  return conn;
})();

// BIGINT/HUGEINT come back as JS bigint, which pages can't do arithmetic or ===
// comparisons on alongside plain numbers; every value here fits in a double.
function toPlain(value: unknown): unknown {
  return typeof value === 'bigint' ? Number(value) : value;
}

export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const conn = await ready;
  const reader = await conn.runAndReadAll(sql);
  return reader
    .getRowObjectsJS()
    .map((row) =>
      Object.fromEntries(Object.entries(row).map(([key, value]) => [key, toPlain(value)]))
    ) as T[];
}
