# -*- coding: utf-8 -*-
"""
Scout Service — busca e avaliação de jogadores no mercado.
Rede global de scouts com cobertura regional (FM-style).
"""
from __future__ import annotations

import random
from typing import List, Optional, Dict

from core.models import Jogador, Time, StaffMembro
from core.enums import Posicao, TipoStaff, TraitJogador


# ── Regiões de cobertura de scout ─────────────────────────────
SCOUT_REGIONS = {
    "brasil": {"nome": "Brasil", "paises": ["Brasil"]},
    "america_sul": {"nome": "América do Sul", "paises": [
        "Argentina", "Uruguai", "Paraguai", "Chile", "Colômbia",
        "Equador", "Peru", "Venezuela", "Bolívia",
    ]},
    "europa_oeste": {"nome": "Europa Ocidental", "paises": [
        "Espanha", "Inglaterra", "França", "Alemanha", "Itália",
        "Portugal", "Holanda", "Bélgica", "Suíça",
    ]},
    "europa_leste": {"nome": "Europa Oriental", "paises": [
        "Rússia", "Turquia", "Ucrânia", "Croácia", "Sérvia",
        "Grécia", "Áustria", "Suécia", "Noruega", "Dinamarca",
    ]},
    "america_norte": {"nome": "América do Norte", "paises": [
        "Estados Unidos", "México",
    ]},
    "asia": {"nome": "Ásia", "paises": [
        "Japão", "China", "Coreia do Sul", "Arábia Saudita", "Emirados Árabes",
    ]},
    "africa": {"nome": "África", "paises": [
        "Marrocos", "Egito", "África do Sul", "Nigéria", "Senegal",
        "Costa do Marfim", "Gana", "Camarões",
    ]},
}


class ScoutNetwork:
    """Rede de scouts com cobertura por região (FM-style)."""

    def __init__(self):
        # região → {"nivel": 0-100, "ativo": bool}
        self.cobertura: Dict[str, Dict] = {}
        # Inicia com Brasil ativo
        for regiao in SCOUT_REGIONS:
            self.cobertura[regiao] = {
                "nivel": 80 if regiao == "brasil" else 0,
                "ativo": regiao == "brasil",
            }

    def ativar_regiao(self, regiao: str) -> bool:
        if regiao in self.cobertura and not self.cobertura[regiao]["ativo"]:
            self.cobertura[regiao]["ativo"] = True
            self.cobertura[regiao]["nivel"] = max(20, self.cobertura[regiao]["nivel"])
            return True
        return False

    def melhorar_regiao(self, regiao: str, pontos: int = 5) -> int:
        if regiao in self.cobertura and self.cobertura[regiao]["ativo"]:
            self.cobertura[regiao]["nivel"] = min(100, self.cobertura[regiao]["nivel"] + pontos)
            return self.cobertura[regiao]["nivel"]
        return 0

    def nivel_cobertura(self, nacionalidade: str) -> int:
        """Retorna o nível de cobertura para uma nacionalidade."""
        for regiao, info in SCOUT_REGIONS.items():
            if nacionalidade in info["paises"]:
                cob = self.cobertura.get(regiao, {})
                return cob.get("nivel", 0) if cob.get("ativo") else 0
        # Nacionalidade desconhecida — mínimo
        return 10

    def regioes_ativas(self) -> List[Dict]:
        return [
            {"id": r, "nome": SCOUT_REGIONS[r]["nome"],
             "nivel": self.cobertura[r]["nivel"],
             "ativo": self.cobertura[r]["ativo"],
             "paises": SCOUT_REGIONS[r]["paises"]}
            for r in SCOUT_REGIONS
        ]

    def custo_ativacao(self, regiao: str) -> int:
        """Custo mensal para manter a cobertura na região."""
        custos = {
            "brasil": 50_000, "america_sul": 100_000,
            "europa_oeste": 250_000, "europa_leste": 150_000,
            "america_norte": 120_000, "asia": 180_000, "africa": 80_000,
        }
        return custos.get(regiao, 100_000)

    def to_save_dict(self) -> Dict:
        return {"cobertura": self.cobertura}

    @classmethod
    def from_save_dict(cls, d: Dict) -> "ScoutNetwork":
        sn = cls()
        sn.cobertura = d.get("cobertura", sn.cobertura)
        return sn


