# -*- coding: utf-8 -*-
"""
Financial Fair Play Engine — controle financeiro e limites salariais.
"""
from __future__ import annotations
from typing import List, Dict
from core.models import Time
from utils.logger import get_logger

log = get_logger(__name__)


class FFPEngine:
    """Financial Fair Play: limites de gastos baseados em receita."""

    def __init__(self):
        self._historico_violacoes: Dict[str, List[Dict]] = {}  # time -> [{temporada, tipo, valor}]

    def calcular_limites(self, time: Time) -> Dict:
        """Calcula limites de FFP para um time."""
        f = time.financas
        receita_anual = (f.receita_tv_mensal + f.receita_patrocinio_mensal + f.receita_socios_mensal) * 12
        limite_folha = int(receita_anual * 0.70)  # 70% receita
        limite_transferencias = int(receita_anual * 0.50)  # 50% receita

        return {
            "receita_anual_estimada": receita_anual,
            "limite_folha_salarial": limite_folha,
            "folha_atual": time.folha_salarial * 12,
            "limite_transferencias": limite_transferencias,
            "orcamento_actual": f.orcamento_transferencias,
            "em_conformidade_folha": (time.folha_salarial * 12) <= limite_folha,
            "em_conformidade_geral": (time.folha_salarial * 12) <= limite_folha,
            "margem_folha": limite_folha - (time.folha_salarial * 12),
            "margem_transferencias": limite_transferencias - f.orcamento_transferencias,
        }

    def verificar_violacao(self, time: Time, temporada: int) -> List[str]:
        """Verifica se o time violou o FFP."""
        limites = self.calcular_limites(time)
        violacoes = []
        if not limites["em_conformidade_folha"]:
            violacoes.append(f"Folha salarial ({limites['folha_atual']:,}) excede o limite FFP ({limites['limite_folha_salarial']:,})")
            self._historico_violacoes.setdefault(time.nome, []).append({
                "temporada": temporada,
                "tipo": "folha_salarial",
                "valor": limites["folha_atual"] - limites["limite_folha_salarial"],
            })
        return violacoes

    def aplicar_penalidades(self, time: Time, temporada: int) -> List[str]:
        """Aplica penalidades por violação do FFP."""
        violacoes = self._historico_violacoes.get(time.nome, [])
        violacoes_atuais = [v for v in violacoes if v["temporada"] == temporada]
        if not violacoes_atuais:
            return []

        penalidades = []
        num_violacoes = len([v for v in violacoes if v["temporada"] >= temporada - 2])
        if num_violacoes >= 3:
            # Reincidente: multa pesada + redução de orçamento
            multa = int(time.financas.saldo * 0.10)
            time.financas.saldo -= multa
            time.financas.orcamento_transferencias = int(time.financas.orcamento_transferencias * 0.5)
            penalidades.append(f"Multa de R$ {multa:,} + orçamento de transferências reduzido em 50%")
        elif num_violacoes >= 1:
            # Primeira/segunda: advertência + multa leve
            multa = int(time.financas.saldo * 0.03)
            time.financas.saldo -= multa
            penalidades.append(f"Advertência FFP + multa de R$ {multa:,}")

        return penalidades

    def to_save_dict(self) -> Dict:
        return {"historico_violacoes": self._historico_violacoes}

    def from_save_dict(self, data: Dict):
        self._historico_violacoes = data.get("historico_violacoes", {})
