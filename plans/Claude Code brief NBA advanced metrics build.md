# Claude Code brief: NBA advanced metrics build

Nov 5, 2026 · @Phil

## 1. Mission and operating rules

You are Claude Code. Extend this project so it can explain historical and current NBA performance for players and teams, using the metrics in this brief.

This brief defines **what to calculate**. It deliberately does not name output tables, output files or pipelines. The project already contains datasets, so you decide what to reuse, what to modify, and what to create.

**Primary source:** the eoinamoore Kaggle dataset, Historical NBA Data and Player Box Scores. Other Kaggle data already in the project can fill gaps.

**Operating rules:**

1. Audit before you build. Complete section 2 before changing anything.
2. Follow the project's existing language, storage, naming, orchestration and test conventions. Don't introduce a new framework unless the audit shows a real need.
3. Prefer extending a suitable dataset to creating a near-duplicate.
4. Create a new dataset when the grain, refresh pattern or dependencies differ enough that extending one would make it harder to use or validate.
5. Keep each metric's definition in one place, so one formula never exists in two versions.
6. Don't overwrite or delete existing data, or change existing columns consumed elsewhere, until you have checked downstream use. Add columns or version definitions where needed.
7. Record every assumption and deviation in the decision log.
8. Show a metric as null when its inputs don't exist. Never convert missing data to zero.

**Stop and ask the user only if:** a change is destructive, breaks an existing consumer, conflicts with an existing definition in a way the audit can't settle, or a source check fails and materially changes scope. Otherwise, make the call and log it.

## 2. Discovery: audit first

Inspect the repository and data, then produce a decision log in the project's documentation location. Do this before any build work.

**Audit:**

1. List existing datasets, with grain, primary key, date range, refresh method, row counts and downstream consumers.
2. List every metric this brief defines that already exists. Compare its formula, inputs and scope with this brief.
3. Inspect the raw Kaggle files in the project and record real column names, types, null rates and date coverage.
4. Run the source checks in section 3, including the play-by-play gate.
5. Find any season-level data in the project that can support pre-1983-84 work or validation.

**Then record one row per metric:**

| Metric | Status | Action | Target | Required grains | Inputs | Coverage | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example: `net_rating` | Exists, wrong possession definition | Modify | Existing dataset you identify | Team-game, team-season | Team-game counts | 1973-74 on | Reason for the choice |

Use `reuse`, `modify`, `create` or `blocked` as the action. The Target column names your own choice of dataset. A metric is `blocked` when its required inputs fail a source check; give the reason.

**Decide using these tests:**

- **Reuse** when the existing metric matches and passes the section 10 tests.
- **Modify** when the dataset has the right grain and refresh pattern, but a metric is missing or wrong.
- **Create** when no dataset can hold the metric cleanly at the required grain.
- **Add a version** when an existing definition differs, but consumers depend on it.

Every metric must be queryable at the grains listed in its section. Those are access requirements, not a table design.

## 3. Kaggle inputs

The file names and column names below are expected, not confirmed. They come from third-party descriptions and memory. Trust the real schema in the project, and map each logical field to it.

| Expected file | Use | Grain |
| --- | --- | --- |
| `TeamStatistics.csv` | Team and opponent box counts, scores, home flag, game type | Team-game |
| `PlayerStatistics.csv` | Player box counts, minutes, plus-minus | Player-game |
| `TeamStatisticsExtended.csv` | Cross-checks and any extra fields, from about 1996 | Team-game |
| `PlayerStatisticsExtended.csv` | Cross-checks and any extra fields; over 100 columns, from about 1996 | Player-game |
| `PlaybyPlay.parquet` | Events for section 8, from about 1996 | Event |
| `Games.csv` | Game IDs, dates, teams, game type | Game |
| `Players.csv` | Player ID, birthdate, listed position | Player |
| `TeamHistories.csv` | Franchise and team-name mapping | Team-era |
| `LeagueSchedule*.csv` | Current schedule and game type | Game |

**Logical fields to map:**

- **Identity:** `game_id`, `game_date`, `season`, `game_type`, `team_id`, `opp_team_id`, `person_id`, `home`, `win`.
- **Counts:** `MP`, `PTS`, `FG`, `FGA`, `3P`, `3PA`, `FT`, `FTA`, `ORB`, `DRB`, `TRB`, `AST`, `STL`, `BLK`, `TOV`, `PF`, `PLUS_MINUS`.
- **Opponent fields:** self-join team-game rows on `game_id` and the opposing team, then prefix with `Opp`.
- **Player context:** team and opponent totals for the same game or stint.
- **Team minutes:** use a real field if one exists. Otherwise take the sum of player minutes, and confirm it equals 240 + 25 × overtime periods.

Expected column names to look for include `personId`, `gameId`, `gameDate`, `gameType`, `numMinutes`, `points`, `assists`, `blocks`, `steals`, `fieldGoalsMade`, `fieldGoalsAttempted`, `threePointersMade`, `threePointersAttempted`, `freeThrowsMade`, `freeThrowsAttempted`, `reboundsOffensive`, `reboundsDefensive`, `reboundsTotal`, `foulsPersonal`, `turnovers`, `plusMinusPoints`, `teamId`, `teamScore` and `opponentScore`.