class ScoutService:
    """Serviço de olheiro (scout) para buscar jogadores em outros times."""

    def buscar_jogadores(self, todos_times: List[Time],
                         time_jogador: Time,
                         posicao: Optional[Posicao] = None,
                         overall_min: int = 0,
                         idade_max: int = 99,
                         valor_max: int = 999_999_999,
                         nacionalidade: Optional[str] = None,
                         pais_liga: Optional[str] = None,
                         scout_network: Optional[ScoutNetwork] = None) -> List[dict]:
        """Retorna lista de jogadores filtrados com informações de scout.
        A rede de scouts afeta precisão por região."""
        resultados: list[dict] = []

        # Precisão do scout do meu time
        olheiro = time_jogador.staff_por_tipo(TipoStaff.SCOUT)
        precisao_base = olheiro.habilidade if olheiro else 50

        for time in todos_times:
            if time.nome == time_jogador.nome:
                continue
            # Filtro por país da liga (regional scouting)
            if pais_liga and getattr(time, 'estado', '') != pais_liga:
                continue
            for j in time.jogadores:
                if posicao and j.posicao != posicao:
                    continue
                if j.overall < overall_min:
                    continue
                if j.idade > idade_max:
                    continue
                if j.valor_mercado > valor_max:
                    continue
                if nacionalidade and j.nacionalidade != nacionalidade:
                    continue

                # Precisão ajustada pela cobertura de scout na região
                precisao = precisao_base
                if scout_network:
                    cobertura = scout_network.nivel_cobertura(j.nacionalidade)
                    precisao = int(precisao_base * (0.5 + cobertura / 200))

                # Imprecisão do scout: overall reportado com erro
                erro = random.randint(-max(1, (100 - precisao) // 5),
                                      max(1, (100 - precisao) // 5))
                overall_visto = max(1, min(99, j.overall + erro))

                resultados.append({
                    "jogador": j,
                    "time": time.nome,
                    "overall_visto": overall_visto,
                    "valor_estimado": j.valor_mercado,
                    "confianca": min(100, precisao + random.randint(-5, 10)),
                })
                if len(resultados) >= 200:
                    break
            if len(resultados) >= 200:
                break

        # Ordenar por overall visto (desc)
        resultados.sort(key=lambda r: r["overall_visto"], reverse=True)
        return resultados[:50]

    def relatorio_jogador(self, jogador: Jogador, precisao_scout: int = 50) -> dict:
        """Gera relatório detalhado de um jogador com imprecisão."""
        erro = max(1, (100 - precisao_scout) // 4)

        def _impreciso(val: int) -> int:
            return max(1, min(99, val + random.randint(-erro, erro)))

        return {
            "nome": jogador.nome,
            "posicao": jogador.posicao.value,
            "idade": jogador.idade,
            "overall_visto": _impreciso(jogador.overall),
            "potencial_visto": _impreciso(jogador.potencial),
            "tecnicos": _impreciso(int(jogador.tecnicos.overall())),
            "fisicos": _impreciso(int(jogador.fisicos.overall())),
            "mentais": _impreciso(int(jogador.mentais.overall())),
            "valor_estimado": jogador.valor_mercado,
            "salario": jogador.contrato.salario,
            "contrato_restante": jogador.contrato.meses_restantes,
            "traits_visiveis": [t.value for t in jogador.traits]
                if precisao_scout >= 70 else [],
            "confianca": min(100, precisao_scout + random.randint(-5, 10)),
        }

    def relatorio_adversario(self, adversario: Time, precisao_scout: int = 50) -> dict:
        """Análise tática do adversário para preparação de jogo."""
        erro = max(1, (100 - precisao_scout) // 4)

        def _imp(val: int) -> int:
            return max(1, min(99, val + random.randint(-erro, erro)))

        titulares = [j for j in adversario.jogadores if j.id in adversario.titulares]
        if not titulares:
            titulares = sorted(adversario.jogadores, key=lambda j: j.overall, reverse=True)[:11]

        setores = {"ataque": [], "meio": [], "defesa": [], "goleiro": []}
        for j in titulares:
            pos = j.posicao.name
            if pos in ("CA", "SA", "PD", "PE"):
                setores["ataque"].append(j)
            elif pos in ("MC", "ME", "MD", "MEI", "VOL"):
                setores["meio"].append(j)
            elif pos in ("ZAG", "LD", "LE"):
                setores["defesa"].append(j)
            else:
                setores["goleiro"].append(j)

        def _media_setor(jogadores):
            return _imp(int(sum(j.overall for j in jogadores) / max(1, len(jogadores)))) if jogadores else 0

        ponto_forte = max(setores, key=lambda s: _media_setor(setores[s]) if s != "goleiro" else 0)
        ponto_fraco = min((s for s in setores if s != "goleiro"), key=lambda s: _media_setor(setores[s]))

        return {
            "nome": adversario.nome,
            "formacao": adversario.tatica.formacao.value,
            "estilo": adversario.tatica.estilo.value,
            "overall_visto": _imp(adversario.overall_medio),
            "forca_ataque": _media_setor(setores["ataque"]),
            "forca_meio": _media_setor(setores["meio"]),
            "forca_defesa": _media_setor(setores["defesa"]),
            "forca_goleiro": _media_setor(setores["goleiro"]),
            "ponto_forte": ponto_forte,
            "ponto_fraco": ponto_fraco,
            "jogador_destaque": max(titulares, key=lambda j: j.overall).nome if titulares else "",
            "forma_recente": f"{adversario.vitorias}V {adversario.empates}E {adversario.derrotas}D",
            "confianca": min(100, precisao_scout + random.randint(-5, 10)),
        }
