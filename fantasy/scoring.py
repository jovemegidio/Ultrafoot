# -*- coding: utf-8 -*-
"""Scoring — calcula pontuação fantasy a partir dos eventos de partida."""
from __future__ import annotations

from typing import Dict, List

from core.constants import FANTASY_PONTOS, SETOR_POSICOES
from core.models import ResultadoPartida, EventoPartida, Time


def calcular_pontos_fantasy(resultado: ResultadoPartida,
                            time_casa: Time,
                            time_fora: Time) -> Dict[int, float]:
    """Retorna ``{jogador_id: pontos_fantasy}`` para todos os participantes."""
    pontos: Dict[int, float] = {}
    fp = FANTASY_PONTOS

    # Mapear jogadores → posição.name
    _pos_map: Dict[int, str] = {}
    for t in (time_casa, time_fora):
        for j in t.jogadores:
            _pos_map[j.id] = j.posicao.name

    def _setor(jid: int) -> str:
        pos = _pos_map.get(jid, "MC")
        if pos in SETOR_POSICOES["goleiro"]:
            return "goleiro"
        if pos in SETOR_POSICOES["defesa"]:
            return "defensor"
        if pos in SETOR_POSICOES["ataque"]:
            return "atacante"
        return "meia"

    # Processar eventos
    goleadores_casa: set[int] = set()
    goleadores_fora: set[int] = set()

    for ev in resultado.eventos:
        jid = ev.jogador_id
        if jid == 0:
            continue
        pontos.setdefault(jid, 0.0)

        if ev.tipo == "gol":
            setor = _setor(jid)
            chave = f"gol_{setor}"
            pontos[jid] += fp.get(chave, fp.get("gol_meia", 9.0))
            if ev.time == resultado.time_casa:
                goleadores_casa.add(jid)
            else:
                goleadores_fora.add(jid)

        elif ev.tipo == "assistencia":
            pontos[jid] += fp["assistencia"]

        elif ev.tipo == "cartao_amarelo":
            pontos[jid] += fp["cartao_amarelo"]

        elif ev.tipo == "cartao_vermelho":
            pontos[jid] += fp["cartao_vermelho"]

        elif ev.tipo == "defesa_dificil":
            pontos[jid] += fp["defesa_dificil"]

        elif ev.tipo == "defesa_penalti":
            pontos[jid] += fp["defesa_penalti"]

        elif ev.tipo == "penalti_perdido":
            pontos[jid] += fp["penalti_perdido"]

    # Bônus sem gol (clean sheet)
    _aplicar_clean_sheet(pontos, time_casa, resultado.gols_fora, fp)
    _aplicar_clean_sheet(pontos, time_fora, resultado.gols_casa, fp)

    # Penalidade por gol sofrido (goleiro/defensores)
    _aplicar_penalidade_gol_sofrido(pontos, time_casa, resultado.gols_fora, fp)
    _aplicar_penalidade_gol_sofrido(pontos, time_fora, resultado.gols_casa, fp)

    return pontos


def _aplicar_clean_sheet(pontos: Dict[int, float], time: Time,
                         gols_sofridos: int, fp: dict) -> None:
    if gols_sofridos > 0:
        return
    for j in time.jogadores:
        if j.id not in (time.titulares or []):
            continue
        pos = j.posicao.name
        if pos in SETOR_POSICOES["goleiro"]:
            pontos.setdefault(j.id, 0.0)
            pontos[j.id] += fp["sem_gol_goleiro"]
        elif pos in SETOR_POSICOES["defesa"]:
            pontos.setdefault(j.id, 0.0)
            pontos[j.id] += fp["sem_gol_defensor"]


def _aplicar_penalidade_gol_sofrido(pontos: Dict[int, float], time: Time,
                                    gols_sofridos: int, fp: dict) -> None:
    if gols_sofridos == 0:
        return
    for j in time.jogadores:
        if j.id not in (time.titulares or []):
            continue
        pos = j.posicao.name
        if pos in SETOR_POSICOES["goleiro"]:
            pontos.setdefault(j.id, 0.0)
            pontos[j.id] += gols_sofridos * fp["gol_sofrido_goleiro"]
        elif pos in SETOR_POSICOES["defesa"]:
            pontos.setdefault(j.id, 0.0)
            pontos[j.id] += gols_sofridos * fp["gol_sofrido_defensor"]
