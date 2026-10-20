#!/usr/bin/env bash
# Start the Comps app on http://localhost:8000
cd "$(dirname "$0")"
if [ ! -f data/model/batter_model.joblib ]; then
  echo "No trained model found — training first (about 20 seconds)..."
  python scripts/train_model.py --no-backtest
fi
exec python -m uvicorn server.app:app --port "${PORT:-8000}"