**Run these source checks and record the results:**

1. **Season mapping:** derive the NBA season from the game ID where possible, and validate it against dates. Calendar rules break for 2019-20 and 2020-21.
2. **Game types:** confirm how preseason, regular season, play-in, playoffs, NBA Cup and All-Star games are labelled.
3. **Coverage:** calculate null and zero rates for every count by season and game type. Treat a zero as suspect where the stat wasn't recorded.
4. **Early history:** compare summed logs with any season totals available. Basketball-Reference's game logs are incomplete before 1983-84, so this feed may be too. Prefer season totals when logs fall short.
5. **Extended files:** compare a sample of supplied advanced fields with your formulas. Keep them under a separate definition until they match.
6. **Tracking and hustle:** search the Extended files for those fields. Tracking is out of scope unless the user adds it later.
7. **Freshness:** record the latest game date. The Kaggle listing recently mentioned upload trouble.

**Minimum data requirements:**

| Stat group | Reliable from | If unavailable |
| --- | --- | --- |
| PTS, FG, FGA, FT, FTA | 1946-47 in season totals | Null |
| Player MP | 1951-52 | Null for per-minute metrics |
| AST-based team context | 1964-65 for AST% | Null |
| ORB, DRB, STL, BLK | 1973-74 | Use only the era rules in section 7 |
| Player TOV | 1977-78 | Use the estimator in section 7 for 1973-74 to 1976-77 |
| 3P and 3PA | 1979-80 | Treat as 0 only because the shot didn't exist |
| Complete game-level box stats | 1983-84 | Use season totals |
| Play-by-play | 1996-97 | Section 8 metrics are null |

## 4. Global calculation rules

Apply these to every metric.

**Required grains:** make metrics available by game, team-season, player-team-season and player-season, and by season type. Current-form metrics also need an as-of date.

**Aggregation:** sum raw counts across the period, then calculate the ratio. Never average game-level percentages or rates.

**Game types:**

- Calculate regular season, play-in and playoffs separately.
- The NBA Cup final doesn't count on either team's record. Keep it out of regular-season totals and baselines.
- Exclude preseason and All-Star games.

**Possessions:** keep box-estimated and play-by-play possessions in separate fields. Never mix them in one series.

```python
# Team possessions, BBRef definition
off = FGA + 0.4*FTA - 1.07*(ORB/(ORB + Opp_DRB))*(FGA - FG) + TOV
def_ = Opp_FGA + 0.4*Opp_FTA - 1.07*(Opp_ORB/(Opp_ORB + DRB))*(Opp_FGA - Opp_FG) + Opp_TOV
Poss = 0.5 * (off + def_)

# Team pace
Pace = 48 * (Poss + Opp_Poss) / (2 * (Tm_MP / 5))
```

Calculate season possessions from season totals of the raw counts, not by summing game estimates, unless the audit shows the project standard is different. Log the choice.

**League baselines:** build them by season and season type, from the sum of all team numerators and denominators. Include:

```text
Lg_G, Lg_PTS, Lg_FG, Lg_FGA, Lg_3P, Lg_3PA, Lg_FT, Lg_FTA, Lg_ORB, Lg_DRB, Lg_TRB,
Lg_AST, Lg_STL, Lg_BLK, Lg_TOV, Lg_PF, Lg_Poss, Lg_MP, Lg_Pace, Lg_PPG, Lg_PPP,
Lg_ORtg, Lg_TS, Lg_eFG, Lg_3PAr, Lg_FTr, Lg_TOV_pct, Lg_ORB_pct
```

For as-of metrics, baselines must use only games before that date.

**Traded players:** calculate team-context rates for each player-team stint, then combine by summing the numerators and denominators or by possession weighting. Keep a total row flagged as multi-team.

**Shortened seasons:** don't compare raw totals directly for 1998-99, 2011-12, 2019-20 or 2020-21. VORP uses team games / 82. Use rates or games-played scaling for other totals, and flag scaled values.

**Heave rule:** from 2025-26, qualifying end-of-quarter heaves count as team attempts, not individual attempts. They apply in the last 3 seconds of Q1 to Q3, from 36 feet or more, on plays starting in the backcourt. Player totals may therefore be lower than team totals. Use team totals for team metrics, and allow that difference in tests.

**Metadata on every metric:** record formula version, season coverage flag, sample size, and whether the value is exact, estimated or era-adjusted.

**Qualifying filters:** store sample sizes, and apply filters at query time. Defaults for ranking are 500 minutes for player-seasons, and at least the league median attempts for shooting leaderboards. Scale these for shortened seasons.

## 5. Team metrics

Required grains: team-game, team-season, and rolling as-of date. Calculate all metrics separately for offence and defence where relevant.

