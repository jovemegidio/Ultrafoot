# -*- coding: utf-8 -*-
"""
Asset registry and compliance summary for offline builds.

This service scans the current workspace/bundle and reports:
- available club badges and kits
- mapped vs missing assets
- soundtrack availability
- missing media that should fall back to placeholders
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Set

from config import BASE_DIR, DATA_DIR
from utils.logger import get_logger

log = get_logger(__name__)


class AssetRegistryService:
    """Scans packaged assets and exposes a compact compliance summary."""

    def __init__(self, base_dir: str = BASE_DIR, data_dir: str = DATA_DIR) -> None:
        self.base_dir = base_dir
        self.data_dir = data_dir
        self.teams_dir = os.path.join(base_dir, "teams")
        self.music_dirs = [
            os.path.join(base_dir, "data", "assets", "music"),
            os.path.join(base_dir, "music"),
        ]
        self.asset_map_path = os.path.join(data_dir, "seeds", "asset_map.json")
        self.teams_br_path = os.path.join(data_dir, "seeds", "teams_br.json")
        self.teams_eu_path = os.path.join(data_dir, "seeds", "teams_eu.json")

    @lru_cache(maxsize=1)
    def _load_asset_map(self) -> Dict:
        if not os.path.isfile(self.asset_map_path):
            return {}
        try:
            with open(self.asset_map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            log.warning("Erro ao carregar asset_map.json: %s", e)
        return {}

    def _iter_asset_map_entries(self, data: Dict) -> Iterable[tuple[str, str]]:
        if not isinstance(data, dict):
            return []
        entries = []
        for key, value in data.items():
            if isinstance(value, str):
                entries.append((key, value))
                continue
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, str):
                        entries.append((f"{key}:{sub_key}", sub_value))
        return entries

    @lru_cache(maxsize=1)
    def _expected_club_keys(self) -> List[str]:
        keys: Set[str] = set()
        keys.update(self._extract_club_keys_br())
        keys.update(self._extract_club_keys_eu())
        return sorted(keys)

    def _extract_club_keys_br(self) -> Iterable[str]:
        if not os.path.isfile(self.teams_br_path):
            return []
        try:
            with open(self.teams_br_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning("Erro ao carregar teams_br.json: %s", e)
            return []

        keys: Set[str] = set()
        if isinstance(data, dict):
            for clubes in data.values():
                if not isinstance(clubes, list):
                    continue
                for clube in clubes:
                    if isinstance(clube, dict):
                        fk = clube.get("file_key")
                        if fk:
                            keys.add(fk)
        return keys

    def _extract_club_keys_eu(self) -> Iterable[str]:
        if not os.path.isfile(self.teams_eu_path):
            return []
        try:
            with open(self.teams_eu_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.warning("Erro ao carregar teams_eu.json: %s", e)
            return []

        keys: Set[str] = set()
        if not isinstance(data, dict):
            return keys
        for country in data.values():
            if not isinstance(country, dict):
                continue
            divs = country.get("divisoes", {})
            if not isinstance(divs, dict):
                continue
            for teams in divs.values():
                if not isinstance(teams, list):
                    continue
                for clube in teams:
                    if isinstance(clube, dict):
                        fk = clube.get("file_key")
                        if fk:
                            keys.add(fk)
        return keys

    def _scan_png_dir(self, relative_dir: str) -> Set[str]:
        pasta = os.path.join(self.base_dir, relative_dir)
        if not os.path.isdir(pasta):
            return set()
        encontrados = set()
        for nome in os.listdir(pasta):
            if nome.lower().endswith(".png"):
                encontrados.add(os.path.splitext(nome)[0])
        return encontrados

    def _scan_music_files(self) -> List[str]:
        tracks: List[str] = []
        vistos: Set[str] = set()
        for pasta in self.music_dirs:
            if not os.path.isdir(pasta):
                continue
            for nome in os.listdir(pasta):
                if not nome.lower().endswith((".mp3", ".ogg", ".wav")):
                    continue
                if nome in vistos:
                    continue
                vistos.add(nome)
                tracks.append(nome)
        return sorted(tracks)

    def resolve_team_asset(self, file_key: str, kind: str = "escudo") -> Dict[str, object]:
        folders = {
            "escudo": "teams/escudos",
            "camisa": "teams/camisas",
            "camisa2": "teams/camisas2",
            "camisa3": "teams/camisas3",
        }
        rel_dir = folders.get(kind, "teams/escudos")
        path = os.path.join(self.base_dir, rel_dir, f"{file_key}.png")
        return {
            "file_key": file_key,
            "tipo": kind,
            "path": path if os.path.isfile(path) else "",
            "exists": os.path.isfile(path),
            "placeholder": not os.path.isfile(path),
        }

    def to_api_dict(self, licensing_engine=None, limit_missing: int = 30) -> Dict:
        expected = self._expected_club_keys()
        escudos = self._scan_png_dir("teams/escudos")
        camisas = self._scan_png_dir("teams/camisas")
        camisas2 = self._scan_png_dir("teams/camisas2")
        camisas3 = self._scan_png_dir("teams/camisas3")
        music_tracks = self._scan_music_files()
        asset_map = self._load_asset_map()

        missing_badges = [fk for fk in expected if fk not in escudos]
        missing_kits = [fk for fk in expected if fk not in camisas]
        missing_alt_kits = [fk for fk in expected if fk not in camisas2 and fk not in camisas3]
        broken_mappings = []
        asset_entries = list(self._iter_asset_map_entries(asset_map))
        for key, rel in asset_entries:
            full = os.path.join(self.base_dir, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                broken_mappings.append({"chave": key, "path": rel})

        critical_missing = []
        if licensing_engine:
            for fk in missing_badges[: limit_missing * 3]:
                try:
                    status = licensing_engine.status_licenca_clube(fk).value
                except Exception:
                    status = "generico"
                if status in {"oficial", "licenciado"}:
                    critical_missing.append({"file_key": fk, "status": status, "tipo": "escudo"})
            for fk in missing_kits[: limit_missing * 3]:
                try:
                    status = licensing_engine.status_licenca_clube(fk).value
                except Exception:
                    status = "generico"
                if status in {"oficial", "licenciado"}:
                    critical_missing.append({"file_key": fk, "status": status, "tipo": "camisa"})

        return {
            "summary": {
                "clubes_esperados": len(expected),
                "escudos_instalados": len(escudos),
                "camisas_instaladas": len(camisas),
                "camisas_alt_instaladas": len(camisas2) + len(camisas3),
                "faixas_musicais": len(music_tracks),
                "mapeamentos_assets": len(asset_entries),
                "mapeamentos_quebrados": len(broken_mappings),
                "escudos_faltantes": len(missing_badges),
                "camisas_faltantes": len(missing_kits),
                "kits_alt_faltantes": len(missing_alt_kits),
                "faltas_criticas_compliance": len(critical_missing),
            },
            "missing": {
                "escudos": missing_badges[:limit_missing],
                "camisas": missing_kits[:limit_missing],
                "alternativos": missing_alt_kits[:limit_missing],
            },
            "critical_missing": critical_missing[:limit_missing],
            "broken_mappings": broken_mappings[:limit_missing],
            "music_tracks": music_tracks[:limit_missing],
        }
