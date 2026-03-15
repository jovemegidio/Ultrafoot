# -*- coding: utf-8 -*-
"""
World Rankings — ranking FIFA-style dinâmico para times.
"""
from __future__ import annotations
from typing import List, Dict, Optional
from core.models import Time, ResultadoPartida
from utils.logger import get_logger

log = get_logger(__name__)


class WorldRankingsEngine:
    """Ranking dinâmico global de clubes, estilo ranking FIFA."""

    def __init__(self):
        self._pontos: Dict[str, float] = {}  # time_nome -> pontos
        self._ranking_cache: List[Dict] = []

    def inicializar(self, todos_times: List[Time]):
        """Inicializa pontos baseados em prestígio e divisão."""
        for t in todos_times:
            base = t.prestigio * 10
            div_bonus = {1: 500, 2: 200, 3: 50, 4: 0}.get(t.divisao, 0)
            self._pontos[t.nome] = base + div_bonus
        self._atualizar_cache(todos_times)

    def processar_resultados(self, resultados: Dict[str, List[ResultadoPartida]],
                             todos_times: List[Time]):
        """Atualiza ranking com resultados da rodada."""
        for comp, lista in resultados.items():
            peso = 3.0 if "Libertadores" in comp else 2.0 if "Copa" in comp else 1.0
            for r in lista:
                pts_casa = self._pontos.get(r.time_casa, 500)
                pts_fora = self._pontos.get(r.time_fora, 500)
                diff = (pts_fora - pts_casa) / 400
                expected_casa = 1 / (1 + 10 ** diff)
                expected_fora = 1 - expected_casa

                if r.gols_casa > r.gols_fora:
                    actual_casa, actual_fora = 1.0, 0.0
                elif r.gols_casa < r.gols_fora:
                    actual_casa, actual_fora = 0.0, 1.0
                else:
                    actual_casa, actual_fora = 0.5, 0.5

                k = 8 * peso
                self._pontos[r.time_casa] = pts_casa + k * (actual_casa - expected_casa)
                self._pontos[r.time_fora] = pts_fora + k * (actual_fora - expected_fora)

        self._atualizar_cache(todos_times)

    def _atualizar_cache(self, todos_times: List[Time]):
        nomes = {t.nome: t for t in todos_times}
        ranking = []
        for nome, pts in sorted(self._pontos.items(), key=lambda x: -x[1]):
            t = nomes.get(nome)
            if t:
                ranking.append({
                    "posicao": 0,
                    "nome": nome,
                    "pontos": round(pts, 1),
                    "divisao": t.divisao,
                    "pais": getattr(t, 'estado', 'BR'),
                    "prestigio": t.prestigio,
                })
        for i, item in enumerate(ranking):
            item["posicao"] = i + 1
        self._ranking_cache = ranking

    def get_ranking(self, top_n: int = 100) -> List[Dict]:
        return self._ranking_cache[:top_n]

    def get_posicao(self, nome_time: str) -> Optional[Dict]:
        for item in self._ranking_cache:
            if item["nome"] == nome_time:
                return item
        return None

    def to_save_dict(self) -> Dict:
        return {"pontos": self._pontos}

    def from_save_dict(self, data: Dict):
        self._pontos = data.get("pontos", {})
