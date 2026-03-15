# -*- coding: utf-8 -*-
"""Models de Fantasy — Time fantasy, liga, jogador escalado."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class EscalacaoFantasy:
    """Um jogador escalado no time fantasy de uma rodada."""
    jogador_id: int = 0
    jogador_nome: str = ""
    time_real: str = ""
    posicao: str = ""
    pontos: float = 0.0
    capitao: bool = False  # 2× pontuação


@dataclass
class TimeFantasy:
    """Um participante da liga fantasy."""
    id: int = 0
    nome: str = ""
    dono: str = "CPU"
    saldo: int = 100  # cartoletas
    pontos_total: float = 0.0
    pontos_rodada: float = 0.0
    escalacao: List[EscalacaoFantasy] = field(default_factory=list)
    historico_rodadas: List[float] = field(default_factory=list)

    @property
    def media_pontos(self) -> float:
        if not self.historico_rodadas:
            return 0.0
        return sum(self.historico_rodadas) / len(self.historico_rodadas)


@dataclass
class LigaFantasy:
    """Representa uma liga fantasy com vários participantes."""
    nome: str = "Liga Ultrafoot"
    rodada_atual: int = 0
    times: List[TimeFantasy] = field(default_factory=list)

    def classificacao(self) -> List[TimeFantasy]:
        return sorted(self.times, key=lambda t: t.pontos_total, reverse=True)

    def time_por_id(self, tid: int) -> TimeFantasy | None:
        for t in self.times:
            if t.id == tid:
                return t
        return None