```python
ORtg = 100 * PTS / Poss                 # 1973-74 on
DRtg = 100 * Opp_PTS / Poss             # 1973-74 on
NetRtg = ORtg - DRtg                    # 1973-74 on
MOV = (PTS - Opp_PTS) / G               # all seasons

# Four Factors, offence; 1973-74 on where ORB and TOV are needed
eFG = (FG + 0.5*3P) / FGA
TOV_pct = TOV / (FGA + 0.44*FTA + TOV)
ORB_pct = ORB / (ORB + Opp_DRB)
FT_rate = FT / FGA

# Four Factors, defence
Opp_eFG = (Opp_FG + 0.5*Opp_3P) / Opp_FGA
Opp_TOV_pct = Opp_TOV / (Opp_FGA + 0.44*Opp_FTA + Opp_TOV)
DRB_pct = DRB / (Opp_ORB + DRB)
Opp_FT_rate = Opp_FT / Opp_FGA

# Style
FG3A_rate = 3PA / FGA                   # 1979-80 on
AST_rate = AST / FG
TS = PTS / (2 * (FGA + 0.44*FTA))

# Record quality
Wins_pyth = G * PTS**14 / (PTS**14 + Opp_PTS**14)
Luck_wins = Wins - Wins_pyth
```

Use the published Basketball-Reference exponent of 14 for Pythagorean wins.

**Four Factors decomposition:** treat the 40/25/20/15 weights as a guide only. Within each era, regress team-season Net Rating on the eight factors, expressed as differences from league average. Store the coefficients and each team's points gained by factor. Use eras of no more than 10 seasons, and report the fit.

**SRS:** solve to convergence for each season and season type, for all seasons:

```python
# Start: SRS = MOV. Repeat until max change < 1e-6:
SRS[t] = MOV[t] + mean(SRS[opp] for each game of t)
SRS = SRS - weighted_mean(SRS)          # keeps the league centred on 0
SOS = SRS - MOV
```

**Adjusted Net Rating:** use least squares, with one row per game and possession weights:

```python
# 1973-74 on. Exclude a home term for neutral-site games.
game_net_per_100 = rating[home] - rating[away] + home_court
# Regularise lightly, and centre ratings on 0 by possession weights.
```

**Elo:** process all games in chronological order, in one pass.

```python
HOME = 100                               # Elo points; ~3.5 real points. 0 at neutral sites.
expected_home = 1 / (1 + 10**(-(elo_home + HOME - elo_away) / 400))
K = 20 * (abs(MOV) + 3)**0.8 / (7.5 + 0.006 * elo_diff_winner)
# elo_diff_winner = winner Elo minus loser Elo, including HOME for the home team.
delta = K * (actual_home - expected_home)
elo_home += delta
elo_away -= delta
```

Start at 1500 and keep the franchise's rating through relocation or rename. Between seasons, use `elo = c*elo + (1-c)*1505`. Start with `c = 0.75`, then tune `c` on log loss with a walk-forward test. That starting value is an unverified placeholder, so log the tuned result.

Store pre-game and post-game Elo for every game. Only pre-game values may feed predictions.

**Team current form:** publish last-10 and last-20 Net Rating, average opponent Elo, and current Elo. Compare with league-to-date baselines, not last season's. Pace often slows and efficiency usually rises during a season.

## 6. Player metrics

Required grains: player-game where inputs support it, player-team-season, player-season, and rolling as-of date. Team and opponent terms use the same game or stint.

```python
TSA = FGA + 0.44*FTA
TS = PTS / (2*TSA)
eFG = (FG + 0.5*3P) / FGA
FG3A_rate = 3PA / FGA                    # 1979-80 on
FT_rate = FT / FGA
TS_points_added = PTS - 2*Lg_TS*TSA      # derived from BBRef's description

USG = 100 * (FGA + 0.44*FTA + TOV) * (Tm_MP/5) / (MP * (Tm_FGA + 0.44*Tm_FTA + Tm_TOV))  # 1977-78 on
AST_pct = 100 * AST / (((MP / (Tm_MP/5)) * Tm_FG) - FG)                                  # 1964-65 on
TOV_pct = 100 * TOV / (FGA + 0.44*FTA + TOV)                                             # 1977-78 on
ORB_pct = 100 * ORB * (Tm_MP/5) / (MP * (Tm_ORB + Opp_DRB))                              # player ORB: 1973-74 on
DRB_pct = 100 * DRB * (Tm_MP/5) / (MP * (Tm_DRB + Opp_ORB))                              # player DRB: 1973-74 on
TRB_pct = 100 * TRB * (Tm_MP/5) / (MP * (Tm_TRB + Opp_TRB))
STL_pct = 100 * STL * (Tm_MP/5) / (MP * Opp_Poss)                                        # 1973-74 on
BLK_pct = 100 * BLK * (Tm_MP/5) / (MP * (Opp_FGA - Opp_3PA))                             # 1973-74 on

player_poss = Tm_Poss * MP / (Tm_MP/5)
stat_per_100 = 100 * stat / player_poss

GameScore = PTS + 0.4*FG - 0.7*FGA - 0.4*(FTA-FT) + 0.7*ORB + 0.3*DRB + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TOV
```

