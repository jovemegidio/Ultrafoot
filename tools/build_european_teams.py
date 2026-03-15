# -*- coding: utf-8 -*-
"""
Build European Teams JSON — Parses .ban files for European countries
and generates teams_eu.json compatible with seed_loader.
"""
import json
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ban_parser import parse_ban_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_DIR = os.path.join(BASE_DIR, "teams")
SEEDS_DIR = os.path.join(BASE_DIR, "data", "seeds")
LEAGUES_FILE = os.path.join(SEEDS_DIR, "leagues.json")
OUTPUT_FILE = os.path.join(SEEDS_DIR, "teams_eu.json")
PLAYERS_OUTPUT = os.path.join(SEEDS_DIR, "players_eu.json")

# Countries to process (top European leagues)
# Each country can have multiple suffixes for .ban files
EU_COUNTRIES = {
    "ING": {"suffixes": ["_ing", "_eng"], "pais_nome": "Inglaterra",
            "no_suffix": ["arsenal", "chelsea"]},
    "ESP": {"suffixes": ["_esp"], "pais_nome": "Espanha"},
    "ITA": {"suffixes": ["_ita", "_it"], "pais_nome": "Itália"},
    "ALE": {"suffixes": ["_ale"], "pais_nome": "Alemanha"},
    "FRA": {"suffixes": ["_fra", "_fr"], "pais_nome": "França"},
    "POR": {"suffixes": ["_por"], "pais_nome": "Portugal"},
    "HOL": {"suffixes": ["_hol"], "pais_nome": "Holanda"},
    "BEL": {"suffixes": ["_bel"], "pais_nome": "Bélgica"},
    "TUR": {"suffixes": ["_tur"], "pais_nome": "Turquia"},
    "RUS": {"suffixes": ["_rus"], "pais_nome": "Rússia"},
    "ESC": {"suffixes": ["_esc"], "pais_nome": "Escócia"},
    "SUI": {"suffixes": ["_sui"], "pais_nome": "Suíça"},
    "AUT": {"suffixes": ["_aut"], "pais_nome": "Áustria"},
    "GRE": {"suffixes": ["_gre"], "pais_nome": "Grécia"},
}

# Explicit mappings: file_key -> country code (for files with wrong/no suffix)
EXPLICIT_COUNTRY_MAP = {
    # English teams without _ing suffix
    "arsenal": "ING",
    "chelsea": "ING",
    "westham_eng": "ING",
    # Italian teams with _it suffix (handled by suffixes list)
    # French teams
    "parissaintgermain_fr": "FRA",
    "monaco_fr": "FRA",
    "lyon": "FRA",
}

# Known team name corrections (file_key -> proper name)
TEAM_NAME_FIXES = {
    "utdman_ing": "Manchester United",
    "machester_ing": "Manchester United",  # duplicate?
    "machestercity_ing": "Manchester City",
    "tottenhamhotspur_ing": "Tottenham Hotspur",
    "astonvilla_ing": "Aston Villa",
    "crystalpalace_ing": "Crystal Palace",
    "hullcity_ing": "Hull City",
    "leedsunited_ing": "Leeds United",
    "leicestercity_ing": "Leicester City",
    "ipswichtown_ing": "Ipswich Town",
    "mkdons_ing": "MK Dons",
    "nottinghamforest_ing": "Nottingham Forest",
    "norwichcity_ing": "Norwich City",
    "queenspark_ing": "Queens Park Rangers",
    "sheffieldunited_ing": "Sheffield United",
    "stokecity_ing": "Stoke City",
    "westbromwich_ing": "West Bromwich Albion",
    "bristolrovers_ing": "Bristol Rovers",
    "yorkcity_ing": "York City",
    "fgr_ing": "Forest Green Rovers",
}


