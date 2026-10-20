#!/usr/bin/env python3
"""Train the batter comparison model and write the artifacts the API serves.

    python scripts/train_model.py            # train + quick backtest (~1 min)
    python scripts/train_model.py --no-backtest

Outputs (data/model/):
    batters.parquet        canonical hitter-seasons with within-season percentiles
    batter_model.joblib    fitted ComparisonModel
    batter_meta.json       features, importances, config, backtest table
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.prepare import load_batters, add_percentiles, FEATURES, OUTCOMES, TRACKING  # noqa: E402
from src.model.engine import ComparisonModel, ModelConfig  # noqa: E402
from src.model.backtest import run_backtest, summarize  # noqa: E402

PROCESSED = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "data" / "model"

CONFIG = ModelConfig(
    profile_weight=0.30,
    kernel_scale=2.0,
    k_default=40,
    ridge_alpha=10.0,
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-backtest", action="store_true")
    p.add_argument("--test-seasons", type=int, nargs="+", default=None)
    args = p.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    df = load_batters(PROCESSED)
    seasons = sorted(df["season"].unique())
    print(f"Loaded {len(df)} hitter-seasons, {seasons[0]}-{seasons[-1]}")
    for c in ["age", "pull_air_pct", "bat_speed"]:
        print(f"  {c}: {df[c].notna().mean():.0%} coverage" if c in df.columns else f"  {c}: absent")

    model = ComparisonModel(CONFIG).fit(df)
    print(f"Fitted on {len(model.features)} features, {model.train_pairs} training pairs; tau={model.tau:.3f}")
    print("Cluster importance:", {k: round(v, 3) for k, v in model.cluster_importance.items()})

    pct_cols = model.features + [o for o in OUTCOMES if o in df.columns] + [t for t in TRACKING if t in df.columns]
    out = add_percentiles(df, pct_cols)
    # Direct model projection for every row (used as a reference line in the UI)
    direct = model.predict_next(out)
    for t in model.targets:
        out[f"{t}_model_next"] = direct[t].values
    out.to_parquet(MODEL_DIR / "batters.parquet", index=False)
    model.save(MODEL_DIR / "batter_model.joblib")

    meta = model.summary()
    meta["n_rows"] = int(len(out))
    meta["trained_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    meta["outcomes"] = {k: v for k, v in OUTCOMES.items() if k in out.columns}
    meta["tracking"] = {k: v for k, v in TRACKING.items() if k in out.columns and out[k].notna().any()}

    if not args.no_backtest:
        last_pair = int(out.loc[out["pa_next"].notna(), "season"].max())
        test_seasons = args.test_seasons or [s for s in range(last_pair - 3, last_pair + 1)]
        print(f"Backtest on test seasons {test_seasons} ...")
        res = run_backtest(out, test_seasons, CONFIG, k_values=[CONFIG.k_default], verbose=False,
                           include_legacy=True, methods=["direct"])
        summ = summarize(res)
        print(summ.round(4).to_string(index=False))
        meta["backtest"] = {
            "test_seasons": test_seasons,
            "eval_min_pa": 200,
            "summary": summ.round(5).to_dict(orient="records"),
            "by_season": res.round(5).to_dict(orient="records"),
        }

    (MODEL_DIR / "batter_meta.json").write_text(json.dumps(meta, indent=2, default=float))
    print(f"Done in {time.time() - t0:.0f}s -> {MODEL_DIR}")


if __name__ == "__main__":
    main()