Use `Tm_MP` as total team player-minutes, about 240 per regulation game.

**Individual Offensive Rating:** Dean Oliver's method, from 1977-78.

```python
qAST = (MP/(Tm_MP/5)) * (1.14*((Tm_AST - AST)/Tm_FG)) \
     + (((Tm_AST/Tm_MP)*MP*5 - AST) / ((Tm_FG/Tm_MP)*MP*5 - FG)) * (1 - MP/(Tm_MP/5))
FG_Part = FG * (1 - 0.5*((PTS - FT)/(2*FGA))*qAST)
AST_Part = 0.5 * (((Tm_PTS - Tm_FT) - (PTS - FT)) / (2*(Tm_FGA - FGA))) * AST
FT_Part = (1 - (1 - FT/FTA)**2) * 0.4 * FTA

Tm_Scoring_Poss = Tm_FG + (1 - (1 - Tm_FT/Tm_FTA)**2) * Tm_FTA * 0.4
Tm_ORB_pct = Tm_ORB / (Tm_ORB + (Opp_TRB - Opp_ORB))
Tm_Play_pct = Tm_Scoring_Poss / (Tm_FGA + Tm_FTA*0.4 + Tm_TOV)
Tm_ORB_Weight = ((1 - Tm_ORB_pct)*Tm_Play_pct) / ((1 - Tm_ORB_pct)*Tm_Play_pct + Tm_ORB_pct*(1 - Tm_Play_pct))
ORB_Part = ORB * Tm_ORB_Weight * Tm_Play_pct

ScPoss = (FG_Part + AST_Part + FT_Part) * (1 - (Tm_ORB/Tm_Scoring_Poss)*Tm_ORB_Weight*Tm_Play_pct) + ORB_Part
FGxPoss = (FGA - FG) * (1 - 1.07*Tm_ORB_pct)
FTxPoss = ((1 - FT/FTA)**2) * 0.4 * FTA
TotPoss = ScPoss + FGxPoss + FTxPoss + TOV

PProd_FG = 2 * (FG + 0.5*3P) * (1 - 0.5*((PTS - FT)/(2*FGA))*qAST)
PProd_AST = 2 * ((Tm_FG - FG + 0.5*(Tm_3P - 3P)) / (Tm_FG - FG)) \
          * 0.5 * (((Tm_PTS - Tm_FT) - (PTS - FT)) / (2*(Tm_FGA - FGA))) * AST
PProd_ORB = ORB * Tm_ORB_Weight * Tm_Play_pct * (Tm_PTS / Tm_Scoring_Poss)
PProd = (PProd_FG + PProd_AST + FT) * (1 - (Tm_ORB/Tm_Scoring_Poss)*Tm_ORB_Weight*Tm_Play_pct) + PProd_ORB

ORtg = 100 * PProd / TotPoss
```

Guard all divisions. When `FTA` or `FGA` is zero, the related term is zero. Calculate at season or stint level, because single-game values are unstable.

**Individual Defensive Rating:** from 1973-74, using estimated turnovers before 1977-78 where needed.

```python
DOR_pct = Opp_ORB / (Opp_ORB + Tm_DRB)
DFG_pct = Opp_FG / Opp_FGA
FMwt = (DFG_pct*(1 - DOR_pct)) / (DFG_pct*(1 - DOR_pct) + (1 - DFG_pct)*DOR_pct)

Stops1 = STL + BLK*FMwt*(1 - 1.07*DOR_pct) + DRB*(1 - FMwt)
Stops2 = (((Opp_FGA - Opp_FG - Tm_BLK)/Tm_MP)*FMwt*(1 - 1.07*DOR_pct) + ((Opp_TOV - Tm_STL)/Tm_MP))*MP \
       + (PF/Tm_PF)*0.4*Opp_FTA*(1 - Opp_FT/Opp_FTA)**2
Stops = Stops1 + Stops2
Stop_pct = (Stops*Opp_MP) / (Tm_Poss*MP)

Tm_DRtg = 100 * Opp_PTS / Tm_Poss
D_Pts_per_ScPoss = Opp_PTS / (Opp_FG + (1 - (1 - Opp_FT/Opp_FTA)**2)*Opp_FTA*0.4)
DRtg = Tm_DRtg + 0.2*(100*D_Pts_per_ScPoss*(1 - Stop_pct) - Tm_DRtg)
```

Label individual DRtg as team-dependent. Don't use it as a stand-alone defensive grade.

## 7. All-in-one metrics

Build BPM, VORP and Win Shares first. Build PER last, for familiarity. Required grain is player-team-season and player-season. Add game-level BPM from 1984-85.

### Turnover estimate, 1973-74 to 1976-77

BPM and Win Shares use different published estimators. Keep each with its own metric, and flag values as estimated.

