"""FanGraphs leaderboards via their JSON API — a drop-in for pybaseball's
batting_stats / pitching_stats, which broke when FanGraphs retired the legacy
HTML leaderboard (HTTP 403 on leaders-legacy.aspx).

Returns DataFrames with pybaseball-style column names (IDfg, Season, Name, Team,
Age, K%, BB%, wRC+, ...). Rate stats are 0-1 decimals, as pybaseball returned them.
Bonus columns not in pybaseball: key_mlbam (MLBAM id), and the bat-tracking block
(AvgBatSpeed, FastSwing%, SwingLength, SquaredUpContact%, BlastContact%, ...).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import pandas as pd

try:  # FanGraphs sits behind bot protection that fingerprints the TLS handshake;
    # curl_cffi impersonates a real Chrome handshake and gets through.
    from curl_cffi import requests as _req
    _IMPERSONATE = {"impersonate": "chrome"}
except ImportError:  # pragma: no cover
    import requests as _req
    _IMPERSONATE = {}

API = "https://www.fangraphs.com/api/leaders/major-league/data"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.fangraphs.com/leaders/major-league",
}
RENAME_COMMON = {
    "playerid": "IDfg",
    "PlayerName": "Name",
    "TeamNameAbb": "Team",
    "xMLBAMID": "key_mlbam",
    "sp_stuff": "Stuff+",
    "sp_location": "Location+",
    "sp_pitching": "Pitching+",
}
# pybaseball exposed FanGraphs' tracked plate-discipline block with a "(sc)" suffix
RENAME_SC = {
    "pfxO-Swing%": "O-Swing% (sc)",
    "pfxZ-Swing%": "Z-Swing% (sc)",
    "pfxSwing%": "Swing% (sc)",
    "pfxO-Contact%": "O-Contact% (sc)",
    "pfxZ-Contact%": "Z-Contact% (sc)",
    "pfxContact%": "Contact% (sc)",
    "pfxZone%": "Zone% (sc)",
}


def _fetch_season(stats: str, season: int, qual: int, retries: int = 3) -> pd.DataFrame:
    params = {
        "age": "", "pos": "all", "stats": stats, "lg": "all", "qual": qual,
        "season": season, "season1": season, "startdate": "", "enddate": "",
        "month": 0, "hand": "", "team": 0, "pageitems": 5000, "pagenum": 1,
        "ind": 0, "rost": 0, "players": "", "type": 8, "postseason": "",
        "sortdir": "default", "sortstat": "WAR",
    }
    last = None
    for attempt in range(retries):
        try:
            r = _req.get(API, params=params, headers=HEADERS, timeout=60, **_IMPERSONATE)
            if r.status_code == 403 and not _IMPERSONATE:
                raise RuntimeError("403 from FanGraphs. Install the Chrome-impersonating client:  pip install curl_cffi")
            r.raise_for_status()
            payload = r.json()
            rows = payload.get("data", [])
            df = pd.DataFrame(rows)
            if df.empty:
                return df
            # 'Name' from the API is an HTML anchor; PlayerName is the plain text
            if "Name" in df.columns and "PlayerName" in df.columns:
                df = df.drop(columns=["Name"])
            df = df.rename(columns={**RENAME_COMMON, **RENAME_SC})
            if "Season" not in df.columns:
                df["Season"] = season
            df["Season"] = df["Season"].astype(int)
            df["IDfg"] = pd.to_numeric(df["IDfg"], errors="coerce").astype("Int64")
            if "key_mlbam" in df.columns:
                df["key_mlbam"] = pd.to_numeric(df["key_mlbam"], errors="coerce").astype("Int64")
            return df
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"FanGraphs API failed for {stats} {season}: {last}")


CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
_LOCAL: dict = {}


def _load_local(stats: str) -> Optional[pd.DataFrame]:
    """Leaderboards saved by scripts/fangraphs_browser_pull.js (FanGraphs blocks scripted
    clients, so the data is pulled through a real browser and read from disk here)."""
    if stats in _LOCAL:
        return _LOCAL[stats]
    path = CACHE_DIR / f"fangraphs_{stats}_2015_2026.json"
    if not path.exists():
        _LOCAL[stats] = None
        return None
    payload = json.loads(path.read_text())
    df = pd.DataFrame(payload["rows"])
    df = df.rename(columns={**RENAME_COMMON, **RENAME_SC, "C+SwStr%": "CSW%"})
    df["Season"] = df["Season"].astype(int)
    df["IDfg"] = pd.to_numeric(df["IDfg"], errors="coerce").astype("Int64")
    if "key_mlbam" in df.columns:
        df["key_mlbam"] = pd.to_numeric(df["key_mlbam"], errors="coerce").astype("Int64")
    _LOCAL[stats] = df
    return df


def _stats(stats: str, start_season: int, end_season: Optional[int], qual: int) -> pd.DataFrame:
    end_season = end_season or start_season
    local = _load_local(stats)
    if local is not None:
        qcol = "PA" if stats == "bat" else "IP"
        sub = local[(local["Season"] >= start_season) & (local["Season"] <= end_season)]
        if qcol in sub.columns:
            sub = sub[pd.to_numeric(sub[qcol], errors="coerce") >= qual]
        return sub.reset_index(drop=True)
    frames = [_fetch_season(stats, y, qual) for y in range(start_season, end_season + 1)]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def batting_stats(start_season: int, end_season: Optional[int] = None, qual: int = 50, **_) -> pd.DataFrame:
    return _stats("bat", start_season, end_season, qual)


def pitching_stats(start_season: int, end_season: Optional[int] = None, qual: int = 20, **_) -> pd.DataFrame:
    return _stats("pit", start_season, end_season, qual)
