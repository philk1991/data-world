# Dataset Exploration: `PlayByPlay.parquet` (NBA play-by-play)
**Generated:** 2026-11-04 13:50
**Tables analysed:** 1 (Kaggle file, not yet in the lake)  |  **Total rows:** 18,832,890

Source: `eoinamoore/historical-nba-data-and-player-box-scores`, version 536, `PlayByPlay.parquet`
(894 MB on disk, 378 row groups). Profiled with DuckDB `read_parquet`, joined to `lake.raw_nba`.

---

## Table: `PlayByPlay.parquet`
**Rows:** 18,832,890  |  **Columns:** 88  |  **Grain:** one row per game event; `(gameId, actionNumber)` is unique (18,832,890 distinct)

### Two feed formats in one file

The file stitches together two different NBA feeds. Staging has to unify them.

| Format | Seasons | Games | How to tell | What it has |
|---|---|---|---|---|
| **legacy** (stats.nba.com PlayByPlayV3) | 1996-97 → early 2019-20 | ~31,100 | `periodType` null; Title-case `actionType` (`Made Shot`, `Missed Shot`, `Rebound`, `Substitution`) | `shotValue`, `shotDistance`, `xLegacy`/`yLegacy`, `location` (h/v), `subType` shot description. Assists only in `description` text (`(Korver 1 AST)`). Subs are one row `SUB: <in> FOR <out>`, `personId` = player going **out**. `scoreHome`/`scoreAway` are 0 on non-scoring rows (must be forward-filled). |
| **live** (cdn.nba.com liveData) | mid 2019-20 → 2026-27 (to date) | ~8,270 | `periodType` = REGULAR/OVERTIME; lower-case `actionType` (`2pt`, `3pt`, `rebound`, `substitution`) | Everything legacy has, plus `x`/`y`, `area`/`areaDetail`, `qualifiers` (pointsinthepaint, fastbreak, 2ndchance…), `possession` team id, `assistPersonId`, `stealPersonId`, `blockPersonId`, `foulDrawnPersonId`, `officialId`, running score on every row. Subs are two rows (`subType` in/out) each with its own `personId`. |

### Column profile (grouped — 88 columns)

| Group | Columns | Null % | Notes |
|---|---|---|---|
| Keys | `gameId` (VARCHAR), `actionNumber` (INT) | 0 | `gameId` lacks leading zeros (`42500151`); raw games use BIGINT, so cast to join |
| Time | `period`, `clock` (ISO `PT11M56.00S`), `gameDateTimeEst` (VARCHAR) | 0 / 0 / 1.1 | `period` 1–10 (OT up to 6th) |
| Event | `actionType` (36 distinct), `subType` (250), `descriptor` (107), `description` | 0 / 0.4 / 92.6 / 0.2 | `actionType` mixes formats and has ~5K rows with trailing spaces (`'Rebound   '`); needs `lower(trim())` + mapping |
| Actor | `personId`, `playerName`, `playerNameI`, `playerFullName`, `teamId`, `teamTricode` | 0.04 / 2.2 / 2.2 / 9.5 / 1.5 / 1.5 | `personId` '0' for period/game events; team IDs (`1610612…`) for team rebounds/turnovers |
| Score | `scoreHome`, `scoreAway` | 15.8 | Legacy: 0 on non-scoring rows. Final score matches `raw_nba_games` in 39,169 of 39,208 games (99.9%) |
| Shot | `isFieldGoal`, `shotResult`, `shotDistance`, `shotValue`, `xLegacy`/`yLegacy` | 0.9 / 16.7 / 18.9 / 27.6 / 18.9 | `shotValue` legacy only; live uses `actionType` 2pt/3pt |
| Shot (live) | `x`, `y`, `area`, `areaDetail`, `side`, `qualifiers` | 89–91 | Live format only |
| Linked players (live) | `assistPersonId`, `stealPersonId`, `blockPersonId`, `foulDrawnPersonId`, `jumpBall*PersonId` | 97.5–99.9 | Sparse by nature (only on the relevant events) |
| Running totals (live) | `pointsTotal`, `reboundTotal`, `assistTotal`, `turnoverTotal`, `foul*Total`… | 21.8–99.99 | Player's running count in the game |
| Live metadata | `possession`, `orderNumber`, `timeActual`, `edited`, `personIdsFilter`, `officialId`, `videoAvailable` | 72.4–97.3 | |
| Empty / junk | `gameType`, `jumpBallRecoveredPersonId`, `jumpBallRecoverdPersonId`, `gameType_g`, `gameDateTimeEst_g`, `playerteamId`, `opponentteamId`, `shortFormattedClock`, `jerseyNumber`, `value` | 99.2–100 | Drop in staging |

### Top values — `actionType` (combined formats)

| Value | Count | | Value | Count |
|---|---|---|---|---|
| Rebound | 3,060,334 | | 2pt | 979,205 |
| Missed Shot | 2,698,830 | | rebound | 968,912 |
| Made Shot | 2,221,385 | | Turnover | 880,278 |
| Free Throw | 1,467,744 | | 3pt | 659,070 |
| Foul | 1,328,834 | | freethrow | 418,953 |
| Substitution | 1,205,329 | | Timeout | 393,032 |
| substitution | 1,031,210 | | foul | 377,079 |