```python
# BPM, per-100 inputs. Year = last two digits of the season-ending year.
TOV_per100_est = 4.1119 - 0.0191*Age - 0.0519*Year - 0.0494*PTS + 0.0442*TRB + 0.0957*FGA \
               + 0.2056*FTA + 0.2216*AST + 0.1972*PF

# Win Shares, season totals
est = max(0, -0.0005075172*MP*Age - 0.0873982755*FG + 0.0925506598*FGA + 0.1566322510*FTA
             + 0.0449241773*TRB + 0.2321637159*AST + 0.2040169400*PF)
player_TOV = Tm_TOV * 0.985 * est / sum(team_est)
```

### BPM 2.0 and OBPM

Coverage: season-level 1973-74 on; game-level 1984-85 on.

**Step 1. Position and role.** Each `pct_x` is the player's share of team production while on court:

```python
pct_x = (x / MP) * (Tm_MP/5) / Tm_x

position = 2.130 + 8.668*pct_TRB - 2.486*pct_STL + 0.992*pct_PF - 3.536*pct_AST + 1.667*pct_BLK

team_pts_per_tsa = Tm_PTS / (Tm_FGA + 0.44*Tm_FTA)
threshold_pts = max(0, PTS - (team_pts_per_tsa - 0.33) * TSA)
# pct_threshold_pts = on-court share of the team's summed threshold_pts
role = 6.00 - 6.642*pct_AST - 8.544*pct_threshold_pts
```

The threshold formula above is this brief's reading of the method. Confirm it through calibration.

**Step 2. Adjust and constrain.**

```python
position = (position*MP + listed_position*50) / (MP + 50)   # listed_position defaults to 3.0
role = (role*MP + 4.0*50) / (MP + 50)
# Clamp each to [1, 5]. Shift the team by a constant so the minute-weighted mean = 3.
# Repeat clamp and shift until both hold.
```

**Step 3. Interpolate.** Use per-100 stats. Position columns use `p`; FGA and FTA use role `r`:

```python
coef(p) = coef_1 + (p - 1)/4 * (coef_5 - coef_1)
```

| Variable | BPM at 1 | BPM at 5 | OBPM at 1 | OBPM at 5 |
| --- | --- | --- | --- | --- |
| Adjusted points | 0.860 | 0.860 | 0.605 | 0.605 |
| 3PM | 0.389 | 0.389 | 0.477 | 0.477 |
| AST | 0.580 | 1.034 | 0.476 | 0.476 |
| TOV | −0.964 | −0.964 | −0.579 | −0.882 |
| ORB | 0.613 | 0.181 | 0.606 | 0.422 |
| DRB | 0.116 | 0.181 | −0.112 | 0.103 |
| STL | 1.369 | 1.008 | 0.177 | 0.294 |
| BLK | 1.327 | 0.703 | 0.725 | 0.097 |
| PF | −0.367 | −0.367 | −0.439 | −0.439 |
| FGA, by role | −0.560 | −0.780 | −0.330 | −0.472 |
| FTA, by role | −0.246 | −0.343 | −0.145 | −0.208 |

The published tables leave several position-5 cells blank, which are treated as constant here. The OBPM AST value at position 5 is the least certain, because the source says assists are worth less for bigs. Confirm through calibration.

**Step 4. Raw value and constants.**

```python
bpm_pos = -0.818*(3 - p)/2 if p < 3 else 0
bpm_role = 1.387*(r - 3)
obpm_pos = -1.698*(3 - p)/2 if p < 3 else 0
obpm_role = 0.430*(r - 3)
raw = sum(coef*stat_per_100) + pos_constant + role_constant
```

**Step 5. Team adjustment.**

```python
team_rating = schedule_adjusted_net_rating + 0.175*average_lead
c = (team_rating - sum(w*raw)) / sum(w)      # w = player's share of team possessions; sum(w) is about 5
BPM = raw + c
DBPM = BPM - OBPM
```

The source text states this lead adjustment with a minus sign, but its example (+3.0 with lead 1.4 gives +3.24) and game formulas require a plus. Use the plus.

Use play-by-play for `average_lead` where available. For earlier seasons, fit it from Net Rating on play-by-play seasons, apply that fit, and flag the value as estimated. Calculate OBPM's own team adjustment from schedule-adjusted offensive rating.

**Known gap: team shooting context.** The source shifts each player's points by a team-level constant based on team points per adjusted shot attempt against a regression baseline, but doesn't publish the baseline or the shift. Don't invent it silently. Implement it as one configurable team-level adjustment, then calibrate against published Basketball-Reference BPM if season-level advanced data exists in the project. Report the error by season, and mark the metric `bpm_2_0_calibrated`. Without calibration data, set the adjustment to zero, mark it `bpm_2_0_approx`, and tell the user.

**Game-level BPM, 1984-85 on.**

```python
ReMPG = minutes / (games + 4)
est_BPM = -4.75 + 0.175*ReMPG
minute_weight = max(0, (450 - minutes)/3)
regressed_BPM = (season_BPM*minutes + est_BPM*minute_weight) / (minutes + minute_weight)

base = sum(regressed_BPM * game_possession_share)
winner_rating = base + margin/2 + 0.175*average_lead
loser_rating = base - margin/2 - 0.175*average_lead
```

