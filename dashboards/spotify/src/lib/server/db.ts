import DuckDB from 'duckdb';
import { resolve } from 'path';

const DB_PATH = resolve(
  process.env.DUCKDB_PATH ?? '/Users/philkillarney/dev-env/data-world/data/spotify.duckdb'
);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = new DuckDB.Database(DB_PATH, { access_mode: 'READ_ONLY' } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const conn = (db as any).connect();

const ready: Promise<void> = new Promise((resolve, reject) => {
  conn.run("SET search_path = 'marts,staging_spotify,main'", (err: Error | null) => {
    if (err) reject(err);
    else resolve();
  });
});

export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  await ready;
  return new Promise((resolve, reject) => {
    conn.all(sql, (err: Error | null, rows: T[]) => {
      if (err) reject(err);
      else resolve(rows as T[]);
    });
  });
}
