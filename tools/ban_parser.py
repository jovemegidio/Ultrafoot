# -*- coding: utf-8 -*-
"""
BAN File Parser — Extrai dados de times e jogadores dos arquivos .ban do Brasfoot.
Gera JSON compatível com o sistema de seeds do jogo.
"""
import javaobj
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_DIR = os.path.join(BASE_DIR, "teams")
SEEDS_DIR = os.path.join(BASE_DIR, "data", "seeds")

# Mapeamento de grupo de posição do Brasfoot para posições do jogo
# e=0 GOL, e=1 LAT (LD/LE), e=2 ZAG, e=3 MEI/VOL, e=4 ATA
POS_GROUP_MAP = {
    0: "GOL",
    1: "LD",   # Laterais — alternaremos LD/LE
    2: "ZAG",
    3: "VOL",  # Meias — mapearemos mais especificamente usando bitmask
    4: "CA",   # Atacantes — mapearemos mais especificamente
}

# Bitmask de posição do Brasfoot para posição específica
# O campo 'c' é um bitmask indicando posições possíveis
POS_BITMASK_MAP = {
    # Goleiros
    (0, None): "GOL",
    # Laterais
    (1, None): "LD",
    # Zagueiros
    (2, None): "ZAG",
    # Meias
    (3, None): "VOL",
    # Atacantes
    (4, None): "CA",
}


def calc_overall(h, g, pos_group, age):
    """Calcula overall baseado nos stats do BAN file.
    
    h e g são os principais indicadores de habilidade no formato Brasfoot.
    Mapeamos para escala 45-92.
    """
    primary = max(h, g)
    secondary = min(h, g)
    raw = primary * 2.8 + secondary * 1.0
    base = int(min(92, max(45, 48 + raw)))
    
    # Goleiros têm h/g inherentemente mais baixos no BAN
    if pos_group == 0:
        base = int(min(88, max(55, 55 + raw * 1.8)))
    
    # Ajuste por idade (prime years boost)
    if 24 <= age <= 29:
        base = min(92, base + 2)
    elif 30 <= age <= 32:
        base = min(90, base + 1)
    elif age >= 35:
        base = max(45, base - 2)
    
    return base


def map_position(pos_group, pos_mask, idx_in_group, total_in_group, h=5, g=5):
    """Mapeia grupo de posição e bitmask para posição específica."""
    if pos_group == 0:
        return "GOL"
    elif pos_group == 1:
        return "LE" if idx_in_group % 2 == 1 else "LD"
    elif pos_group == 2:
        return "ZAG"
    elif pos_group == 3:
        # Usar h vs g para diferenciar: h alto = mais técnico/ofensivo
        ratio = h / max(1, h + g)
        if ratio >= 0.6:
            # Técnico → MEI ou ME/MD
            return "MEI" if idx_in_group % 3 != 2 else ("ME" if idx_in_group % 2 == 0 else "MD")
        elif ratio <= 0.4:
            # Físico → VOL
            return "VOL"
        else:
            # Equilibrado → MC
            return "MC"
    elif pos_group == 4:
        frac = idx_in_group / max(1, total_in_group)
        if frac < 0.35:
            return "CA"
        elif frac < 0.65:
            return "PE"
        else:
            return "PD"
    return "MC"


def parse_ban_file(filepath):
    """Parse um arquivo .ban e retorna dados do time e jogadores."""
    try:
        with open(filepath, 'rb') as f:
            obj = javaobj.load(f)
    except Exception as e:
        print(f"  ERRO ao parsear {filepath}: {e}")
        return None, []
    
    team = {
        'name': str(getattr(obj, 'e', '') or ''),
        'stadium': str(getattr(obj, 'f', '') or ''),
        'capacity': int(getattr(obj, 'g', 0) or 0),
        'coach': str(getattr(obj, 'h', '') or ''),
        'cor1': str(getattr(obj, 'cor1', '') or ''),
        'cor2': str(getattr(obj, 'cor2', '') or ''),
        'budget': int(getattr(obj, 'a', 0) or 0),
        'nivel': int(getattr(obj, 'n', 0) or 0),
    }
    
    players = []
    # First pass: count players per group
    raw_players = []
    group_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    for p in (getattr(obj, 'l', []) or []):
        pos_group_raw = getattr(p, 'e', None)
        pos_group = int(pos_group_raw) if pos_group_raw is not None else 3
        group_counts[pos_group] = group_counts.get(pos_group, 0) + 1
        raw_players.append((p, pos_group))
    
    group_idx = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    
    for p, pos_group in raw_players:
        pos_mask = int(getattr(p, 'c', 0) or 0)
        age_raw = getattr(p, 'd', None)
        age = int(age_raw) if age_raw is not None else 25
        h_raw = getattr(p, 'h', None)
        h = int(h_raw) if h_raw is not None else 5
        g_raw = getattr(p, 'g', None)
        g = int(g_raw) if g_raw is not None else 5
        
        idx = group_idx.get(pos_group, 0)
        total = group_counts.get(pos_group, 1)
        group_idx[pos_group] = idx + 1
        
        pos = map_position(pos_group, pos_mask, idx, total, h, g)
        overall = calc_overall(h, g, pos_group, age)
        
        players.append({
            'nome': str(getattr(p, 'a', '') or ''),
            'pos': pos,
            'idade': age,
            'base': overall,
        })
    
    return team, players


def parse_all_br_teams():
    """Parsea todos os times brasileiros das séries A e B."""
    # Carregar mapeamento de file_keys
    teams_json_path = os.path.join(SEEDS_DIR, "teams_br.json")
    with open(teams_json_path, 'r', encoding='utf-8') as f:
        teams_data = json.load(f)
    
    all_players = {}
    
    for div in ['serie_a', 'serie_b']:
        for team_info in teams_data[div]:
            file_key = team_info.get('file_key', '')
            team_name = team_info['nome']
            ban_path = os.path.join(TEAMS_DIR, file_key + '.ban')
            
            if not os.path.exists(ban_path):
                print(f"  AVISO: {ban_path} não encontrado para {team_name}")
                continue
            
            team, players = parse_ban_file(ban_path)
            if team and players:
                all_players[team_name] = players
                print(f"  {team_name}: {len(players)} jogadores parseados")
                
                # Atualizar dados do time com info do BAN
                if team['stadium']:
                    team_info['estadio_nome'] = team['stadium']
                if team['capacity']:
                    team_info['estadio_cap'] = team['capacity']
    
    # Salvar players atualizado
    players_path = os.path.join(SEEDS_DIR, "players_br.json")
    with open(players_path, 'w', encoding='utf-8') as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)
    print(f"\nSalvo {len(all_players)} times em {players_path}")
    
    # Salvar teams atualizado
    with open(teams_json_path, 'w', encoding='utf-8') as f:
        json.dump(teams_data, f, ensure_ascii=False, indent=2)
    print(f"Atualizado {teams_json_path}")
    
    return all_players


if __name__ == "__main__":
    print("=== BAN Parser — Extraindo dados dos times brasileiros ===\n")
    parse_all_br_teams()
    print("\nConcluído!")
