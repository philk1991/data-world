import DuckDB from 'duckdb';
import { resolve } from 'path';

const DB_PATH = resolve(
  process.env.DUCKDB_PATH ?? '/Users/philkillarney/dev-env/data-world/data/spotify.duckdb'
);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const db = new DuckDB.Database(DB_PATH, { access_mode: 'READ_ONLY' } as any);

export function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  return new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (db as any).all(sql, (err: Error | null, rows: T[]) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
}
