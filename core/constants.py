# -*- coding: utf-8 -*-
"""
Constantes de domínio do jogo — não-configuráveis.
Tabelas de referência, pesos e mapeamentos.
"""
from __future__ import annotations

# ── Pesos de overall por posição ──────────────────────────────
# (técnico, físico, mental, goleiro)
OVERALL_WEIGHTS = {
    "GOL": (0.10, 0.20, 0.20, 0.50),
    "DEFAULT": (0.40, 0.30, 0.30, 0.00),
}

# ── Posições requeridas por formação ──────────────────────────
FORMACAO_POSICOES: dict[str, dict[str, int]] = {
    "4-4-2":   {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "MC": 2, "ME": 1, "MD": 1, "CA": 2},
    "4-3-3":   {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 1, "MC": 2, "PE": 1, "PD": 1, "CA": 1},
    "4-2-3-1": {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 2, "MEI": 1, "PE": 1, "PD": 1, "CA": 1},
    "4-5-1":   {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 1, "MC": 2, "ME": 1, "MD": 1, "CA": 1},
    "3-5-2":   {"GOL": 1, "ZAG": 3, "VOL": 1, "MC": 2, "ME": 1, "MD": 1, "CA": 2},
    "3-4-3":   {"GOL": 1, "ZAG": 3, "MC": 2, "ME": 1, "MD": 1, "PE": 1, "PD": 1, "CA": 1},
    "4-1-4-1": {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 1, "MC": 2, "ME": 1, "MD": 1, "CA": 1},
    "5-3-2":   {"GOL": 1, "ZAG": 3, "LD": 1, "LE": 1, "VOL": 1, "MC": 2, "CA": 2},
    "4-3-2-1": {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 1, "MC": 2, "MEI": 1, "SA": 1, "CA": 1},
    "4-2-2-2": {"GOL": 1, "ZAG": 2, "LD": 1, "LE": 1, "VOL": 2, "MEI": 2, "CA": 2},
}

# ── Ordem visual das posições (para exibição) ────────────────
POSICAO_ORDEM = {
    "GOL": 0, "ZAG": 1, "LD": 2, "LE": 3, "VOL": 4,
    "MC": 5, "ME": 6, "MD": 7, "MEI": 8, "PE": 9, "PD": 10,
    "SA": 11, "CA": 12,
}

# ── Pesos de finalização por posição ─────────────────────────
PESO_FINALIZACAO = {
    "CA": 5.0, "SA": 4.0, "PE": 3.0, "PD": 3.0, "MEI": 3.0,
    "MC": 1.5, "ME": 1.5, "MD": 1.5, "VOL": 0.5,
    "LD": 0.4, "LE": 0.4, "ZAG": 0.3, "GOL": 0.05,
}

# ── Setores do campo ─────────────────────────────────────────
SETOR_POSICOES = {
    "ataque": {"CA", "SA", "PE", "PD", "MEI"},
    "meio":   {"MC", "ME", "MD", "VOL", "MEI"},
    "defesa": {"ZAG", "LD", "LE", "VOL"},
    "goleiro": {"GOL"},
}

# ── Estilo de jogo → multiplicador de finalizações ───────────
ESTILO_MULT_FINALIZACAO = {
    "Muito Defensivo": 0.6,
    "Defensivo": 0.8,
    "Equilibrado": 1.0,
    "Ofensivo": 1.25,
    "Muito Ofensivo": 1.5,
}

# ── Bonificação de atributo por posição na geração ────────────
# Cada posição tem bônus/penalidades para grupos de atributos
# Formato: {posição: {grupo: {atributo: bonus}}}
# Definido em seed_loader para não poluir este arquivo.

# ── Elenco padrão por posição (para geração) ─────────────────
ELENCO_MODELO = [
    ("GOL", 3), ("ZAG", 4), ("LD", 2), ("LE", 2),
    ("VOL", 3), ("MC", 2), ("MEI", 2), ("PE", 2),
    ("PD", 2), ("CA", 3), ("SA", 1),
]

# ── Fantasy — pontuação padrão ────────────────────────────────
FANTASY_PONTOS = {
    "gol_goleiro": 18.0,
    "gol_defensor": 12.0,
    "gol_meia": 9.0,
    "gol_atacante": 8.0,
    "assistencia": 5.0,
    "desarme_certo": 1.2,
    "defesa_dificil": 3.0,
    "defesa_penalti": 7.0,
    "sem_gol_goleiro": 5.0,
    "sem_gol_defensor": 3.0,
    "gol_sofrido_goleiro": -2.0,
    "gol_sofrido_defensor": -1.0,
    "cartao_amarelo": -2.0,
    "cartao_vermelho": -5.0,
    "penalti_perdido": -4.0,
    "falta_cometida": -0.5,
    "falta_sofrida": 0.5,
    "finalizacao_gol": 1.2,
    "passe_decisivo": 0.8,
    "minutos_jogados_45": 1.0,
    "minutos_jogados_90": 2.0,
}
