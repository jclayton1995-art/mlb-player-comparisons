"""Fall back to Baseball Savant's custom leaderboard CSV when FanGraphs is unreachable.

FanGraphs put `leaders-legacy.aspx` and the modern `/api/leaders/...` endpoints
behind a Cloudflare challenge that pybaseball can't pass. Savant exposes a
flat CSV download with most of the same fields. The functions here return
DataFrames shaped like `pybaseball.batting_stats` / `pitching_stats` output so
the existing mergers consume them without changes.

Lost vs FanGraphs: wRC+, ERA/FIP/xFIP/WAR, Stuff+, G/GS/W/L — proprietary or
not exposed by Savant.
"""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import requests

from .player_lookup import PlayerRegistry

SAVANT_URL = "https://baseballsavant.mlb.com/leaderboard/custom"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

BATTER_SELECTIONS = [
    "pa", "k_percent", "bb_percent",
    "batting_avg", "slg_percent", "on_base_percent", "on_base_plus_slg",
    "whiff_percent", "swing_percent", "oz_swing_percent",
    "iz_contact_percent", "oz_contact_percent",
    "groundballs_percent", "flyballs_percent",
    "pull_percent", "straightaway_percent", "opposite_percent",
]
BATTER_RENAME = {
    "pa": "PA",
    "k_percent": "K%",
    "bb_percent": "BB%",
    "batting_avg": "AVG",
    "on_base_percent": "OBP",
    "slg_percent": "SLG",
    "on_base_plus_slg": "OPS",
    "oz_swing_percent": "O-Swing%",
    "iz_contact_percent": "Z-Contact%",
    "groundballs_percent": "GB%",
    "flyballs_percent": "FB%",
    "pull_percent": "Pull%",
}

PITCHER_SELECTIONS = [
    "pa", "strikeout", "walk", "k_percent", "bb_percent",
    "whiff_percent", "swing_percent",
    "oz_swing_percent", "z_swing_percent", "oz_contact_percent", "iz_contact_percent",
    "zone_percent", "groundballs_percent", "p_formatted_ip", "pitches",
]
PITCHER_RENAME = {
    "k_percent": "K%",
    "bb_percent": "BB%",
    "groundballs_percent": "GB%",
    "oz_swing_percent": "O-Swing% (sc)",
    "swing_percent": "Swing% (sc)",
    "zone_percent": "Zone% (sc)",
    "iz_contact_percent": "Z-Contact% (sc)",
}


def _fetch_csv(year: int, kind: str, min_value, selections: list[str]) -> pd.DataFrame:
    params = {
        "year": year,
        "type": kind,
        "filter": "",
        "min": min_value,
        "selections": ",".join(selections),
        "chart": "false",
        "x": "ab", "y": "ab", "r": "no",
        "chartType": "beeswarm", "csv": "true",
    }
    resp = requests.get(SAVANT_URL, params=params, headers={"User-Agent": _UA}, timeout=60)
    resp.raise_for_status()
    text = resp.text.lstrip("﻿")
    if not text.strip() or "<html" in text[:200].lower():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(text))


def _normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    col = "last_name, first_name"
    if col in df.columns:
        parts = df[col].astype(str).str.split(", ", n=1, expand=True)
        if parts.shape[1] >= 2:
            df["Name"] = (parts[1].fillna("") + " " + parts[0].fillna("")).str.strip()
        else:
            df["Name"] = df[col]
    return df


def _coerce_slash(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")


def _attach_fangraphs_id(df: pd.DataFrame, registry: PlayerRegistry) -> pd.DataFrame:
    if "player_id" not in df.columns:
        return df
    mlbam_ids = df["player_id"].dropna().astype(int).tolist()
    info = registry.lookup_by_mlbam(mlbam_ids)
    if info.empty:
        df["IDfg"] = pd.NA
        return df
    id_map = info[["key_mlbam", "key_fangraphs"]].rename(
        columns={"key_mlbam": "player_id", "key_fangraphs": "IDfg"}
    )
    merged = df.merge(id_map, on="player_id", how="left")
    # Pandas merges NaN-to-NaN when paired with another matching key (e.g. Season),
    # which would Cartesian-join every Savant player with no FanGraphs ID to every
    # statcast player with no FanGraphs ID. Give each unmapped row a unique
    # negative sentinel so the downstream IDfg join can't accidentally match.
    # Registry's own -1 sentinel for "no FG match" gets the same treatment.
    needs_sentinel = merged["IDfg"].isna() | (merged["IDfg"] == -1)
    merged.loc[needs_sentinel, "IDfg"] = (
        -1_000_000 - merged.loc[needs_sentinel, "player_id"].astype("Int64")
    )
    return merged


def get_batter_leaderboard(
    year: int, min_pa: int = 50, registry: Optional[PlayerRegistry] = None
) -> pd.DataFrame:
    df = _fetch_csv(year, "batter", max(int(min_pa), 1), BATTER_SELECTIONS)
    if df.empty:
        return df
    df = _normalize_names(df)
    _coerce_slash(df, ["batting_avg", "slg_percent", "on_base_percent", "on_base_plus_slg"])

    if {"swing_percent", "whiff_percent"}.issubset(df.columns):
        # FanGraphs SwStr% = swings_missed / pitches. Savant whiff% is per-swing,
        # swing% is per-pitch → product gives the FanGraphs definition.
        df["SwStr%"] = df["swing_percent"] * df["whiff_percent"] / 100.0
        df["Contact%"] = 100.0 - df["whiff_percent"]

    df = df.rename(columns=BATTER_RENAME)
    df["Season"] = year
    if registry is not None:
        df = _attach_fangraphs_id(df, registry)
    return df


def get_pitcher_leaderboard(
    year: int, min_ip: int = 15, registry: Optional[PlayerRegistry] = None
) -> pd.DataFrame:
    # Savant's `min` for pitchers maps directly to innings pitched.
    df = _fetch_csv(year, "pitcher", max(int(min_ip), 1), PITCHER_SELECTIONS)
    if df.empty:
        return df
    df = _normalize_names(df)

    if "p_formatted_ip" in df.columns:
        df["IP"] = pd.to_numeric(df["p_formatted_ip"], errors="coerce")
    if "strikeout" in df.columns:
        df["SO"] = pd.to_numeric(df["strikeout"], errors="coerce")
    if "walk" in df.columns:
        df["BB"] = pd.to_numeric(df["walk"], errors="coerce")
    if {"swing_percent", "whiff_percent"}.issubset(df.columns):
        df["SwStr%"] = df["swing_percent"] * df["whiff_percent"] / 100.0
    if {"K%", "BB%"}.issubset(df.columns) or {"k_percent", "bb_percent"}.issubset(df.columns):
        k = df.get("K%", df.get("k_percent"))
        bb = df.get("BB%", df.get("bb_percent"))
        df["K-BB%"] = pd.to_numeric(k, errors="coerce") - pd.to_numeric(bb, errors="coerce")

    df = df.rename(columns=PITCHER_RENAME)
    df["Season"] = year
    if registry is not None:
        df = _attach_fangraphs_id(df, registry)
    return df
