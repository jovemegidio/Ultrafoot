"""
Import player photos from Donwloader/times/{Country}/{Team}/jogadores/
into data/assets/players/{file_key}/{slug}.jpg

Matches team folders to seed file_keys by normalizing team names.
"""

import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DONWLOADER_TIMES = BASE / "Donwloader" / "times"
DEST = BASE / "data" / "assets" / "players"
SEEDS = BASE / "data" / "seeds"


def slug(nome: str) -> str:
    """Same logic as desktop_app._slug_player_name"""
    texto = (nome or "").lower()
    normalizado = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    normalizado = re.sub(r"[^a-z0-9]+", "-", normalizado).strip("-")
    return normalizado or "jogador"


def normalize_team_name(name: str) -> str:
    """Normalize a team name for fuzzy matching."""
    text = name.lower().strip()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_all_teams() -> dict[str, str]:
    """Returns { normalized_team_name: file_key } from seeds."""
    mapping = {}

    # Brazilian teams
    br_path = SEEDS / "teams_br.json"
    if br_path.exists():
        with open(br_path, "r", encoding="utf-8") as f:
            br = json.load(f)
        for division in ("serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"):
            for team in br.get(division, []):
                nome = team.get("nome", "")
                fk = team.get("file_key", "")
                if nome and fk:
                    mapping[normalize_team_name(nome)] = fk

    # European / world teams
    eu_path = SEEDS / "teams_eu.json"
    if eu_path.exists():
        with open(eu_path, "r", encoding="utf-8") as f:
            eu = json.load(f)
        for country_data in eu.values():
            if not isinstance(country_data, dict):
                continue
            for div_teams in country_data.get("divisoes", {}).values():
                if not isinstance(div_teams, list):
                    continue
                for team in div_teams:
                    nome = team.get("nome", "")
                    fk = team.get("file_key", "")
                    if nome and fk:
                        mapping[normalize_team_name(nome)] = fk

    return mapping


def find_team_file_key(folder_name: str, team_map: dict[str, str]) -> str | None:
    """Try to match a Donwloader team folder to a seed file_key."""
    norm = normalize_team_name(folder_name)
    if norm in team_map:
        return team_map[norm]

    # Try partial match (folder name contained in seed name or vice versa)
    for seed_name, fk in team_map.items():
        if norm and seed_name and (norm in seed_name or seed_name in norm):
            return fk

    return None


def main():
    team_map = load_all_teams()
    print(f"Loaded {len(team_map)} teams from seeds")

    copied = 0
    skipped = 0
    unmatched_teams = set()

    for country_dir in sorted(DONWLOADER_TIMES.iterdir()):
        if not country_dir.is_dir():
            continue
        for team_dir in sorted(country_dir.iterdir()):
            if not team_dir.is_dir():
                continue

            jogadores_dir = team_dir / "jogadores"
            if not jogadores_dir.is_dir():
                continue

            file_key = find_team_file_key(team_dir.name, team_map)
            if not file_key:
                photos = list(jogadores_dir.glob("*.jpg")) + list(jogadores_dir.glob("*.png"))
                if photos:
                    unmatched_teams.add(f"{country_dir.name}/{team_dir.name} ({len(photos)} fotos)")
                skipped += len(photos) if photos else 0
                continue

            dest_dir = DEST / file_key
            dest_dir.mkdir(parents=True, exist_ok=True)

            for photo in jogadores_dir.iterdir():
                if photo.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue
                player_name = photo.stem.replace("_", " ")
                player_slug = slug(player_name)
                dest_path = dest_dir / f"{player_slug}{photo.suffix.lower()}"
                shutil.copy2(photo, dest_path)
                copied += 1

    print(f"\nCopied: {copied} photos")
    print(f"Skipped (unmatched teams): {skipped} photos")
    if unmatched_teams:
        print(f"\nUnmatched teams ({len(unmatched_teams)}):")
        for t in sorted(unmatched_teams):
            print(f"  - {t}")


if __name__ == "__main__":
    main()