def parse_country_teams(country_code, suffixes, explicit_keys=None):
    """Parse all .ban files for a country (supporting multiple suffixes)."""
    all_ban_files = os.listdir(TEAMS_DIR)
    ban_files = set()

    # Find files by suffix
    for suffix in suffixes:
        for f in all_ban_files:
            if f.endswith(suffix + '.ban'):
                ban_files.add(f)

    # Add explicit mappings
    if explicit_keys:
        for key in explicit_keys:
            fname = key + '.ban'
            if fname in all_ban_files:
                ban_files.add(fname)

    # Also check EXPLICIT_COUNTRY_MAP
    for fkey, cc in EXPLICIT_COUNTRY_MAP.items():
        if cc == country_code:
            fname = fkey + '.ban'
            if fname in all_ban_files:
                ban_files.add(fname)

    ban_files = sorted(ban_files)
    # Filter out reserve/II teams
    ban_files = [f for f in ban_files if 'II_' not in f and not f.endswith('II.ban')]

    teams = []
    players_db = {}

    for ban_file in ban_files:
        file_key = ban_file[:-4]  # remove .ban
        ban_path = os.path.join(TEAMS_DIR, ban_file)

        team_data, players = parse_ban_file(ban_path)
        if not team_data or not players:
            print(f"  SKIP {ban_file}: parse failed")
            continue

        name = TEAM_NAME_FIXES.get(file_key, team_data['name'])
        if not name:
            # Derive name from file_key
            name = file_key.replace(suffix, '').replace('_', ' ').title()

        # Calculate team prestige from nivel (n field: 0-5) and capacity
        nivel = team_data.get('nivel', 0)
        cap = team_data.get('capacity', 0) or 3000
        squad_size = len(players)

        # nivel is the primary quality indicator from Brasfoot
        # n=5 → 85-95, n=4 → 75-87, n=3 → 65-77, n=2 → 55-67, n=1 → 45-57, n=0 → 35-48
        base_prestige = {5: 85, 4: 75, 3: 65, 2: 55, 1: 45, 0: 35}
        prestige_base = base_prestige.get(nivel, 35)

        # Capacity bonus: bigger stadiums → higher prestige within tier
        if cap > 60000:
            cap_bonus = 10
        elif cap > 40000:
            cap_bonus = 7
        elif cap > 25000:
            cap_bonus = 5
        elif cap > 15000:
            cap_bonus = 3
        elif cap > 8000:
            cap_bonus = 1
        else:
            cap_bonus = 0

        # Squad size bonus (bigger squads = more resources)
        squad_bonus = min(3, max(0, (squad_size - 15) // 4))

        prestigio = min(95, prestige_base + cap_bonus + squad_bonus)

        # Estimate finances from prestige
        saldo = int(prestigio ** 2.2 * 500)
        torcida = int(prestigio ** 2.5 * 30)
        cap = team_data.get('capacity', 0) or int(prestigio * 400)

        # Generate short name (3 chars)
        words = name.split()
        if len(words) >= 2:
            curto = (words[0][:2] + words[1][0]).upper()
        else:
            curto = name[:3].upper()

        team_entry = {
            "nome": name,
            "curto": curto,
            "cidade": name,  # approximate
            "estado": country_code,  # use country code as 'estado'
            "cor1": team_data.get('cor1') or '#ffffff',
            "cor2": team_data.get('cor2') or '#000000',
            "prestigio": prestigio,
            "torcida": torcida,
            "estadio_cap": cap,
            "estadio_nome": team_data.get('stadium') or f"Estádio do {name}",
            "saldo": saldo,
            "file_key": file_key,
            "patrocinador": "",
        }
        teams.append(team_entry)

        # Save players
        players_db[name] = players

    # Sort by prestige (descending)
    teams.sort(key=lambda t: t['prestigio'], reverse=True)
    return teams, players_db


def assign_divisions(teams, league_config):
    """Assign teams to divisions based on league_config."""
    divisions = {}
    idx = 0

    for div_cfg in league_config:
        div_num = div_cfg['divisao']
        n_times = div_cfg['n_times']
        div_name = div_cfg['nome']

        div_teams = teams[idx:idx + n_times]
        idx += n_times

        if div_teams:
            divisions[f"div_{div_num}"] = div_teams
            print(f"    {div_name} (div {div_num}): {len(div_teams)} times")

    # Remaining teams go to last division or 'extras'
    if idx < len(teams):
        last_div = max(int(k.split('_')[1]) for k in divisions) if divisions else 1
        key = f"div_{last_div}"
        if key in divisions:
            divisions[key].extend(teams[idx:])
            print(f"    + {len(teams) - idx} extras added to div {last_div}")
        else:
            divisions["sem_divisao"] = teams[idx:]

    return divisions


def main():
    # Load league configs
    with open(LEAGUES_FILE, 'r', encoding='utf-8') as f:
        leagues = json.load(f)

    all_teams = {}
    all_players = {}

    for cc, info in EU_COUNTRIES.items():
        print(f"\n{'='*50}")
        print(f"Processing {info['pais_nome']} ({cc})...")
        print(f"{'='*50}")

        teams, players_db = parse_country_teams(
            cc,
            info['suffixes'],
            info.get('no_suffix', [])
        )
        print(f"  Parsed {len(teams)} teams")

        if not teams:
            continue

        # Get league config
        league_cfg = leagues.get(cc, [])
        if league_cfg:
            divisions = assign_divisions(teams, league_cfg)
        else:
            # Single division
            divisions = {"div_1": teams}

        all_teams[cc] = {
            "pais": cc,
            "pais_nome": info['pais_nome'],
            "ligas": league_cfg,
            "divisoes": divisions,
        }
        all_players.update(players_db)

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_teams, f, ensure_ascii=False, indent=2)
    print(f"\n\nSaved {len(all_teams)} countries to {OUTPUT_FILE}")

    with open(PLAYERS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_players)} teams' players to {PLAYERS_OUTPUT}")


if __name__ == "__main__":
    main()