Then apply the same team adjustment within the game.

### VORP

```python
VORP = (BPM + 2.0) * pct_team_possessions_played * team_games/82
WAR = VORP * 2.7
```

### Win Shares

Calculate by era, and store an `era_method` value.

**Modern: offence from 1977-78, defence from 1973-74.** Use `PProd`, `TotPoss` and `DRtg` from section 6.

```python
marginal_offense = PProd - 0.92*Lg_PPP*TotPoss
marginal_ppw = 0.32*Lg_PPG*(Tm_Pace/Lg_Pace)
OWS = marginal_offense / marginal_ppw

marginal_defense = (MP/Tm_MP)*Tm_Def_Poss*(1.08*Lg_PPP - DRtg/100)
DWS = marginal_defense / marginal_ppw
WS = OWS + DWS
WS_48 = 48*WS/MP
```

The source's example of 1973-74 to 1976-77 offence uses the turnover estimate with the modern formula.

**Pre-1973-74 offence, 1946-47 to 1972-73.**

```python
ratio = Tm_AST/Tm_FG
mod_pts = 2.0*FG*(1 - ratio) + 1.5*FG*ratio + 1.0*FT + 0.5*AST
mod_sa = 1.00*FG*(1 - ratio) + 0.50*FG*ratio + 1.00*(FGA - FG) + 0.44*FTA + 0.50*AST
Lg_PPSA = Lg_PTS / (Lg_FGA + 0.44*Lg_FTA)
marginal_offense = mod_pts - 0.92*Lg_PPSA*mod_sa
marginal_ppw = 0.16*(Tm_PPG + Opp_PPG)
OWS = marginal_offense / marginal_ppw
```

**Pre-1973-74 defence.**

```python
team_marginal_defense = 1.08*Lg_PPSA*(Tm_FGA + 0.44*Tm_FTA) - Opp_PTS

# 1951-52 to 1972-73
share = 0.25*(MP/Tm_MP) + 0.5*(TRB/Tm_TRB) + 0.25*(AST/Tm_AST)
# 1950-51
share = 0.25*(FGA/Tm_FGA) + 0.5*(TRB/Tm_TRB) + 0.25*(AST/Tm_AST)
# 1946-47 to 1949-50
share = 0.25*(FGA/Tm_FGA) + 0.5*(PF/Tm_PF) + 0.25*(AST/Tm_AST)

DWS = team_marginal_defense*share / (0.16*(Tm_PPG + Opp_PPG))
```

Before 1967-68, multiply team total rebounds by 0.875. Before 1964-65, estimate team minutes as `5*48*team_games + 125`. These pre-1973-74 calculations require season totals, so skip any season the data can't support.

### PER

Coverage: 1951-52 on. Apply the source's fallbacks below for missing stats, and flag those seasons.

```python
factor = (2/3) - (0.5*(Lg_AST/Lg_FG)) / (2*(Lg_FG/Lg_FT))
VOP = Lg_PTS / (Lg_FGA - Lg_ORB + Lg_TOV + 0.44*Lg_FTA)
DRBP = (Lg_TRB - Lg_ORB) / Lg_TRB

uPER = (1/MP) * (
    3P + (2/3)*AST + (2 - factor*(Tm_AST/Tm_FG))*FG
    + FT*0.5*(1 + (1 - Tm_AST/Tm_FG) + (2/3)*(Tm_AST/Tm_FG))
    - VOP*TOV - VOP*DRBP*(FGA - FG) - VOP*0.44*(0.44 + 0.56*DRBP)*(FTA - FT)
    + VOP*(1 - DRBP)*(TRB - ORB) + VOP*DRBP*ORB + VOP*STL + VOP*DRBP*BLK
    - PF*((Lg_FT/Lg_PF) - 0.44*(Lg_FTA/Lg_PF)*VOP))

pace_adj = Lg_Pace/Tm_Pace              # before 1973-74: 2*Lg_PPG/(Tm_PPG + Opp_PPG)
aPER = pace_adj*uPER
PER = aPER*15/minute_weighted_mean(aPER)
```

Fallbacks: `3P = 0` before 1979-80; `TOV = 0` before 1977-78; `STL = BLK = 0` before 1973-74; and where needed `VOP = 1`, `DRBP = 0.7`, and `ORB = 0.3*TRB`.

## 8. Play-by-play metrics

These metrics depend on a gate. Run it first, and mark every metric here `blocked` if it fails.

**Gate.** `PlaybyPlay.parquet`, or equivalent project data, must provide all of these for a sampled set of games in every era from 1996-97:

- Game ID, period, game clock, event order, event type and team.
- Player IDs on shots, fouls, turnovers, rebounds and free throws.
- Substitutions with player in and player out, or existing on-court lineups.
- Score after each scoring event.

**Reconcile.** Rebuild points, field goals and rebounds from events for a sample of games, and compare with the box scores. Investigate any season with a material mismatch. If stats.nba.com-style sources are in use, expect events out of order, and repair the sequence before counting possessions.

