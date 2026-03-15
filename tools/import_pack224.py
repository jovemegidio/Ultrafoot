# -*- coding: utf-8 -*-
"""
Import Pack224 — Parses 224 .cfg league configs and .ban team files
from the Pack224 directory and generates comprehensive seed data.
Only imports countries NOT already present in teams_eu.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ban_parser import parse_ban_file, calc_overall, map_position

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_DIR = os.path.join(BASE_DIR, "Pack224")
PACK_CFG_DIR = os.path.join(PACK_DIR, "conf_ligas_nacionais")
PACK_TEAMS_DIR = os.path.join(PACK_DIR, "teams")
SEEDS_DIR = os.path.join(BASE_DIR, "data", "seeds")

# Existing seed files
TEAMS_EU_FILE = os.path.join(SEEDS_DIR, "teams_eu.json")
PLAYERS_EU_FILE = os.path.join(SEEDS_DIR, "players_eu.json")
LEAGUES_FILE = os.path.join(SEEDS_DIR, "leagues.json")

# Output files (will be merged into existing)
OUTPUT_TEAMS = os.path.join(SEEDS_DIR, "teams_eu.json")
OUTPUT_PLAYERS = os.path.join(SEEDS_DIR, "players_eu.json")
OUTPUT_LEAGUES = os.path.join(SEEDS_DIR, "leagues.json")

# CFG code -> .ban suffix override (when they don't match directly)
SUFFIX_OVERRIDES = {
    "AGO": ["ang"],
    "ARS": ["ara"],
    "CPR": ["chp"],
    "CRS": ["cor"],
    "CSR": ["cri", "csr"],  # Costa Rica
    "ESS": ["esw"],          # Essuatíni
    "ESV": ["slv"],          # El Salvador
    "GAN": ["gha"],          # Gana
    "ICO": ["ica", "ico"],   # Ilhas Cook
    "IDO": ["idn"],          # Indonésia
    "IFA": ["fro"],          # Ilhas Faroe
    "MCD": ["mkd"],          # Macedônia
    "MIC": ["mic"],          # Micronésia
    "NOZ": ["nzl", "noz"],   # Nova Zelândia
    "RTC": ["cze"],          # República Tcheca
    "SAN": ["smr"],          # San Marino
    "TGO": ["tgo"],          # Togo
    "TON": ["tga"],          # Tonga
    "TRT": ["tri"],          # Trinidad e Tobago
    "TTI": ["tti", "tah"],   # Taiti
    "AFS": ["rsa", "afs"],   # África do Sul
    # Brazilian states (BRA has special handling)
    "BRA": ["bra", "br"],
}

# Skip these countries (already fully managed by existing seed system)
SKIP_COUNTRIES = {"BRA"}  # BR teams managed by teams_br.json

try:
    import javaobj
except ImportError:
    print("ERROR: javaobj-py3 not installed. Run: pip install javaobj-py3")
    sys.exit(1)


def parse_cfg_file(filepath):
    """Parse a .cfg league config file and return list of division configs."""
    with open(filepath, 'rb') as f:
        obj = javaobj.load(f)
    arr = getattr(obj, 'a', [])
    divisions = []
    for item in arr:
        div = {
            "divisao": int(getattr(item, 'divisao', 1)),
            "n_times": int(getattr(item, 'nTimes', 20)),
            "nome": str(getattr(item, 'nomeDivisao', '') or ''),
            "pais_nome": str(getattr(item, 'nome', '') or ''),
            "n_grupos": int(getattr(item, 'nGrupos', 0)),
            "n_rebaixados": int(getattr(item, 'nRebaixados', 0)),
            "dois_turnos": bool(getattr(item, 'doisTurnos', False)),
            "formula": int(getattr(item, 'formula', 0)),
        }
        divisions.append(div)
    return divisions


def find_ban_files_for_country(country_code):
    """Find all .ban files belonging to a country."""
    all_files = os.listdir(PACK_TEAMS_DIR)
    ban_files = set()

    # Determine suffixes to search
    suffixes = SUFFIX_OVERRIDES.get(country_code, [country_code.lower()])
    # Always include the lowercase code itself
    if country_code.lower() not in suffixes:
        suffixes = [country_code.lower()] + suffixes

    for suffix in suffixes:
        for f in all_files:
            if f.endswith(f"_{suffix}.ban"):
                ban_files.add(f)

    return sorted(ban_files)


def parse_country(country_code, divisions):
    """Parse all teams for a country and assign to divisions."""
    ban_files = find_ban_files_for_country(country_code)

    if not ban_files:
        return None, None

    teams = []
    players_db = {}

    for ban_file in ban_files:
        file_key = ban_file[:-4]
        ban_path = os.path.join(PACK_TEAMS_DIR, ban_file)

        team_data, players = parse_ban_file(ban_path)
        if not team_data or not players:
            continue

        name = team_data['name']
        if not name or name.strip() == '':
            name = file_key.replace('_', ' ').title()

        nivel = team_data.get('nivel', 0)
        cap = team_data.get('capacity', 0) or 3000

        base_prestige = {5: 85, 4: 75, 3: 65, 2: 55, 1: 45, 0: 35}
        prestige_base = base_prestige.get(nivel, 35)

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

        squad_bonus = min(3, max(0, (len(players) - 15) // 4))
        prestigio = min(95, prestige_base + cap_bonus + squad_bonus)

        saldo = int(prestigio ** 2.2 * 500)
        torcida = int(prestigio ** 2.5 * 30)
        cap = team_data.get('capacity', 0) or int(prestigio * 400)

        words = name.split()
        if len(words) >= 2:
            curto = (words[0][:2] + words[1][0]).upper()
        else:
            curto = name[:3].upper()

        team_entry = {
            "nome": name,
            "curto": curto,
            "cidade": name,
            "estado": country_code,
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
        players_db[name] = players

    teams.sort(key=lambda t: t['prestigio'], reverse=True)

    # Assign to divisions
    div_data = {}
    idx = 0
    for div_cfg in divisions:
        div_num = div_cfg['divisao']
        n_times = div_cfg['n_times']
        div_teams = teams[idx:idx + n_times]
        idx += n_times
        if div_teams:
            div_data[f"div_{div_num}"] = div_teams

    if idx < len(teams):
        last_key = f"div_{max(int(k.split('_')[1]) for k in div_data)}" if div_data else "div_1"
        if last_key in div_data:
            div_data[last_key].extend(teams[idx:])
        else:
            div_data["sem_divisao"] = teams[idx:]

    return div_data, players_db


def main():
    # Load existing data
    existing_teams = {}
    if os.path.exists(TEAMS_EU_FILE):
        with open(TEAMS_EU_FILE, 'r', encoding='utf-8') as f:
            existing_teams = json.load(f)

    existing_players = {}
    if os.path.exists(PLAYERS_EU_FILE):
        with open(PLAYERS_EU_FILE, 'r', encoding='utf-8') as f:
            existing_players = json.load(f)

    existing_leagues = {}
    if os.path.exists(LEAGUES_FILE):
        with open(LEAGUES_FILE, 'r', encoding='utf-8') as f:
            existing_leagues = json.load(f)

    print(f"Existing: {len(existing_teams)} countries, {len(existing_players)} team rosters")
    print(f"Existing league configs: {len(existing_leagues)} countries")

    # Parse all .cfg files
    cfg_files = sorted([f for f in os.listdir(PACK_CFG_DIR) if f.endswith('.cfg')])
    print(f"\nFound {len(cfg_files)} .cfg files to process")

    new_countries = 0
    new_teams_total = 0
    skipped = 0

    for cfg_file in cfg_files:
        code = cfg_file[:-4]

        if code in SKIP_COUNTRIES:
            skipped += 1
            continue

        # Skip if already in teams_eu (we keep existing data)
        if code in existing_teams:
            skipped += 1
            continue

        cfg_path = os.path.join(PACK_CFG_DIR, cfg_file)
        divisions = parse_cfg_file(cfg_path)

        if not divisions:
            print(f"  {code}: no divisions found, skipping")
            continue

        pais_nome = divisions[0].get('pais_nome', code)

        # Parse teams
        div_data, players_db = parse_country(code, divisions)

        if not div_data:
            print(f"  {code} ({pais_nome}): no .ban files found, skipping")
            continue

        total_teams = sum(len(v) for v in div_data.values())
        print(f"  {code} ({pais_nome}): {total_teams} teams in {len(div_data)} divisions")

        # Add to existing data
        existing_teams[code] = {
            "pais": code,
            "pais_nome": pais_nome,
            "ligas": [{"divisao": d["divisao"], "n_times": d["n_times"],
                       "nome": d["nome"]} for d in divisions],
            "divisoes": div_data,
        }

        # Update league configs
        existing_leagues[code] = [{"divisao": d["divisao"], "n_times": d["n_times"],
                                   "nome": d["nome"]} for d in divisions]

        existing_players.update(players_db)
        new_countries += 1
        new_teams_total += total_teams

    # Save
    with open(OUTPUT_TEAMS, 'w', encoding='utf-8') as f:
        json.dump(existing_teams, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_PLAYERS, 'w', encoding='utf-8') as f:
        json.dump(existing_players, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_LEAGUES, 'w', encoding='utf-8') as f:
        json.dump(existing_leagues, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Import complete!")
    print(f"  New countries added: {new_countries}")
    print(f"  New teams added: {new_teams_total}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Total countries now: {len(existing_teams)}")
    print(f"  Total player rosters: {len(existing_players)}")
    print(f"\nFiles updated:")
    print(f"  {OUTPUT_TEAMS}")
    print(f"  {OUTPUT_PLAYERS}")
    print(f"  {OUTPUT_LEAGUES}")


if __name__ == "__main__":
    main()
