# -*- coding: utf-8 -*-
"""
AI Service — lógica de IA dos times adversários.
Toma decisões de escalação, tática, contratações e vendas para CPUs.
"""
from __future__ import annotations

import random
from typing import List

from core.models import Time
from core.enums import FormacaoTatica, EstiloJogo


class AIService:
    """Serviço de IA para gerenciar times controlados pelo computador."""

    def decidir_tatica(self, time: Time, adversario: Time) -> None:
        """Ajusta tática do time CPU conforme o adversário."""
        forca_propria = time.forca_time
        forca_adv = adversario.forca_time

        diff = forca_propria - forca_adv

        if diff > 10:
            # Muito mais forte → ofensivo
            time.tatica.estilo = EstiloJogo.OFENSIVO
        elif diff > 3:
            time.tatica.estilo = EstiloJogo.EQUILIBRADO
        elif diff > -5:
            time.tatica.estilo = EstiloJogo.EQUILIBRADO
        elif diff > -15:
            time.tatica.estilo = EstiloJogo.DEFENSIVO
        else:
            time.tatica.estilo = EstiloJogo.MUITO_DEFENSIVO
            time.tatica.contra_ataque = True

        # Variação aleatória de formação
        if random.random() < 0.1:
            time.tatica.formacao = random.choice(list(FormacaoTatica))

    def escalar_titulares(self, time: Time) -> None:
        """Auto-escala titulares do time CPU."""
        from data.seeds.seed_loader import _selecionar_titulares_auto
        time.titulares = _selecionar_titulares_auto(time)

    def avaliar_elenco(self, time: Time) -> dict:
        """Retorna análise do elenco para decisões de mercado."""
        from core.constants import ELENCO_MODELO
        from core.enums import Posicao

        posicoes_necessarias = {Posicao[p]: n for p, n in ELENCO_MODELO}
        contagem = {}
        for j in time.jogadores:
            contagem[j.posicao] = contagem.get(j.posicao, 0) + 1

        carentes: List[str] = []
        excessos: List[str] = []

        for pos, necessario in posicoes_necessarias.items():
            atual = contagem.get(pos, 0)
            if atual < necessario:
                carentes.append(pos.name)
            elif atual > necessario + 1:
                excessos.append(pos.name)

        return {
            "total": len(time.jogadores),
            "overall_medio": time.overall_medio,
            "folha": time.folha_salarial,
            "carentes": carentes,
            "excessos": excessos,
        }