Plus period, turnover, steal (live only — legacy logs steals inside the Turnover row), block (live only), timeout, Violation, Jump Ball, stoppage, Instant Replay, game, Ejection, heave, memo.

> Range: `1996-11-01 19:00` → `2026-04-19 21:00` by `gameDateTimeEst`; game IDs run into 2026-27 (174 games so far)

---

## Coverage

- **39,338 games, average 479 events (13–778).**
- **Regular season and playoffs: 100% from 1996-97 onward**, apart from 2 regular-season games, in 2006-07 and 2007-08.
- **No play-by-play before 1996-97.**
- **Preseason:** none for 2003-04 to 2012-13, then full from 2013-14.
- **Play-in, NBA Cup and All-Star games:** covered where they exist.
- **130 games aren't in `raw_nba_games`:** 85 preseason, 23 regular season and 22 All-Star.

Shot coordinates (`xLegacy`/`yLegacy`, where 0/0 means missing):

| Seasons | FGA without coordinates |
|---|---|
| 1996-97 | 35% |
| 1997-98 → 2009-10 | 22–25% |
| 2010-11 → today | 0% |

Assist attribution:

| Format | How it's recorded | Share of made FGs |
|---|---|---|
| Live | `assistPersonId` | 59–64% assisted |
| Legacy | Assister's **surname in `description`** only, which needs parsing and resolving to a player on the same team in that game | ~59% |

---

## Missing Data

Most nulls are structural: a column only applies to some event types, or only to one feed format. The issues that matter:

| Issue | Rows affected | Impact |
|---|---|---|
| Legacy scores 0 on non-scoring rows | ~72% of rows | Forward-fill `scoreHome`/`scoreAway` per game before any score-state metric |
| No `possession` in legacy | 72.4% | Possessions must be derived (made FG/FT end, defensive rebound, turnover) |
| No shot coordinates 1996–2009 | ~25% of those FGA | Shot charts reliable from 2010-11; use `shotDistance` (0% null) before that |
| Team IDs in `personId` | 5.1% of events | Team rebounds/turnovers; exclude from player joins |
| `personId` not in `raw_nba_players` | 755 players, 18,187 events (0.1%) | Minor; left join |

---

## Suggested dbt Models

### Staging
- `stg_nba_play_by_play` (view over `raw_nba.raw_nba_play_by_play`) — unify the two formats:
  - zero-padded `game_id`;
  - `season_start_year` from the game ID;
  - `action_type` normalised to one vocabulary (2pt/3pt/freethrow/rebound/turnover/steal/block/foul/substitution/…);
  - `seconds_remaining` parsed from the ISO clock;
  - forward-filled home and away scores;
  - `shot_value`, `is_made`, `shot_distance`, `shot_x`, `shot_y` (legacy coordinates);
  - `team_id`;
  - player IDs only where `personId` is a player.

  It's large (18.8M rows), so consider materialising it as a table, or doing the forward-fill in an intermediate model.

### Potential marts
1. **`nba_player_shot_zones`** — grain: player × season × game type × shot zone (distance band; area where live). Question: where does a player shoot from, and how efficiently, compared with the league? Covers 1996-97 onward, with coordinate-based zones from 2010-11.
2. **`nba_player_clutch_stats`** — grain: player × season × game type. Clutch means the last 5 minutes of the 4th quarter or OT with the score within 5 points. Columns: points, FG/FGA, TS%, turnovers. Question: who performs in close games? Needs the forward-filled score; covers all seasons.
3. **`nba_lineup_stints`** → **`nba_player_on_off`** — grain: game × stint (the five players on court per team between substitutions), then player × season with on-court and off-court net rating. Question: which players and lineups win their minutes? This is the most valuable model and the hardest. Who is on court at the start of a period has to be inferred, because the feed only logs substitutions. The legacy format also gives only the incoming player's name.

Also cheap: `nba_game_flow` (score margin over game time, biggest lead, lead changes, comebacks), and assist networks (passer → scorer pairs, easy for 2019-20 onward from `assistPersonId`).

---

## Relation to Existing dbt

### Already modelled in this domain
Player and team box-score models (`stg_nba_player_statistics`, `stg_nba_player_statistics_extended`, `stg_nba_team_statistics*`, `stg_nba_games`, `stg_nba_players`, `stg_nba_team_histories`) and the NBA marts, including:
- `nba_player_game_stats`
- `nba_player_season_stats`
- `nba_player_advanced_career`
- `nba_players_dim`
- `nba_team_dim`
- `nba_game_results`
- `nba_team_season_summary`
- `nba_team_head_to_head`

### Potential joins and enrichments
- `game_id` (pbp `gameId::BIGINT`) → `stg_nba_games` / `nba_game_results` (game type, date, season, home/away teams); 99.7% of pbp games match.
- `(game_id, person_id)` → `nba_player_game_stats`: reconcile pbp-derived points/FGA against the box score as a data test, and add clutch/zone columns per game.
- `person_id` → `nba_players_dim` (names, position, height for shot-profile-by-position).
- `team_id` → `nba_team_dim`.
