# -*- coding: utf-8 -*-
"""
ULTRAFOOT — Configuração Global
Todas as constantes configuráveis do jogo centralizadas.
"""
import os
import sys

# ── Caminhos ──────────────────────────────────────────────────
# Assets (seeds, teams, sons, etc.) live inside the bundle
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    # Persistent data goes next to the executable, not inside MEIPASS
    _APP_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _APP_DIR = BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "data")
SEEDS_DIR = os.path.join(DATA_DIR, "seeds")

# Saves and logs go to Documents/Ultrafoot/ so they survive updates
_DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Ultrafoot")
SAVES_DIR = os.path.join(_DOCS_DIR, "saves")
LOGS_DIR = os.path.join(_DOCS_DIR, "logs")

# Migrate saves from old exe-relative location to Documents
_OLD_SAVES = os.path.join(_APP_DIR, "saves")
if os.path.isdir(_OLD_SAVES) and _OLD_SAVES != SAVES_DIR:
    import shutil as _shutil
    os.makedirs(SAVES_DIR, exist_ok=True)
    for _fn in os.listdir(_OLD_SAVES):
        _src = os.path.join(_OLD_SAVES, _fn)
        _dst = os.path.join(SAVES_DIR, _fn)
        if os.path.isfile(_src) and not os.path.exists(_dst):
            _shutil.copy2(_src, _dst)
        elif os.path.isdir(_src) and not os.path.exists(_dst):
            _shutil.copytree(_src, _dst)

APP_DIR = _APP_DIR
RUNTIME_DIR = _APP_DIR

# ── Jogo ──────────────────────────────────────────────────────
GAME_VERSION = "BETA"
GAME_TITLE = "Ultrafoot 26"
GAME_PUBLISHER = "Ultrafoot Studios"
BUILD_CHANNEL = "release"
TEMPORADA_INICIAL = 2026
SEMANAS_POR_TEMPORADA = 56

# ── Simulação ─────────────────────────────────────────────────
SIM_CHANCE_FINALIZACAO_BASE = 0.028
SIM_CHANCE_FALTA = 0.040
SIM_CHANCE_ESCANTEIO = 0.030
SIM_CHANCE_IMPEDIMENTO = 0.012
SIM_CHANCE_LESAO_JOGO = 0.003
SIM_VANTAGEM_CASA = 1.08

# ── Evolução ──────────────────────────────────────────────────
EVO_FATOR_JOVEM = 1.5       # < 23 anos
EVO_FATOR_PRIME = 1.0       # 23-28
EVO_FATOR_VETERANO = 0.3    # 29-32
EVO_FATOR_DECLINIO = -0.2   # > 32
EVO_CHANCE_EVOLUCAO = 0.30
EVO_CHANCE_DECLINIO = 0.15
IDADE_APOSENTADORIA = 38
CHANCE_APOSENTADORIA = 0.5

# ── Treinamento ───────────────────────────────────────────────
TREINO_RISCO = {"LEVE": 0.01, "NORMAL": 0.03, "INTENSO": 0.06, "MUITO_INTENSO": 0.10}
TREINO_FATOR = {"LEVE": 0.5, "NORMAL": 1.0, "INTENSO": 1.5, "MUITO_INTENSO": 2.0}

# ── Transferências ────────────────────────────────────────────
TRANSFER_SCORE_ACEITE = 1.2
TRANSFER_SCORE_CHANCE = 0.9
TRANSFER_SCORE_BAIXA = 0.7
TRANSFER_CHANCE_IA = 0.35
JOGADORES_LIVRES_INICIAL = 50

# ── Finanças ──────────────────────────────────────────────────
SALARIO_MINIMO_JOGADOR = 5000
SALARIO_MINIMO_STAFF = 10000

# ── UI ────────────────────────────────────────────────────────
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 780
SIDEBAR_WIDTH = 220
FONT_FAMILY = "Segoe UI"

# ── Fantasy ───────────────────────────────────────────────────
FANTASY_ORCAMENTO_INICIAL = 100_000_000
FANTASY_MAX_JOGADORES = 15
FANTASY_TITULARES = 11
FANTASY_CAPITAO_MULTIPLIER = 1.5