**Possessions.** Count a possession end on a made field goal, a defensive rebound, a turnover, or a final made free throw that gives up the ball, and at period end. Offensive rebounds continue a possession. Don't count and-one free throws separately. Keep this in a `pbp_poss` field.

**On-court players.** Track the five players for each team through substitutions. Infer period starters from the first events and substitutions when needed. Validate each stint with player minutes.

**Metrics, at stint, player-season and lineup grains:**

```python
on_net = 100*(pts_for_on - pts_against_on)/poss_on
off_net = 100*(pts_for_off - pts_against_off)/poss_off
on_off = on_net - off_net

average_lead = time_weighted_mean(score_margin)      # per team-season, for BPM
```

Publish on/off and lineup values with possessions, and label them raw.

**Garbage-time filter.** Use the Cleaning the Glass definition:

```python
# Starts in Q4 only when all conditions hold:
#   12:00 to 9:00 left: margin >= 25
#    9:00 to 6:00 left: margin >= 20
#    6:00 to 0:00 left: margin >= 10
#   2 or fewer starters on the floor, across both teams combined
#   the game does not return under the threshold later
# Also remove end-of-period heave possessions: Q1 to Q3 possessions starting with <= 4 seconds left.
```

Add filtered versions of team ratings, player on/off and lineup ratings. Keep unfiltered versions as well.

**RAPM with a BPM prior.** Build this only after BPM passes validation.

```python
# One row per stint. Target: points per 100 for the offence; weight: possessions.
# Two columns per player: offence (+1 on offence) and defence (-1 on defence).
# Controls: home court, and a score-margin term for the rubber-band effect.
beta = beta_prior + solve(X.T @ W @ X + lam*I, X.T @ W @ (y - X @ beta_prior))
```

- Use several seasons, with time decay on older possessions.
- Use `pbp_poss` and garbage-time-filtered stints as variants, and log which is primary.
- Use the player's OBPM and DBPM, or a stable blend, as offensive and defensive priors.
- Tune `lam` by predicting future-season results. Don't tune on in-sample fit.
- Keep plain RAPM alongside the prior version.
- Store values by player, as-of date and training window, with possessions.
- Use sparse solvers, so the design matrix stays efficient.

Don't try to reproduce EPM, LEBRON or DARKO. If benchmark data is available, compare with it for sanity only.

## 9. Era comparison and current form

Historical comparison always uses the same season and season type. Current form uses data available before the as-of date.

### Era comparison

Apply to these at minimum: TS, eFG, 3PA rate, FT rate, USG, AST%, TOV%, ORB%, DRB%, STL%, BLK%, per-100 production, ORtg, DRtg, Net Rating, BPM, OBPM, DBPM, WS/48, PER. Team equivalents use the same methods.

```python
relative = value - Lg_value
index = 100 * value / Lg_value
z = (value - weighted_mean) / weighted_sd     # within season among qualifiers
percentile = weighted_rank(value)             # within season among qualifiers
```

- Weight by the stat's denominator, or by minutes for player ratings.
- Default to z-scores for all-era ranking. Use indexes only for display.
- Suppress index values where the league base is small, such as three-point rates in the early 1980s.
- Calculate career values as weighted means of season z-scores.
- Don't translate counting stats between eras with a pace ratio. Use per-100 rates and z-scores.
- Store the cohort size and filter behind every z-score and percentile.

### Current form

**Shrunk rate:**

```python
shrunk_rate = (makes + k*prior_rate) / (attempts + k)
```

Use career-to-date, age and position information for the prior. Build the prior only from games before the as-of date.

**Decay-weighted rate:**

```python
weight = d**days_ago
weighted_rate = sum(weight*numerator) / sum(weight*denominator)
```

Combine them by using weighted makes and attempts in the shrunk rate. Tune `k` and `d` separately for each stat by predicting the next game or next 10 games, with walk-forward validation. Compare against the season-to-date average, and keep a simple average if tuning doesn't beat it.

Initial values: for three-point percentage, start with `k = 320` attempts. This comes from an estimate of 0.7 reliability at about 750 attempts, so treat it as a starting point only. A 60% shooter on 50 attempts with a 36% prior should be about 39%.

**Apply to:** minutes, USG, TS, 3P%, 3PA rate, FT rate, AST%, TOV%, ORB%, DRB%, STL%, BLK%, and per-100 scoring. Also publish last-5, last-10 and last-20 raw splits for transparency.

Compare form values with same-date league baselines, and show the raw number and sample size beside each shrunk value. Keep playoff form on its own baseline.

## 10. Validation

A metric is complete only when its tests pass in the project's test framework.

**Formula fixtures.** Hard-code these inputs and expected values.

