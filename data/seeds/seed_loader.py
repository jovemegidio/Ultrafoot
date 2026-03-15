# -*- coding: utf-8 -*-
"""
Seed Loader — carrega dados do JSON e gera elencos, staff e atributos.
Funções públicas exportadas (usadas por engines e managers):
    - gerar_atributos_jogador(jogador, base)
    - criar_times_serie_a() -> List[Time]
    - criar_times_serie_b() -> List[Time]
    - criar_times_serie_c() -> List[Time]
    - criar_times_serie_d() -> List[Time]
    - criar_times_sem_divisao() -> List[Time]
"""
from __future__ import annotations

import os
import random
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

try:
    import orjson as _json_mod
    def _json_load(f):
        return _json_mod.loads(f.read())
    _JSON_READ_MODE = "rb"
except ImportError:
    import json as _json_mod
    def _json_load(f):
        data = f.read()
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return _json_mod.loads(data)
    _JSON_READ_MODE = "rb"

from core.enums import (
    Posicao, PePreferido, TipoContrato, TipoStaff,
    FormacaoTatica, TraitJogador,
)
from core.models import (
    Time, Jogador, Estadio, Financas, BaseJuvenil,
    Tatica, ContratoJogador, StaffMembro, Treinamento,
    AtributosTecnicos, AtributosFisicos, AtributosMentais, AtributosGoleiro,
)
from core.constants import ELENCO_MODELO, FORMACAO_POSICOES
from utils.name_generator import gerar_nome_brasileiro


# ══════════════════════════════════════════════════════════════
#  CAMINHO DOS SEEDS
# ══════════════════════════════════════════════════════════════

_SEEDS_DIR = os.path.dirname(os.path.abspath(__file__))
_TEAMS_FILE = os.path.join(_SEEDS_DIR, "teams_br.json")
_PLAYERS_FILE = os.path.join(_SEEDS_DIR, "players_br.json")
_ALL_TEAMS_FILE = os.path.join(_SEEDS_DIR, "all_teams.json")
_TEAM_METADATA_OVERRIDES_FILE = os.path.join(_SEEDS_DIR, "team_metadata_overrides.json")
_DIVISION_OVERRIDES_FILE = os.path.join(_SEEDS_DIR, "division_overrides_2026.json")
_PLAYER_PHOTO_OVERRIDES_FILE = os.path.join(_SEEDS_DIR, "player_photo_overrides.json")

# ── Cache global dos JSONs (evita releitura de disco) ─────────
_CACHE: dict[str, object] = {}


_STOPWORDS_LOOKUP = {
    "futebol", "clube", "esporte", "esportiva", "sociedade", "associacao",
    "anonima", "saf", "ltda", "sa", "do", "da", "de", "e", "fc", "ec", "ac",
    "sc", "club", "sports", "sociedadeanonima", "brasil", "safsociedadeanonima",
}

_COUNTRY_NAMES = {
    "BRA": "Brasil",
    "ARG": "Argentina",
    "BOL": "Bolivia",
    "CHI": "Chile",
    "COL": "Colombia",
    "EQU": "Equador",
    "PAR": "Paraguai",
    "PER": "Peru",
    "URU": "Uruguai",
    "VEN": "Venezuela",
    "ING": "Inglaterra",
    "ESP": "Espanha",
    "ITA": "Italia",
    "ALE": "Alemanha",
    "FRA": "Franca",
    "POR": "Portugal",
    "HOL": "Holanda",
    "BEL": "Belgica",
    "TUR": "Turquia",
    "RUS": "Russia",
    "ESC": "Escocia",
    "SUI": "Suica",
    "AUT": "Austria",
    "GRE": "Grecia",
    "MEX": "Mexico",
    "EUA": "Estados Unidos",
}


