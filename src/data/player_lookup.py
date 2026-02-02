"""Player ID crosswalk between MLBAM and FanGraphs IDs."""

from typing import Optional, Dict, List
import pandas as pd
from pybaseball import playerid_reverse_lookup

from .cache_manager import CacheManager


class PlayerRegistry:
    """Manages player ID crosswalk between different data sources."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()
        self._registry: Optional[pd.DataFrame] = None

    def _load_registry(self) -> pd.DataFrame:
        """Load or build the player registry."""
        if self._registry is not None:
            return self._registry

        cached = self.cache.get("player_registry")
        if cached is not None:
            self._registry = cached
            return self._registry

        self._registry = pd.DataFrame(columns=[
            "key_mlbam", "key_fangraphs", "name_first", "name_last", "name_full"
        ])
        return self._registry

    def lookup_by_mlbam(self, mlbam_ids: List[int]) -> pd.DataFrame:
        """Look up player info by MLBAM IDs, fetching from API if needed."""
        registry = self._load_registry()

        known_ids = set(registry["key_mlbam"].dropna().astype(int).tolist())
        unknown_ids = [pid for pid in mlbam_ids if pid not in known_ids]

        if unknown_ids:
            try:
                new_players = playerid_reverse_lookup(unknown_ids, key_type="mlbam")
                if not new_players.empty:
                    new_players["name_full"] = (
                        new_players["name_first"] + " " + new_players["name_last"]
                    )
                    self._registry = pd.concat(
                        [registry, new_players], ignore_index=True
                    ).drop_duplicates(subset=["key_mlbam"])
                    self.cache.set("player_registry", self._registry)
            except Exception:
                pass

        return self._registry[self._registry["key_mlbam"].isin(mlbam_ids)]

    def get_fangraphs_id(self, mlbam_id: int) -> Optional[int]:
        """Get FanGraphs ID for a given MLBAM ID."""
        result = self.lookup_by_mlbam([mlbam_id])
        if not result.empty:
            fg_id = result.iloc[0].get("key_fangraphs")
            if pd.notna(fg_id):
                return int(fg_id)
        return None

    def get_mlbam_id(self, fangraphs_id: int) -> Optional[int]:
        """Get MLBAM ID for a given FanGraphs ID."""
        registry = self._load_registry()
        match = registry[registry["key_fangraphs"] == fangraphs_id]
        if not match.empty:
            mlbam_id = match.iloc[0].get("key_mlbam")
            if pd.notna(mlbam_id):
                return int(mlbam_id)
        return None

    def search_players(self, name_query: str) -> pd.DataFrame:
        """Search for players by name."""
        registry = self._load_registry()
        if registry.empty:
            return registry

        query_lower = name_query.lower()
        mask = registry["name_full"].str.lower().str.contains(query_lower, na=False)
        return registry[mask]

    def get_player_name(self, mlbam_id: int) -> str:
        """Get player full name by MLBAM ID."""
        result = self.lookup_by_mlbam([mlbam_id])
        if not result.empty:
            return result.iloc[0].get("name_full", f"Unknown ({mlbam_id})")
        return f"Unknown ({mlbam_id})"
