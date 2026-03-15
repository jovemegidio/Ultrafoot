# -*- coding: utf-8 -*-
"""
Hall of Fame — registro cumulativo de destaques ao longo das temporadas.
"""
from __future__ import annotations
from typing import List, Dict
from utils.logger import get_logger

log = get_logger(__name__)


class HallOfFameEngine:
    """Hall da Fama cumulativo cross-temporada."""

    def __init__(self):
        self._entradas: List[Dict] = []

    def registrar(self, jogador_nome: str, time_nome: str, temporada: int,
                  categoria: str, descricao: str, valor: str = ""):
        """Adiciona jogador ao Hall of Fame."""
        self._entradas.append({
            "jogador": jogador_nome,
            "time": time_nome,
            "temporada": temporada,
            "categoria": categoria,  # "artilheiro", "bola_ouro", "revelacao", "melhor_goleiro", "selecao"
            "descricao": descricao,
            "valor": valor,
        })

    def get_todos(self) -> List[Dict]:
        return sorted(self._entradas, key=lambda e: -e["temporada"])

    def get_por_categoria(self, categoria: str) -> List[Dict]:
        return [e for e in self._entradas if e["categoria"] == categoria]

    def get_por_jogador(self, nome: str) -> List[Dict]:
        return [e for e in self._entradas if e["jogador"] == nome]

    def get_lendas(self, min_premios: int = 3) -> List[Dict]:
        """Retorna jogadores com múltiplas aparições no HoF."""
        contagem: Dict[str, int] = {}
        for e in self._entradas:
            contagem[e["jogador"]] = contagem.get(e["jogador"], 0) + 1
        lendas = []
        for nome, count in contagem.items():
            if count >= min_premios:
                premios = [e for e in self._entradas if e["jogador"] == nome]
                lendas.append({"jogador": nome, "total_premios": count, "premios": premios})
        return sorted(lendas, key=lambda l: -l["total_premios"])

    def to_save_dict(self) -> Dict:
        return {"entradas": self._entradas}

    def from_save_dict(self, data: Dict):
        self._entradas = data.get("entradas", [])