def _normalizar_lookup(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(
        parte for parte in texto.split()
        if parte and parte not in _STOPWORDS_LOOKUP
    )


def _normalizar_lookup_rigido(valor: Any) -> str:
    return _normalizar_lookup(valor).replace(" ", "")


def _sigla_clube(nome: str) -> str:
    partes = [
        p for p in re.split(r"[^A-Za-zÀ-ÿ0-9]+", nome)
        if p and len(p) > 1
    ]
    if len(partes) >= 2:
        return (partes[0][:2] + partes[1][:1]).upper()[:3]
    if partes:
        return partes[0][:3].upper()
    return "CLB"


def _normalizar_nacionalidade(valor: Any, fallback_estado: str = "") -> str:
    texto = str(valor or "").strip()
    if not texto:
        texto = str(fallback_estado or "").strip()
    if not texto:
        return "Brasil"
    codigo = texto.upper()
    if len(codigo) == 2 and codigo.isalpha():
        return "Brasil"
    if codigo in _COUNTRY_NAMES:
        return _COUNTRY_NAMES[codigo]
    return texto


def _cor_deterministica(nome: str, fallback: str) -> str:
    base = sum((i + 1) * ord(c) for i, c in enumerate(nome))
    paleta = [
        "#111827", "#1d4ed8", "#0f766e", "#7c3aed", "#b91c1c",
        "#14532d", "#92400e", "#1e3a8a", "#4c1d95", "#0f172a",
    ]
    return paleta[base % len(paleta)] if nome else fallback


def _carregar_all_teams_index() -> dict[str, dict[str, Any]]:
    if "all_teams_index" not in _CACHE:
        index: dict[str, dict[str, Any]] = {}
        if os.path.exists(_ALL_TEAMS_FILE):
            with open(_ALL_TEAMS_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            if isinstance(raw, dict):
                for teams in raw.values():
                    if not isinstance(teams, list):
                        continue
                    for item in teams:
                        if isinstance(item, dict) and item.get("file_key"):
                            index[item["file_key"]] = item
        _CACHE["all_teams_index"] = index
    return _CACHE["all_teams_index"]


def _carregar_team_metadata_overrides() -> dict[str, dict[str, Any]]:
    if "team_metadata_overrides" not in _CACHE:
        if not os.path.exists(_TEAM_METADATA_OVERRIDES_FILE):
            _CACHE["team_metadata_overrides"] = {}
        else:
            with open(_TEAM_METADATA_OVERRIDES_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            _CACHE["team_metadata_overrides"] = raw if isinstance(raw, dict) else {}
    return _CACHE["team_metadata_overrides"]


def _carregar_player_photo_overrides() -> dict[str, dict[str, str]]:
    if "player_photo_overrides" not in _CACHE:
        if not os.path.exists(_PLAYER_PHOTO_OVERRIDES_FILE):
            _CACHE["player_photo_overrides"] = {}
        else:
            with open(_PLAYER_PHOTO_OVERRIDES_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            _CACHE["player_photo_overrides"] = raw if isinstance(raw, dict) else {}
    return _CACHE["player_photo_overrides"]


def _carregar_division_overrides() -> dict[str, list]:
    if "division_overrides" not in _CACHE:
        if not os.path.exists(_DIVISION_OVERRIDES_FILE):
            _CACHE["division_overrides"] = {}
        else:
            with open(_DIVISION_OVERRIDES_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            _CACHE["division_overrides"] = raw if isinstance(raw, dict) else {}
    return _CACHE["division_overrides"]


def _carregar_all_teams_bra() -> list[dict[str, Any]]:
    if "all_teams_bra" not in _CACHE:
        if not os.path.exists(_ALL_TEAMS_FILE):
            _CACHE["all_teams_bra"] = []
        else:
            with open(_ALL_TEAMS_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            lista = raw.get("BRA", []) if isinstance(raw, dict) else []
            _CACHE["all_teams_bra"] = [item for item in lista if isinstance(item, dict)]
    return _CACHE["all_teams_bra"]


def _estadio_nome_valido(nome: Any) -> bool:
    valor = re.sub(r"\s+", " ", str(nome or "")).strip()
    if not valor or len(valor) <= 2:
        return False
    if valor.isdigit():
        return False
    if re.fullmatch(r"[A-Z0-9]{2,5}", valor):
        return False
    return True


def _cidade_valida(nome: Any) -> bool:
    valor = re.sub(r"\s+", " ", str(nome or "")).strip()
    if not valor or len(valor) <= 2:
        return False
    if re.fullmatch(r"[A-Z]{2,5}", valor):
        return False
    return True


def _materializar_time_do_all_teams(
    referencia: dict[str, Any],
    divisao: int,
    override: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    override = override or {}
    nome = str(referencia.get("nome") or override.get("nome") or "Clube")
    prestigio = {1: 82, 2: 72, 3: 62, 4: 54}.get(divisao, 48)
    torcida = max(35_000, prestigio * 55_000)
    saldo = max(5_000_000, prestigio * 900_000)
    base = {
        "nome": nome,
        "curto": _sigla_clube(nome),
        "cidade": "",
        "estado": str(override.get("estado") or "BR"),
        "cor1": referencia.get("cor1") or _cor_deterministica(nome, "#1d4ed8"),
        "cor2": referencia.get("cor2") or "#ffffff",
        "prestigio": int(referencia.get("prestigio_bf") or prestigio),
        "torcida": int(torcida),
        "estadio_cap": int(referencia.get("estadio_cap") or max(4000, prestigio * 450)),
        "saldo": int(saldo),
        "file_key": referencia.get("file_key") or _normalizar_lookup_rigido(nome),
        "estadio_nome": referencia.get("estadio") or f"Estádio do {nome}",
        "patrocinador": "",
    }
    if _cidade_valida(override.get("cidade")):
        base["cidade"] = override["cidade"]
    elif _cidade_valida(referencia.get("cidade")):
        base["cidade"] = str(referencia["cidade"])
    if override:
        for chave, valor in override.items():
            if chave == "nome":
                continue
            if valor not in (None, ""):
                base[chave] = valor
    return base


def _sintetizar_time_override(item: Any, divisao: int) -> dict[str, Any]:
    if isinstance(item, dict):
        nome = str(item.get("nome") or "Clube")
        estado = str(item.get("estado") or "BR")
        cidade = str(item.get("cidade") or "")
        estadio = str(item.get("estadio_nome") or f"Estádio do {nome}")
    else:
        nome = str(item)
        estado = "BR"
        cidade = ""
        estadio = f"Estádio do {nome}"
    prestigio = {1: 82, 2: 72, 3: 62, 4: 54}.get(divisao, 48)
    return {
        "nome": nome,
        "curto": _sigla_clube(nome),
        "cidade": cidade,
        "estado": estado,
        "cor1": _cor_deterministica(nome, "#1d4ed8"),
        "cor2": "#ffffff",
        "prestigio": prestigio,
        "torcida": max(25_000, prestigio * 50_000),
        "estadio_cap": max(4000, prestigio * 400),
        "saldo": max(4_000_000, prestigio * 750_000),
        "file_key": _normalizar_lookup_rigido(nome),
        "estadio_nome": estadio,
        "patrocinador": "",
    }


def _construir_pool_times_br(raw: dict[str, Any]) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    for lista in raw.values():
        if isinstance(lista, list):
            pool.extend(item for item in lista if isinstance(item, dict))
    for referencia in _carregar_all_teams_bra():
        if referencia.get("pais") == "BRA":
            pool.append(_materializar_time_do_all_teams(referencia, divisao=4))
    return pool


def _resolver_override_time(
    item: Any,
    divisao: int,
    pool_fk: dict[str, dict[str, Any]],
    pool_nome: dict[str, dict[str, Any]],
    all_teams_fk: dict[str, dict[str, Any]],
    all_teams_nome: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    override = item if isinstance(item, dict) else {}
    file_key = str(override.get("file_key") or "")
    nome = str(override.get("nome") or item or "")

    candidato = None
    if file_key and file_key in pool_fk:
        candidato = dict(pool_fk[file_key])
    elif file_key and file_key in all_teams_fk:
        candidato = _materializar_time_do_all_teams(all_teams_fk[file_key], divisao, override)
    else:
        nome_norm = _normalizar_lookup(nome)
        nome_rigido = _normalizar_lookup_rigido(nome)
        candidato = (
            pool_nome.get(nome_norm)
            or pool_nome.get(nome_rigido)
            or all_teams_nome.get(nome_norm)
            or all_teams_nome.get(nome_rigido)
        )
        if candidato:
            candidato = dict(candidato)
            if candidato.get("pais") == "BRA" or candidato.get("jogadores"):
                candidato = _materializar_time_do_all_teams(candidato, divisao, override)

    if not candidato:
        candidato = _sintetizar_time_override(item, divisao)

    for chave, valor in override.items():
        if valor not in (None, ""):
            candidato[chave] = valor
    return candidato


def _aplicar_division_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    overrides = _carregar_division_overrides()
    if not overrides:
        return raw

    pool = _construir_pool_times_br(raw)
    pool_fk: dict[str, dict[str, Any]] = {}
    pool_nome: dict[str, dict[str, Any]] = {}
    for item in pool:
        if item.get("file_key"):
            pool_fk[item["file_key"]] = item
        pool_nome.setdefault(_normalizar_lookup(item.get("nome")), item)
        pool_nome.setdefault(_normalizar_lookup_rigido(item.get("nome")), item)

    all_teams_fk: dict[str, dict[str, Any]] = {}
    all_teams_nome: dict[str, dict[str, Any]] = {}
    for item in _carregar_all_teams_bra():
        fk = str(item.get("file_key") or "")
        if fk:
            all_teams_fk[fk] = item
        all_teams_nome.setdefault(_normalizar_lookup(item.get("nome")), item)
        all_teams_nome.setdefault(_normalizar_lookup_rigido(item.get("nome")), item)

    resultado = {
        chave: list(valor) if isinstance(valor, list) else valor
        for chave, valor in raw.items()
    }
    usados_fk: set[str] = set()
    usados_nome: set[str] = set()

    divisao_map = {
        "serie_a": 1,
        "serie_b": 2,
        "serie_c": 3,
        "serie_d": 4,
    }
    for chave, divisao in divisao_map.items():
        alvo = overrides.get(chave)
        if not isinstance(alvo, list) or not alvo:
            continue
        lista: list[dict[str, Any]] = []
        for item in alvo:
            time = _resolver_override_time(
                item, divisao, pool_fk, pool_nome, all_teams_fk, all_teams_nome,
            )
            fk = str(time.get("file_key") or "")
            nome_norm = _normalizar_lookup(time.get("nome"))
            if (fk and fk in usados_fk) or (nome_norm and nome_norm in usados_nome):
                continue
            lista.append(time)
            if fk:
                usados_fk.add(fk)
            if nome_norm:
                usados_nome.add(nome_norm)
        resultado[chave] = lista

    sem_divisao: list[dict[str, Any]] = []
    for time in _construir_pool_times_br(raw):
        fk = str(time.get("file_key") or "")
        nome_norm = _normalizar_lookup(time.get("nome"))
        if (fk and fk in usados_fk) or (nome_norm and nome_norm in usados_nome):
            continue
        if nome_norm and nome_norm not in {_normalizar_lookup(t.get("nome")) for t in sem_divisao}:
            sem_divisao.append(time)
    resultado["sem_divisao"] = sem_divisao
    return resultado


def _normalizar_dados_time(dados_time: dict[str, Any]) -> dict[str, Any]:
    time = dict(dados_time)
    file_key = time.get("file_key", "")
    referencia = _carregar_all_teams_index().get(file_key, {})
    override = _carregar_team_metadata_overrides().get(file_key, {})
    if isinstance(override, dict):
        for chave, valor in override.items():
            if valor not in (None, ""):
                time[chave] = valor

    if not _cidade_valida(time.get("cidade")):
        time["cidade"] = str(time.get("cidade") or "")

    if (not time.get("estadio_cap")) and referencia.get("estadio_cap"):
        time["estadio_cap"] = referencia["estadio_cap"]

    estadio_nome = time.get("estadio_nome")
    if not _estadio_nome_valido(estadio_nome):
        estadio_ref = referencia.get("estadio")
        if _estadio_nome_valido(estadio_ref):
            time["estadio_nome"] = estadio_ref
        elif time.get("cidade"):
            time["estadio_nome"] = f"Estádio Municipal de {time['cidade']}"
        else:
            time["estadio_nome"] = f"Estádio do {time.get('nome', 'Clube')}"

    patrocinador = str(time.get("patrocinador") or "").strip()
    time["patrocinador"] = patrocinador
    return time


def _normalizar_times_br(raw: dict[str, Any]) -> dict[str, Any]:
    dados: dict[str, Any] = {}
    for serie, lista in raw.items():
        if isinstance(lista, list):
            dados[serie] = [_normalizar_dados_time(item) for item in lista]
        else:
            dados[serie] = lista
    return dados


def _normalizar_times_eu(raw: dict[str, Any]) -> dict[str, Any]:
    dados: dict[str, Any] = {}
    for pais, info in raw.items():
        if not isinstance(info, dict):
            dados[pais] = info
            continue
        info_norm = dict(info)
        divisoes_norm = {}
        for div_key, lista in info.get("divisoes", {}).items():
            divisoes_norm[div_key] = [_normalizar_dados_time(item) for item in lista]
        info_norm["divisoes"] = divisoes_norm
        dados[pais] = info_norm
    return dados


def _carregar_json_times() -> dict:
    if "teams_br" not in _CACHE:
        with open(_TEAMS_FILE, _JSON_READ_MODE) as f:
            bruto = _json_load(f)
        bruto = _aplicar_division_overrides(bruto if isinstance(bruto, dict) else {})
        _CACHE["teams_br"] = _normalizar_times_br(bruto)
    return _CACHE["teams_br"]


def _aplicar_fotos_jogadores(
    roster: list[dict[str, Any]],
    nome_time: str,
) -> list[dict[str, Any]]:
    fotos = _carregar_player_photo_overrides()
    por_time = fotos.get(nome_time, {}) if isinstance(fotos.get(nome_time), dict) else {}
    globais = fotos.get("__all__", {}) if isinstance(fotos.get("__all__"), dict) else {}
    resultado: list[dict[str, Any]] = []
    for jogador in roster:
        item = dict(jogador)
        foto = por_time.get(item.get("nome")) or globais.get(item.get("nome"))
        if foto:
            item["foto"] = foto
        resultado.append(item)
    return resultado


def _mesclar_jogadores_brasileiros(raw: dict[str, Any]) -> dict[str, Any]:
    mesclado: dict[str, Any] = {}
    for nome_time, roster in raw.items():
        if isinstance(roster, list):
            mesclado[nome_time] = _aplicar_fotos_jogadores(roster, nome_time)

    for referencia in _carregar_all_teams_bra():
        nome_time = str(referencia.get("nome") or "")
        roster_ref = referencia.get("jogadores") or []
        roster_atual = mesclado.get(nome_time)
        if not roster_atual and isinstance(roster_ref, list) and roster_ref:
            mesclado[nome_time] = _aplicar_fotos_jogadores(roster_ref, nome_time)
        elif isinstance(roster_atual, list):
            mesclado[nome_time] = _aplicar_fotos_jogadores(roster_atual, nome_time)

    return mesclado


def _carregar_json_jogadores() -> dict:
    if "players_br" not in _CACHE:
        if not os.path.exists(_PLAYERS_FILE):
            _CACHE["players_br"] = {}
        else:
            with open(_PLAYERS_FILE, _JSON_READ_MODE) as f:
                raw = _json_load(f)
            _CACHE["players_br"] = _mesclar_jogadores_brasileiros(raw if isinstance(raw, dict) else {})
    return _CACHE["players_br"]


def limpar_cache_seeds() -> None:
    """Limpa o cache de seeds (útil após edições no editor)."""
    _CACHE.clear()


# ══════════════════════════════════════════════════════════════
#  GERAÇÃO DE ATRIBUTOS
# ══════════════════════════════════════════════════════════════

# Bônus por posição: (grupo, atributo, bonus_min, bonus_max)
_BONUS_POSICAO: dict[str, list[tuple[str, str, int, int]]] = {
    "GOL": [
        ("goleiro", "reflexos", 5, 15), ("goleiro", "posicionamento_gol", 5, 15),
        ("goleiro", "jogo_aereo", 5, 10), ("goleiro", "defesa_1v1", 5, 10),
        ("goleiro", "elasticidade", 3, 10), ("goleiro", "comando_area", 3, 10),
        ("fisicos", "salto", 3, 8),
    ],
    "ZAG": [
        ("tecnicos", "desarme", 5, 15), ("tecnicos", "marcacao", 5, 15),
        ("tecnicos", "cabeceio", 5, 10), ("fisicos", "forca", 3, 10),
        ("mentais", "posicionamento", 5, 10), ("mentais", "bravura", 3, 10),
    ],
    "LD": [
        ("fisicos", "velocidade", 5, 12), ("fisicos", "resistencia", 3, 10),
        ("tecnicos", "cruzamento", 5, 10), ("tecnicos", "marcacao", 3, 8),
    ],
    "LE": [
        ("fisicos", "velocidade", 5, 12), ("fisicos", "resistencia", 3, 10),
        ("tecnicos", "cruzamento", 5, 10), ("tecnicos", "marcacao", 3, 8),
    ],
    "VOL": [
        ("tecnicos", "desarme", 5, 12), ("tecnicos", "marcacao", 5, 12),
        ("tecnicos", "passe_curto", 3, 8), ("mentais", "posicionamento", 3, 10),
        ("fisicos", "resistencia", 3, 8), ("fisicos", "forca", 3, 8),
    ],
    "MC": [
        ("tecnicos", "passe_curto", 5, 12), ("tecnicos", "passe_longo", 3, 10),
        ("mentais", "visao_jogo", 5, 10), ("tecnicos", "controle_bola", 3, 8),
        ("fisicos", "resistencia", 3, 8),
    ],
    "ME": [
        ("fisicos", "velocidade", 3, 10), ("tecnicos", "cruzamento", 5, 10),
        ("tecnicos", "drible", 3, 8), ("fisicos", "resistencia", 3, 8),
    ],
    "MD": [
        ("fisicos", "velocidade", 3, 10), ("tecnicos", "cruzamento", 5, 10),
        ("tecnicos", "drible", 3, 8), ("fisicos", "resistencia", 3, 8),
    ],
    "MEI": [
        ("tecnicos", "passe_curto", 5, 12), ("mentais", "visao_jogo", 5, 12),
        ("mentais", "criatividade", 5, 12), ("tecnicos", "drible", 3, 10),
        ("tecnicos", "finalizacao", 3, 8),
    ],
    "PE": [
        ("fisicos", "velocidade", 5, 15), ("fisicos", "aceleracao", 5, 12),
        ("tecnicos", "drible", 5, 12), ("tecnicos", "finalizacao", 3, 8),
        ("tecnicos", "cruzamento", 3, 8),
    ],
    "PD": [
        ("fisicos", "velocidade", 5, 15), ("fisicos", "aceleracao", 5, 12),
        ("tecnicos", "drible", 5, 12), ("tecnicos", "finalizacao", 3, 8),
        ("tecnicos", "cruzamento", 3, 8),
    ],
    "CA": [
        ("tecnicos", "finalizacao", 5, 15), ("tecnicos", "cabeceio", 5, 10),
        ("mentais", "compostura", 3, 10), ("fisicos", "forca", 3, 8),
        ("tecnicos", "controle_bola", 3, 8),
    ],
    "SA": [
        ("tecnicos", "finalizacao", 5, 12), ("tecnicos", "drible", 3, 10),
        ("mentais", "visao_jogo", 3, 8), ("tecnicos", "passe_curto", 3, 8),
    ],
}

# Traits possíveis por posição
_TRAITS_POSICAO: dict[str, list[TraitJogador]] = {
    "GOL": [TraitJogador.MURALHA, TraitJogador.PEGADOR_PENALTI, TraitJogador.LIDERANCA_NATO],
    "ZAG": [TraitJogador.MURALHA, TraitJogador.RAINHA, TraitJogador.LIDERANCA_NATO, TraitJogador.CLUTCH],
    "LD": [TraitJogador.VELOCISTA, TraitJogador.MOTOR, TraitJogador.ASSISTENTE],
    "LE": [TraitJogador.VELOCISTA, TraitJogador.MOTOR, TraitJogador.ASSISTENTE],
    "VOL": [TraitJogador.MOTOR, TraitJogador.MURALHA, TraitJogador.LIDERANCA_NATO],
    "MC": [TraitJogador.CAMISA_10, TraitJogador.MOTOR, TraitJogador.ASSISTENTE],
    "ME": [TraitJogador.VELOCISTA, TraitJogador.ASSISTENTE, TraitJogador.DRIBLE_MAGICO],
    "MD": [TraitJogador.VELOCISTA, TraitJogador.ASSISTENTE, TraitJogador.DRIBLE_MAGICO],
    "MEI": [TraitJogador.CAMISA_10, TraitJogador.ASSISTENTE, TraitJogador.CLUTCH, TraitJogador.DRIBLE_MAGICO],
    "PE": [TraitJogador.VELOCISTA, TraitJogador.DRIBLE_MAGICO, TraitJogador.ARTILHEIRO],
    "PD": [TraitJogador.VELOCISTA, TraitJogador.DRIBLE_MAGICO, TraitJogador.ARTILHEIRO],
    "CA": [TraitJogador.ARTILHEIRO, TraitJogador.RAINHA, TraitJogador.CLUTCH, TraitJogador.LIDERANCA_NATO],
    "SA": [TraitJogador.ARTILHEIRO, TraitJogador.DRIBLE_MAGICO, TraitJogador.ASSISTENTE, TraitJogador.CLUTCH],
}


def gerar_atributos_jogador(jogador: Jogador, base: int) -> None:
    """Preenche os atributos do jogador a partir de um valor base.

    - Valores base são distribuídos com variação aleatória.
    - Bônus por posição são aplicados.
    - Traits são sorteados conforme posição e overall.
    """
    variacao = max(3, base // 6)

    # Bulk random generation (41 main + 9 goleiro = 50 values)
    lo = max(1, base - variacao)
    hi = min(99, base + variacao)
    r = random.choices(range(lo, hi + 1), k=41)

    # Técnicos (13)
    jogador.tecnicos = AtributosTecnicos(
        passe_curto=r[0], passe_longo=r[1], cruzamento=r[2],
        finalizacao=r[3], chute_longa_dist=r[4], cabeceio=r[5],
        drible=r[6], controle_bola=r[7], falta=r[8], penalti=r[9],
        desarme=r[10], marcacao=r[11], lancamento=r[12],
    )

    # Físicos (7)
    jogador.fisicos = AtributosFisicos(
        velocidade=r[13], aceleracao=r[14], resistencia=r[15],
        forca=r[16], agilidade=r[17], salto=r[18], equilibrio=r[19],
    )

    # Mentais (12)
    jogador.mentais = AtributosMentais(
        visao_jogo=r[20], decisao=r[21], concentracao=r[22],
        determinacao=r[23], lideranca=r[24], trabalho_equipe=r[25],
        criatividade=r[26], compostura=r[27], agressividade=r[28],
        posicionamento=r[29], antecipacao=r[30], bravura=r[31],
    )

    # Goleiro — base mais baixo se não for goleiro
    gol_base = base if jogador.posicao == Posicao.GOL else max(1, base // 3)
    gol_var = max(2, gol_base // 6)
    glo = max(1, gol_base - gol_var)
    ghi = min(99, gol_base + gol_var)
    rg = random.choices(range(glo, ghi + 1), k=9)

    jogador.goleiro = AtributosGoleiro(
        reflexos=rg[0], posicionamento_gol=rg[1], jogo_aereo=rg[2],
        defesa_1v1=rg[3], reposicao=rg[4], jogo_com_pes=rg[5],
        punho=rg[6], elasticidade=rg[7], comando_area=rg[8],
    )

    # ── Bônus por posição ─────────────────────────────────────
    pos_nome = jogador.posicao.name
    for grupo, atributo, bmin, bmax in _BONUS_POSICAO.get(pos_nome, []):
        obj = getattr(jogador, grupo, None)
        if obj and hasattr(obj, atributo):
            atual = getattr(obj, atributo)
            setattr(obj, atributo, min(99, atual + random.randint(bmin, bmax)))

    # ── Traits ────────────────────────────────────────────────
    jogador.traits = []
    pool = _TRAITS_POSICAO.get(pos_nome, [])
    # Negativos universais
    negativos = [TraitJogador.VIDRACEIRO, TraitJogador.PANELEIRO]

    if base >= 70 and pool:
        # Jogadores bons têm mais chance de trait positivo
        if random.random() < 0.35:
            jogador.traits.append(random.choice(pool))
    elif base >= 50 and pool:
        if random.random() < 0.15:
            jogador.traits.append(random.choice(pool))

    # Chance de trait negativo
    if random.random() < 0.08:
        neg = random.choice(negativos)
        if neg not in jogador.traits:
            jogador.traits.append(neg)


# ══════════════════════════════════════════════════════════════
#  GERAÇÃO DE ELENCO
# ══════════════════════════════════════════════════════════════

_IDADES_PESOS = [2, 3, 4, 5, 6, 7, 8, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1, 1, 1]

# Mapa simplificado pos_str -> Posicao
_POS_MAP = {
    "GOL": Posicao.GOL, "ZAG": Posicao.ZAG, "LD": Posicao.LD, "LE": Posicao.LE,
    "VOL": Posicao.VOL, "MC": Posicao.MC, "ME": Posicao.ME, "MD": Posicao.MD,
    "MEI": Posicao.MEI, "PE": Posicao.PE, "PD": Posicao.PD,
    "CA": Posicao.CA, "SA": Posicao.SA,
}


def _gerar_elenco(time: Time, id_base: int, prestigio: int,
                  jogadores_reais: list[dict] | None = None) -> Tuple[List[Jogador], int]:
    """Gera elenco completo para o *time*. Usa dados reais se disponíveis."""
    jogadores: list[Jogador] = []

    if prestigio >= 85:
        base_min, base_max = 55, 80
    elif prestigio >= 70:
        base_min, base_max = 45, 70
    elif prestigio >= 55:
        base_min, base_max = 35, 60
    else:
        base_min, base_max = 25, 50

    # ── Modo dados reais ──────────────────────────────────────
    if jogadores_reais:
        camisa = 1
        for jd in jogadores_reais:
            posicao = _POS_MAP.get(jd["pos"], Posicao.MC)
            base_attr = jd.get("base", random.randint(base_min, base_max))
            idade = jd.get("idade", random.choices(range(18, 37), weights=_IDADES_PESOS, k=1)[0])

            jogador = Jogador(
                id=id_base,
                nome=jd["nome"],
                idade=idade,
                nacionalidade=_normalizar_nacionalidade(
                    jd.get("nac") or jd.get("nacionalidade"),
                    fallback_estado=time.estado,
                ),
                foto=jd.get("foto", ""),
                posicao=posicao,
                pe_preferido=random.choices(
                    [PePreferido.DIREITO, PePreferido.ESQUERDO, PePreferido.AMBIDESTRO],
                    weights=[60, 30, 10], k=1,
                )[0],
                numero_camisa=camisa,
                altura=round(random.uniform(
                    1.85 if posicao in (Posicao.GOL, Posicao.ZAG, Posicao.CA) else 1.68,
                    1.98 if posicao in (Posicao.GOL, Posicao.ZAG, Posicao.CA) else 1.88,
                ), 2),
                peso=round(random.uniform(65, 92), 1),
                potencial=min(99, base_attr + random.randint(5, 20)),
                moral=random.randint(55, 85),
                condicao_fisica=random.randint(75, 100),
                contrato=ContratoJogador(
                    tipo=TipoContrato.PROFISSIONAL,
                    salario=max(10_000, base_attr * random.randint(800, 2000)),
                    multa_rescisoria=max(500_000, base_attr * random.randint(20_000, 100_000)),
                    duracao_meses=random.choice([12, 24, 36, 48]),
                    meses_restantes=random.choice([6, 12, 18, 24, 30, 36]),
                ),
            )
            gerar_atributos_jogador(jogador, base_attr)
            jogadores.append(jogador)
            id_base += 1
            camisa += 1

        return jogadores, id_base

    # ── Modo geração aleatória (fallback) ─────────────────────
    camisa = 1
    for pos_nome, qtd in ELENCO_MODELO:
        posicao = Posicao[pos_nome]
        for j_idx in range(qtd):
            base_attr = random.randint(base_min, base_max)
            # Titular é mais forte
            if j_idx == 0:
                base_attr = min(99, base_attr + random.randint(5, 15))

            idade = random.choices(range(18, 37), weights=_IDADES_PESOS, k=1)[0]

            jogador = Jogador(
                id=id_base,
                nome=gerar_nome_brasileiro(),
                idade=idade,
                nacionalidade=_normalizar_nacionalidade(time.estado, fallback_estado="BRA"),
                posicao=posicao,
                pe_preferido=random.choices(
                    [PePreferido.DIREITO, PePreferido.ESQUERDO, PePreferido.AMBIDESTRO],
                    weights=[60, 30, 10], k=1,
                )[0],
                numero_camisa=camisa,
                altura=round(random.uniform(
                    1.85 if posicao in (Posicao.GOL, Posicao.ZAG, Posicao.CA) else 1.68,
                    1.98 if posicao in (Posicao.GOL, Posicao.ZAG, Posicao.CA) else 1.88,
                ), 2),
                peso=round(random.uniform(65, 92), 1),
                potencial=min(99, base_attr + random.randint(5, 20)),
                moral=random.randint(55, 85),
                condicao_fisica=random.randint(75, 100),
                contrato=ContratoJogador(
                    tipo=TipoContrato.PROFISSIONAL,
                    salario=max(10_000, base_attr * random.randint(800, 2000)),
                    multa_rescisoria=max(500_000, base_attr * random.randint(20_000, 100_000)),
                    duracao_meses=random.choice([12, 24, 36, 48]),
                    meses_restantes=random.choice([6, 12, 18, 24, 30, 36]),
                ),
            )
            gerar_atributos_jogador(jogador, base_attr)
            jogadores.append(jogador)
            id_base += 1
            camisa += 1

    return jogadores, id_base


# ══════════════════════════════════════════════════════════════
#  SELEÇÃO AUTOMÁTICA DE TITULARES
# ══════════════════════════════════════════════════════════════

def _selecionar_titulares_auto(time: Time) -> List[int]:
    """Seleciona 11 melhores titulares para a formação do *time*."""
    formacao_str = time.tatica.formacao.value
    nec = FORMACAO_POSICOES.get(formacao_str, FORMACAO_POSICOES["4-4-2"])

    titulares: list[int] = []
    usados: set[int] = set()

    for pos_nome, qtd in nec.items():
        posicao = Posicao[pos_nome]
        candidatos = sorted(
            [j for j in time.jogadores if j.posicao == posicao and j.id not in usados and j.pode_jogar()],
            key=lambda j: j.overall, reverse=True,
        )
        for j in candidatos[:qtd]:
            titulares.append(j.id)
            usados.add(j.id)

    # Preencher se faltam titulares
    if len(titulares) < 11:
        sobras = sorted(
            [j for j in time.jogadores if j.id not in usados and j.pode_jogar()],
            key=lambda j: j.overall, reverse=True,
        )
        for j in sobras:
            if len(titulares) >= 11:
                break
            titulares.append(j.id)
            usados.add(j.id)

    return titulares[:11]


# ══════════════════════════════════════════════════════════════
#  GERAÇÃO DE STAFF
# ══════════════════════════════════════════════════════════════

def _gerar_staff(time: Time, prestigio: int) -> List[StaffMembro]:
    """Gera staff completo do *time*."""
    staff: list[StaffMembro] = []
    id_base = time.id * 100 + 900
    hab_base = max(30, prestigio - random.randint(0, 20))

    specs = [
        (TipoStaff.TREINADOR, 38, 65, 0, (3000, 8000), ""),
        (TipoStaff.AUXILIAR, 35, 55, -10, (1000, 3000), ""),
        (TipoStaff.PREPARADOR, 30, 50, -5, (800, 2000), ""),
        (TipoStaff.TREINADOR_GOL, 35, 55, -10, (500, 1500), ""),
        (TipoStaff.SCOUT, 30, 60, -5, (500, 1500), None),
        (TipoStaff.MEDICO, 35, 55, 0, (800, 2000), ""),
    ]

    for i, (tipo, idade_min, idade_max, hab_offset, sal_range, espec) in enumerate(specs):
        hab = min(99, hab_base + hab_offset + random.randint(-5, 10))
        if espec is None:
            espec = random.choice(["Brasil", "América do Sul", "Europa"])
        staff.append(StaffMembro(
            id=id_base + i,
            nome=gerar_nome_brasileiro(),
            idade=random.randint(idade_min, idade_max),
            tipo=tipo,
            habilidade=hab,
            salario=max(10_000, hab * random.randint(*sal_range)),
            especializacao=espec,
        ))

    return staff


# ══════════════════════════════════════════════════════════════
#  CRIAÇÃO DE TIMES (API PÚBLICA)
# ══════════════════════════════════════════════════════════════

def _criar_times(dados_lista: List[dict], divisao: int,
                 jogadores_db: dict | None = None) -> List[Time]:
    """Cria lista de Time a partir dos dados JSON."""
    times: list[Time] = []
    id_jogador = divisao * 10_000

    for i, d in enumerate(dados_lista):
        prestigio = d["prestigio"]
        saldo = d["saldo"]
        capacidade = d["estadio_cap"]
        torcida = d["torcida"]

        time = Time(
            id=divisao * 100 + i,
            nome=d["nome"],
            nome_curto=d["curto"],
            cidade=d["cidade"],
            estado=d["estado"],
            cor_principal=d["cor1"],
            cor_secundaria=d["cor2"],
            divisao=divisao,
            prestigio=prestigio,
            torcida_tamanho=torcida,
            estadio=Estadio(
                nome=d.get("estadio_nome") or f"Estádio do {d['nome']}",
                capacidade=capacidade,
                nivel_gramado=50 + prestigio // 3,
                nivel_estrutura=50 + prestigio // 3,
                preco_ingresso=max(30, prestigio // 2),
                custo_manutencao=capacidade * 5,
            ),
            financas=Financas(
                saldo=saldo,
                orcamento_salarios=saldo // 5,
                orcamento_transferencias=saldo // 2,
                patrocinador_principal=d.get("patrocinador") or "Sem patrocinador",
                receita_patrocinio_mensal=saldo // 50,
                receita_tv_mensal=saldo // 60 if divisao == 1 else saldo // 100,
                num_socios=torcida // 100,
                mensalidade_socio=50,
            ),
            base_juvenil=BaseJuvenil(
                nivel=min(90, prestigio + random.randint(-10, 10)),
                investimento_mensal=saldo // 100,
            ),
        )

        # Gerar elenco (com dados reais se disponíveis)
        reais = jogadores_db.get(d["nome"], []) if jogadores_db else []
        elenco, id_jogador = _gerar_elenco(time, id_jogador, prestigio,
                                            jogadores_reais=reais or None)
        time.jogadores = elenco

        # Selecionar titulares
        time.titulares = _selecionar_titulares_auto(time)

        # Gerar staff
        time.staff = _gerar_staff(time, prestigio)

        times.append(time)

    return times


def carregar_times_br_raw() -> dict:
    """Retorna o dict {serie_a: [...], serie_b: [...], ...} já com overrides aplicados.

    Cada valor é uma lista de dicts (não objetos Time).
    Usado pelo desktop_app para listar times na seleção de jogo.
    """
    return _carregar_json_times()


def criar_times_serie_a() -> List[Time]:
    """Cria os 20 times da Série A."""
    dados = _carregar_json_times()
    jogadores_db = _carregar_json_jogadores()
    return _criar_times(dados["serie_a"], divisao=1, jogadores_db=jogadores_db)


def criar_times_serie_b() -> List[Time]:
    """Cria os 20 times da Série B."""
    dados = _carregar_json_times()
    jogadores_db = _carregar_json_jogadores()
    return _criar_times(dados["serie_b"], divisao=2, jogadores_db=jogadores_db)


def criar_times_serie_c() -> List[Time]:
    """Cria os 20 times da Série C."""
    dados = _carregar_json_times()
    jogadores_db = _carregar_json_jogadores()
    return _criar_times(dados["serie_c"], divisao=3, jogadores_db=jogadores_db)


def criar_times_serie_d() -> List[Time]:
    """Cria os times da Série D."""
    dados = _carregar_json_times()
    jogadores_db = _carregar_json_jogadores()
    return _criar_times(dados["serie_d"], divisao=4, jogadores_db=jogadores_db)


def criar_times_sem_divisao() -> List[Time]:
    """Cria times que jogam apenas estaduais (sem divisão nacional)."""
    dados = _carregar_json_times()
    jogadores_db = _carregar_json_jogadores()
    return _criar_times(dados.get("sem_divisao", []), divisao=5, jogadores_db=jogadores_db)


# ══════════════════════════════════════════════════════════════
#  TIMES EUROPEUS
# ══════════════════════════════════════════════════════════════

_TEAMS_EU_FILE = os.path.join(_SEEDS_DIR, "teams_eu.json")
_PLAYERS_EU_FILE = os.path.join(_SEEDS_DIR, "players_eu.json")


def _carregar_json_times_eu() -> dict:
    if "teams_eu" not in _CACHE:
        if not os.path.exists(_TEAMS_EU_FILE):
            _CACHE["teams_eu"] = {}
        else:
            with open(_TEAMS_EU_FILE, _JSON_READ_MODE) as f:
                _CACHE["teams_eu"] = _normalizar_times_eu(_json_load(f))
    return _CACHE["teams_eu"]


def _carregar_json_jogadores_eu() -> dict:
    if "players_eu" not in _CACHE:
        if not os.path.exists(_PLAYERS_EU_FILE):
            _CACHE["players_eu"] = {}
        else:
            with open(_PLAYERS_EU_FILE, _JSON_READ_MODE) as f:
                _CACHE["players_eu"] = _json_load(f)
    return _CACHE["players_eu"]


# Map country code -> base divisao offset (10+)
# Original EU countries keep their fixed offsets for save compatibility.
# New countries get auto-generated offsets starting from 66.
_EU_DIVISAO_OFFSET_FIXED = {
    "ING": 10, "ESP": 14, "ITA": 18, "ALE": 22, "FRA": 26,
    "POR": 30, "HOL": 34, "BEL": 38, "TUR": 42, "RUS": 46,
    "ESC": 50, "SUI": 54, "AUT": 58, "GRE": 62,
}

_EU_DIVISAO_OFFSET_CACHE = None

def _get_eu_divisao_offset(pais: str) -> int:
    global _EU_DIVISAO_OFFSET_CACHE
    if pais in _EU_DIVISAO_OFFSET_FIXED:
        return _EU_DIVISAO_OFFSET_FIXED[pais]
    if _EU_DIVISAO_OFFSET_CACHE is None:
        dados = _carregar_json_times_eu()
        _EU_DIVISAO_OFFSET_CACHE = {}
        next_offset = 66
        for cc in sorted(dados.keys()):
            if cc not in _EU_DIVISAO_OFFSET_FIXED:
                _EU_DIVISAO_OFFSET_CACHE[cc] = next_offset
                next_offset += 4
    return _EU_DIVISAO_OFFSET_CACHE.get(pais, 1000)


def criar_times_europeus(pais: str) -> dict:
    """Cria times de um país europeu, retornando dict de divisao -> List[Time].

    Exemplo: criar_times_europeus('ING') -> {1: [...20 times...], 2: [...], ...}
    """
    dados_eu = _carregar_json_times_eu()
    jogadores_db = _carregar_json_jogadores_eu()

    if pais not in dados_eu:
        return {}

    country_data = dados_eu[pais]
    divisoes = country_data.get("divisoes", {})
    offset = _get_eu_divisao_offset(pais)

    result = {}
    for div_key, teams_list in divisoes.items():
        div_num = int(div_key.replace("div_", ""))
        divisao_id = offset + div_num - 1  # e.g. ING div_1 -> 10
        times = _criar_times(teams_list, divisao=divisao_id, jogadores_db=jogadores_db)
        result[div_num] = times

    return result


def criar_todos_times_europeus() -> dict:
    """Cria times de todos os países europeus disponíveis.

    Retorna: {pais_code: {div_num: List[Time]}}
    """
    dados_eu = _carregar_json_times_eu()
    all_times = {}
    for pais in dados_eu:
        country_times = criar_times_europeus(pais)
        if country_times:
            all_times[pais] = country_times
    return all_times


def listar_paises_europeus() -> list:
    """Retorna lista de países europeus disponíveis com info."""
    dados_eu = _carregar_json_times_eu()
    result = []
    for cc, data in dados_eu.items():
        ligas = data.get("ligas", [])
        top_liga = ligas[0]["nome"] if ligas else "Liga"
        total = sum(len(v) for v in data.get("divisoes", {}).values())
        result.append({
            "codigo": cc,
            "nome": data.get("pais_nome", cc),
            "liga_principal": top_liga,
            "total_times": total,
        })
    return result
