#!/usr/bin/env python3
"""Diagnose FanGraphs API access: which HTTP client is in use and what the server says."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("python:", sys.executable)
try:
    import curl_cffi
    print("curl_cffi:", curl_cffi.__version__)
except Exception as e:  # noqa: BLE001
    print("curl_cffi: NOT importable ->", e)

from src.data import fangraphs_api as f  # noqa: E402

print("client:", f._req.__name__ if hasattr(f._req, "__name__") else f._req, "impersonate:", f._IMPERSONATE)
params = {"pos": "all", "stats": "bat", "lg": "all", "qual": 400, "season": 2025, "season1": 2025,
          "month": 0, "team": 0, "pageitems": 3, "pagenum": 1, "ind": 0, "type": 8}
for label, kwargs in [("with impersonation", f._IMPERSONATE), ("plain", {})]:
    try:
        r = f._req.get(f.API, params=params, headers=f.HEADERS, timeout=60, **kwargs)
        body = r.text[:200].replace("\n", " ")
        print(f"{label}: status {r.status_code} | {body}")
    except Exception as e:  # noqa: BLE001
        print(f"{label}: ERROR {type(e).__name__}: {str(e)[:200]}")