```python
# 2004-05 Suns, team-season
FG, FGA, TOV, FTA, ORB = 3351, 7018, 1125, 2080, 967
P3, FT, Opp_DRB = 796, 1556, 2550
DRB, Opp_ORB = 2652, 1233
Opp_FG, Opp_FGA, Opp_3P, Opp_TOV, Opp_FTA, Opp_FT = 3328, 7485, 494, 1131, 1775, 1320
# Expected:
# eFG .534, TOV .124, ORB .275, FT rate .222
# Opp eFG .478, Opp TOV .120, DRB .683, Opp FT rate .176

# 2016-17 LeBron James, BPM
# per-100: adj_pts 30.4, 3PM 2.2, AST 11.5, TOV 5.4, ORB 1.7, DRB 9.7, STL 1.6, BLK 0.8, PF 2.4, FGA 24.0, FTA 9.5
# position 2.3, role 1.0, team constant -8.0, pct possessions 0.70, BPM 7.6
# Expected: raw about 15.6 (15.5 with rounded inputs), BPM about +7.6, VORP 6.7

# 2008-09 LeBron James, Win Shares
# PProd 2345.9, TotPoss 1928.1, Lg_PPP 1.083, Lg_PPG 100, Tm_Pace 88.7, Lg_Pace 91.7
# MP 3054, Tm_MP 19780, Tm_Def_Poss 7341, DRtg 99.1
# Expected: OWS 13.7, DWS 6.54, WS 20.27

# Lead adjustment
# Team +3.0 with average lead +1.4 gives +3.24
```

Tolerance is ±0.1 for BPM and Win Shares, and ±0.001 for the Four Factors. The fixtures test formulas, not the pipeline.

**Reference comparison.** Compare a sample of seasons with Basketball-Reference, or with project season-level data derived from it. Include seasons from at least 1975, 1985, 1998, 2012, and the latest complete season. Report mean absolute error by metric.

**Refresh checks:**

- Primary keys are unique at each grain.
- Each regular-season game has two team rows, and team points match opponent points.
- Player points, rebounds and minutes sum to team totals. Attempts can differ from 2025-26.
- Team minutes equal 240 + 25 × overtime periods.
- Season league Net Rating, MOV and SRS centre on 0.
- Possession-weighted final BPM reproduces each team's target rating.
- Minute-weighted league PER equals 15.
- Team Win Shares track team wins. Published error is a mean absolute error of 2.74 and an RMSE of 3.41 wins.
- Pythagorean wins have an RMSE near the published 3.14 wins.
- Rates stay in possible ranges, allowing for small-sample extremes.
- No metric appears before its coverage start.
- No as-of metric uses same-day or future games.
- Latest game date advances during the season; raise an alert if it doesn't.
- Row counts and key aggregates don't change for closed seasons without a logged reason.

## 11. Build sequence and definition of done

Work in this dependency order. Use existing assets wherever the decision log allows.

1. Audit, source checks and decision log.
2. Clean identifiers, season mapping, game types and coverage flags.
3. Team-game foundations: opponent join, possessions, pace.
4. League baselines.
5. Team metrics, then SRS, Adjusted Net Rating and Elo.
6. Player rates and individual ratings.
7. BPM, OBPM, DBPM, VORP and Win Shares.
8. Era comparison and current-form metrics.
9. Play-by-play metrics, if the gate passes.
10. PER, plus any remaining low-priority metrics.

Run tests after each step. Don't start a step until its inputs pass.

**Done means:**

- [ ] Decision log covers every metric in this brief, with action and reason.
- [ ] Each metric is available at its required grains, or is logged as `blocked`.
- [ ] Definitions exist in one place, with version and coverage metadata.
- [ ] Tests in section 10 pass, or each exception is logged and explained.
- [ ] Existing consumers still work, or the user approved the change.
- [ ] Refreshing adds new games without a manual rebuild, following the project's existing pattern.
- [ ] Documentation lists each metric, its location, its grains, and how to query it.

**Final report to the user:** datasets reused, modified and created; metrics delivered and blocked; test results; calibration error for BPM; the play-by-play gate result; and any decisions they should review.

## 12. Reference sources

Use these to resolve ambiguity. If a source conflicts with this brief, log it and follow the source's worked example.

- [Basketball-Reference glossary](https://www.basketball-reference.com/about/glossary.html)
- [Four Factors](https://www.basketball-reference.com/about/factors.html)
- [Box Plus/Minus 2.0](https://www.basketball-reference.com/about/bpm2.html)
- [Win Shares](https://www.basketball-reference.com/about/ws.html)
- [Individual ratings](https://www.basketball-reference.com/about/ratings.html)
- [PER](https://www.basketball-reference.com/about/per.html)
- [Data coverage](https://www.basketball-reference.com/data/stats-coverage-game.html)
- [Cleaning the Glass garbage time](https://cleaningtheglass.com/stats/guide/garbage_time)
- [Heave rule report](https://www.thescore.com/s/32356837)
- [EPM methodology](https://dunksandthrees.com/about/epm)
- [Kaggle dataset](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores)
- [Third-party file description](https://github.com/owensharpe/predicting-nba-games)
- [Elo build guide](https://luke-lite.github.io/blog/how-to-build-an-NBA-Elo-rating-system)
- [Three-point stability study](https://fansided.com/2014/08/29/long-take-three-point-shooting-stabilize)
