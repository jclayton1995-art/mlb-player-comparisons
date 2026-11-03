# Comps v2 — model design & architecture (updated 2026-10-19)

## Decisions
- UI stack: React (Vite + TypeScript) frontend served by FastAPI. `./run.sh` → http://localhost:8000. Old Streamlit app in `legacy/`.
- Scope: batters (done through 2026 data). Pitchers / pitch-arsenal comps later.
- Comps are chosen on **underlying skills only**. Results (AVG/wRC+/xwOBA) are projection targets, never similarity inputs.
- Age enters the outcome regression (age + age²), not the similarity profile.
- Bat tracking (2024+) is shown on the card but NOT a model input — see experiment below.
- Chase-contact% (O-Contact%) removed from the model 2026-10-19: it held the top ridge weight but dropping it left the backtest unchanged (21.10 → 21.14 wRC+ RMSE, xwOBA slightly better). Small denominator, redundant with whiff%/zone-contact%. Still shown in the data.

## Data sources (as of Oct 2026)
- Baseball Savant via pybaseball: works from scripts.
- FanGraphs: blocks all scripted clients (Cloudflare JS challenge; curl_cffi impersonation also fails). Pulled through Jack's Chrome with `scripts/fangraphs_browser_pull.js` (12 single-season API calls; multi-season ranges need membership). Saved to `data/cache/fangraphs_bat_2015_2026.json`; `src/data/fangraphs_api.py` reads it in place of pybaseball's batting_stats. Pitching file not yet saved (Chrome blocked the second download).
- 2015–2026 batters: 5,668 usable hitter-seasons. Age/ISO/BABIP/wOBA/WAR/plate-discipline splits/bat tracking joined by MLBAM id.
- Pull-air% from bulk pitch-level Statcast (`refresh_data.py --statcast-only`, cached per season) — done for all seasons; in the model (shape cluster, ~4% weight).

## Changes since 2026-10-26 (all backtested, test seasons 2022–2025)
- **Track-record adjustment**: wRC+ projection += 0.46 × career gap between results and what xwOBA implies (β fit 2019–21, validated 2022–25). 21.14 → 21.07.
- **Neighborhood-offset correction** for kNN edge bias: shift by regression(target) − regression(comps). Top-tier (140+) bias −9 → −3. 21.07 → 20.88.
- **History blending**: each skill blended with the player's prior two seasons (weights 0.6 / 0.3) before z-scoring; shrinkage uses the blended sample. xwOBA .0256 → .0248; short seasons and stars both improve.
- **Similarity τ** calibrated against eligible comps (other players, 200+ PA) — previously a hitter's own prior season was his nearest row, making "90 = typical best match" ~2 points too strict. Median best match is now 90 by construction. Low-confidence flag at 85.
- **2020 treated as never happened** (`SKIP_SEASONS`): 2019 links to 2021. 20.88 → 20.78 wRC+, .0248 → .0247 xwOBA. Explicit next/prev season links everywhere.
- Current ladder (comps / regression / old app / Marcel): **20.78** / 20.74 / 21.9 / 21.9 wRC+ RMSE.

## UI (Nov 2026)
- App: one visual language — Savant-style percentile tracks; dumbbell (two dots + bar) for comparisons. Player hero band, projection range bars, comps as expandable rows, front page with top projections / climbs / falls / closest matches, Explore with percentile filters. Paper/ink palette, one navy, blue–red only for percentile data.
- Share card (1080×1350, navy ground, gold = the comp): headline "X comps to YEAR Y", similarity + tag (near-twin 95+, strong 90+, solid 80+, loose <80), runner-up chips, 4 shared-skill tracks, what the comp did next, projection payoff on paper. Comp selectable from top five.
- Deployed via Render blueprint (render.yaml); repo jclayton1995-art/mlb-player-comparisons, model + built frontend committed.

