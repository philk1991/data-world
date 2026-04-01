# dashboard

The Spotify data dashboard — a SvelteKit app that reads directly from the local DuckDB database and renders your listening history in a Spotify-styled interface.

## Stack

| Layer | Technology |
|---|---|
| Framework | [SvelteKit](https://kit.svelte.dev) with TypeScript |
| Styling | [Tailwind CSS v4](https://tailwindcss.com) + Spotify CSS custom properties |
| Database | [duckdb](https://www.npmjs.com/package/duckdb) npm package (v1.2.1) |
| Font | Inter via `@fontsource/inter` |

## Architecture

### How pages load data

SvelteKit's `+page.server.ts` files run on the **server only** (Node.js process). They import from `$lib/server/db` to query DuckDB, then return the data as props to the Svelte page component. There is no client-side API — the database is never exposed to the browser.

```
Browser request
    │
    ▼
+page.server.ts  ← runs in Node.js, has access to DuckDB
    │  returns { data }
    ▼
+page.svelte     ← receives data as props via `let { data } = $props()`
    │  renders HTML
    ▼
Browser
```

### Period tabs (client-side filtering)

All three time periods (short/medium/long term) are loaded in a single server query. The `PeriodTabs` component switches which period is active using Svelte 5's `$state` — no extra network requests on tab switch.

Each mart table has `rank_short_term`, `rank_medium_term`, and `rank_long_term` columns. The page filters and sorts the already-loaded array client-side based on whichever period is selected.

## Directory Structure

```
dashboard/
├── src/
│   ├── lib/
│   │   ├── server/
│   │   │   └── db.ts              # DuckDB singleton + query<T>() helper
│   │   ├── components/
│   │   │   ├── ArtistCard.svelte  # Artist image, rank badge, genres, popularity
│   │   │   ├── TrackRow.svelte    # Track row with rank, name, artists, duration
│   │   │   ├── PeriodTabs.svelte  # Short/medium/long term tab switcher
│   │   │   ├── RankBadge.svelte   # Gold (#1–3) / green (#4–10) rank number
│   │   │   ├── PopularityBar.svelte # Thin progress bar (0–100)
│   │   │   ├── HourlyBarChart.svelte # SVG bar chart of plays by hour
│   │   │   └── RecentTrackRow.svelte # Play event with relative timestamp
│   │   ├── types.ts               # TypeScript interfaces: TopArtist, TopTrack, RecentPlay
│   │   └── index.ts               # Re-exports
│   ├── routes/
│   │   ├── +layout.svelte         # Sidebar nav shell
│   │   ├── +page.svelte           # Overview: hero artist, hero track, nav tiles
│   │   ├── +page.server.ts        # Loads #1 artist, #1 track, last ingested timestamp
│   │   ├── artists/
│   │   │   ├── +page.svelte       # Artist grid with period tabs
│   │   │   └── +page.server.ts    # SELECT * FROM top_artists_by_period
│   │   ├── tracks/
│   │   │   ├── +page.svelte       # Track list with period tabs
│   │   │   └── +page.server.ts    # SELECT * FROM top_tracks_by_period
│   │   └── recent/
│   │       ├── +page.svelte       # Play feed + hourly chart
│   │       └── +page.server.ts    # SELECT * FROM stg_recently_played LIMIT 50
│   └── app.css                    # Tailwind base + Spotify colour tokens
├── .env                           # DUCKDB_PATH (absolute path to spotify.duckdb)
├── package.json
├── svelte.config.js
└── vite.config.ts
```

## Key Files

### `src/lib/server/db.ts`

Opens a single read-only DuckDB connection when the server starts. All queries go through `query<T>(sql)` which wraps the callback-based `db.all()` in a Promise.

```typescript
const db = new DuckDB.Database(DB_PATH, { access_mode: 'READ_ONLY' });

export function query<T>(sql: string): Promise<T[]> {
  return new Promise((resolve, reject) => {
    db.all(sql, (err, rows) => { ... });
  });
}
```

`db.all()` is called directly on the `Database` object — this uses DuckDB's built-in default connection. The database is opened in `READ_ONLY` mode so dbt can write to the same file while the dashboard is running.

### `src/lib/types.ts`

TypeScript interfaces that mirror the dbt mart columns:

- `TopArtist` — artist metadata + `rank_short_term / rank_medium_term / rank_long_term`
- `TopTrack` — track metadata + same three rank columns
- `RecentPlay` — individual play event with `played_at`, `played_hour`, `played_date`
- `Period` — `'short_term' | 'medium_term' | 'long_term'`

### `src/routes/+layout.svelte`

The outer shell: black sidebar with Spotify logo, nav links (Overview / Top Artists / Top Tracks / Recently Played), and a scrollable main area. The active link is highlighted with a green indicator bar.

## Design Tokens

Defined as CSS custom properties in `app.css`:

| Token | Value | Used for |
|---|---|---|
| `--bg-base` | `#121212` | Page background |
| `--bg-elevated` | `#181818` | Cards and panels |
| `--bg-highlight` | `#282828` | Hover states, tab pill background |
| `--accent-green` | `#1DB954` | Spotify green — active nav, CTAs, rank badges |
| `--text-primary` | `#FFFFFF` | Headings and primary text |
| `--text-muted` | `#B3B3B3` | Secondary text |
| `--text-subdued` | `#6A6A6A` | Tertiary text, explicit badge |

## Pages

### Overview (`/`)
Hero cards for your #1 short-term artist (with image) and #1 short-term track. Quick-nav tiles to the three main sections. Last ingested timestamp pulled from `MAX(ingested_at)` on the artists mart.

### Top Artists (`/artists`)
Grid of artist cards. Each card shows the artist photo, rank badge (gold for #1–3, green for #4–10), name, top two genres, popularity bar, follower count, and a link to Spotify. Artists not ranked in the selected period are shown dimmed at the bottom.

### Top Tracks (`/tracks`)
Dense ranked list. Each row shows rank, track name, artist(s), album, duration, explicit badge, popularity bar, and a Spotify link.

### Recently Played (`/recent`)
Chronological feed of your last 50 plays with relative timestamps ("2 hours ago"). Below the feed, an SVG bar chart shows your listening distribution by hour of day (0–23).

## Running Locally

```bash
# Install dependencies (once)
task dashboard:install

# Start dev server with hot reload
task dashboard:dev
# → http://localhost:5173

# Build for production
task dashboard:build
task dashboard:start
```

## Environment

The `.env` file sets the database path:

```
DUCKDB_PATH=/absolute/path/to/data-world/data/spotify.duckdb
```

This must be an **absolute path**. The path is read at server startup by `src/lib/server/db.ts`.