## Model (src/model/engine.py)
1. Season-relative z-scores, **shrunk by sample size**: z × n/(n+k), k = 2× Carleton-style stabilization points (prepare.SHRINK). Backtest: helps, most for <300 PA hitters.
2. PCA whitening (full rank) → Mahalanobis distance. Dropped FB% (=100−GB%−LD%), Swing% (≈ zone-swing + chase) and chase-contact%: compositional/redundant inputs got inflated weights under whitening without adding predictive value. **Rule: any feature whose weight looks surprising gets the drop test in the backtest.**
3. Ridge: whitened profile + age terms → next-season xwOBA, wRC+, K%, BB% (ISO/BABIP when present).
4. Embedding = [predicted outcomes, 0.30 × whitened profile]. Similarity 90 ≈ typical best comp.
5. Projection = kernel-weighted mean of next seasons of 40 nearest comps with a known next season; band = weighted 20th–80th pct.

Current features (19): EV, EV50, max EV, hard-hit%, barrel% (BBE), barrel/PA, launch angle, sweet-spot%, GB%, LD%, pull%, oppo%, pull-air%, chase%, zone-swing%, zone-contact%, whiff%, SwStr%, K%, BB%. Learned cluster weights (after chase-contact removal): approach 41%, power 31%, shape 25%, age 4%.

## Backtest (walk-forward, test seasons 2022–2025, 200+ PA both years, n=1,065)
| Method | wRC+ RMSE | xwOBA RMSE |
|---|---|---|
| Regression, no comps | 20.9 | .0255 |
| **40 nearest comps (v2)** | **21.1** | **.0259** |
| Old app (hand-weighted z) | 21.9 | .0280 |
| Marcel-style | 21.9 | .0263 |
| Naive | 25.7 | .0285 |

## 2024+ bat-tracking experiment (2025→2026, n=263, same test set)
Full-history standard model 20.33 wRC+ / .0249 xwOBA; modern-era (2024+) standard 20.71 / .0262; modern + 7 swing metrics 20.69 / .0264; swing-only 20.97 / .0267; Marcel 20.92 / .0251. Swing metrics add nothing on top of EV50/barrels/whiff and the modern model is starved for pairs. Re-run after 2027. Hooks are in place (FEATURES entries with default=False, cluster "swing", ModelConfig.min_season).

## Tested and rejected
Delta projection; pure prediction-space distance; reduced PCA rank; previous-season features (+0.1); sprint speed (Jack: hitting only); chase-contact% as a feature.

### Drop-test ledger (comps, wRC+ RMSE, test 2022–2025, current data)
Baseline 21.14 · without chase-contact% 21.14 (**removed**) · without K% 21.29 · without BB% 21.38 · without both 21.55 (**kept** — Jack considers K%/BB% results rather than skills, so they stay in the model but are excluded from the share card's skills table, which shows the top process metrics instead; footer reads "matched on skills, not on results").

## UI
- Player page: target rail + comp table with per-feature fingerprint, expandable side-by-side, bat tracking, what-happened-next.
- **Share card** (1080×1350 PNG): photo + hero stats; projection as a range bar (band = middle 60% of the 40 comps' next seasons, estimate = weighted mean, actual marked when known); 3 closest profiles with similarity and next-season wRC+ "(+7 vs ’21)"; skills table = the model's five highest-weighted process features (K%/BB% excluded; ≤2 per cluster, one per family of near-synonyms), cells colored Savant-style by within-season percentile (blue poor → red elite; direction-less metrics stay white). Palette: white / ink / one navy; blue–red is the only data color.
- **Explore** (`#/explore`): every hitter-season with its single best comp, similarity, comp-based projection, proj − now, and actual next season; sortable, filterable by name / season / PA floor; precomputed at server start (`build_explore`, ~2 s, chunked pairwise distances).
- Headshots proxied through `/api/headshot/{id}` and cached on disk so the PNG export isn't tainted. No upload endpoints.

## Open items
- Pitcher model (reuse engine with pitcher catalogue + targets); re-pull FanGraphs pitching file through Chrome.
- Possible: per-player "as-of" projection from the backtest alongside the live one; per-player "why these comps" feature pick on the card (currently model-wide five for consistency).
