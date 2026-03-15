# -*- coding: utf-8 -*-
"""
Motor de coletivas de imprensa — gera perguntas contextuais e processa respostas.
"""
from __future__ import annotations

import random
from typing import List, Dict, Optional

from core.enums import TipoColetiva, TomResposta, CategoriaNoticia
from core.models import (
    PerguntaColetiva, RespostaColetiva, SessaoColetiva, Noticia,
)
from utils.logger import get_logger

log = get_logger(__name__)

# Jornalistas fictícios
_JORNALISTAS = [
    ("Marcos Ribeiro", "GloboEsporte"),
    ("Ana Paula Souza", "ESPN Brasil"),
    ("Pedro Mendes", "Lance!"),
    ("Luciana Torres", "UOL Esporte"),
    ("Roberto Dantas", "Gazeta Esportiva"),
    ("Fernanda Lima", "SporTV"),
    ("Carlos Augusto", "Fox Sports"),
    ("Juliana Martins", "TNT Sports"),
]


class PressConferenceEngine:
    """Gera e processa coletivas de imprensa."""

    def __init__(self) -> None:
        self.coletiva_pendente: Optional[SessaoColetiva] = None
        self.historico: List[Dict] = []

    def gerar_coletiva_pos_jogo(
        self,
        time_nome: str,
        adversario: str,
        gols_favor: int,
        gols_contra: int,
        competicao: str,
        eh_derby: bool = False,
        jogador_destaque: str = "",
    ) -> SessaoColetiva:
        """Gera coletiva pós-jogo com 3-5 perguntas contextuais."""
        perguntas: List[PerguntaColetiva] = []
        resultado = "vitória" if gols_favor > gols_contra else "empate" if gols_favor == gols_contra else "derrota"
        placar = f"{gols_favor}x{gols_contra}"

        # Pergunta 1: Sobre o resultado
        if resultado == "vitória":
            textos_resultado = [
                f"Como avalia a vitória por {placar} sobre o {adversario}?",
                f"A equipe mostrou consistência nessa vitória. O que achou do desempenho?",
                f"Vitória importante contra o {adversario}. Mudou algo na semana de preparação?",
            ]
        elif resultado == "derrota":
            textos_resultado = [
                f"O que explica a derrota por {placar} para o {adversario}?",
                f"A equipe ficou abaixo do esperado. O que precisa melhorar?",
                f"Derrota dolorosa. Isso afeta os planos para as próximas rodadas?",
            ]
        else:
            textos_resultado = [
                f"O empate em {placar} era o esperado contra o {adversario}?",
                f"Como avalia o ponto conquistado? Positivo ou negativo?",
            ]

        j, v = random.choice(_JORNALISTAS)
        perguntas.append(PerguntaColetiva(
            id=1, texto=random.choice(textos_resultado),
            jornalista=j, veiculo=v,
            tom_sugerido=[TomResposta.CONFIANTE, TomResposta.HUMILDE, TomResposta.DIPLOMATICO],
            contexto=f"resultado_{resultado}",
        ))

        # Pergunta 2: Sobre jogador destaque (se houver)
        if jogador_destaque:
            j, v = random.choice(_JORNALISTAS)
            perguntas.append(PerguntaColetiva(
                id=2, texto=f"O {jogador_destaque} foi destaque hoje. Pode falar sobre a atuação dele?",
                jornalista=j, veiculo=v,
                tom_sugerido=[TomResposta.CONFIANTE, TomResposta.HUMILDE],
                contexto=f"jogador_{jogador_destaque}",
            ))

        # Pergunta 3: Sobre competição/temporada
        j, v = random.choice(_JORNALISTAS)
        textos_comp = [
            f"Quais são as expectativas para o restante da {competicao}?",
            f"Essa sequência de jogos é decisiva. Como mantém o foco do grupo?",
            f"O time briga por algo mais nessa {competicao}?",
        ]
        perguntas.append(PerguntaColetiva(
            id=len(perguntas) + 1, texto=random.choice(textos_comp),
            jornalista=j, veiculo=v,
            tom_sugerido=[TomResposta.CONFIANTE, TomResposta.DIPLOMATICO, TomResposta.EVASIVO],
            contexto="competicao",
        ))

        # Pergunta 4: Derby extra
        if eh_derby:
            j, v = random.choice(_JORNALISTAS)
            perguntas.append(PerguntaColetiva(
                id=len(perguntas) + 1,
                texto=f"Clássico contra o {adversario} sempre tem um peso extra. O que esse resultado significa para a torcida?",
                jornalista=j, veiculo=v,
                tom_sugerido=[TomResposta.CONFIANTE, TomResposta.AGRESSIVO, TomResposta.HUMILDE],
                contexto="derby",
            ))

        # Pergunta 5: Pressão (aleatória)
        if random.random() < 0.4:
            j, v = random.choice(_JORNALISTAS)
            textos_pressao = [
                "Há rumores de insatisfação da diretoria. Isso é verdade?",
                "A torcida tem cobrado resultados. Como lida com a pressão?",
                "Alguns jogadores parecem desmotivados. Percebe isso?",
                "O mercado de transferências pode resolver os problemas do elenco?",
            ]
            perguntas.append(PerguntaColetiva(
                id=len(perguntas) + 1, texto=random.choice(textos_pressao),
                jornalista=j, veiculo=v,
                tom_sugerido=[TomResposta.DIPLOMATICO, TomResposta.AGRESSIVO, TomResposta.EVASIVO],
                contexto="pressao",
            ))

        sessao = SessaoColetiva(
            tipo=TipoColetiva.POS_JOGO,
            perguntas=perguntas,
        )
        self.coletiva_pendente = sessao
        return sessao

    def responder_pergunta(
        self,
        pergunta_id: int,
        tom: TomResposta,
    ) -> RespostaColetiva:
        """Processa resposta do técnico a uma pergunta."""
        if not self.coletiva_pendente:
            return RespostaColetiva()

        pergunta = None
        for p in self.coletiva_pendente.perguntas:
            if p.id == pergunta_id:
                pergunta = p
                break
        if not pergunta:
            return RespostaColetiva()

        # Gerar texto e impactos baseados no tom
        impactos = self._calcular_impactos(tom, pergunta.contexto)
        texto = self._gerar_texto_resposta(tom, pergunta)

        resposta = RespostaColetiva(
            tom=tom, texto=texto,
            impacto_moral_elenco=impactos["moral"],
            impacto_torcida=impactos["torcida"],
            impacto_midia=impactos["midia"],
            impacto_diretoria=impactos["diretoria"],
        )
        self.coletiva_pendente.respostas.append(resposta)
        return resposta

    def finalizar_coletiva(self) -> Dict:
        """Finaliza coletiva e retorna resumo de impactos."""
        if not self.coletiva_pendente:
            return {}
        self.coletiva_pendente.concluida = True
        total = {"moral": 0, "torcida": 0, "midia": 0, "diretoria": 0}
        for r in self.coletiva_pendente.respostas:
            total["moral"] += r.impacto_moral_elenco
            total["torcida"] += r.impacto_torcida
            total["midia"] += r.impacto_midia
            total["diretoria"] += r.impacto_diretoria

        self.historico.append({
            "tipo": self.coletiva_pendente.tipo.value,
            "perguntas": len(self.coletiva_pendente.perguntas),
            "respondidas": len(self.coletiva_pendente.respostas),
            "impactos": total,
        })
        self.coletiva_pendente = None
        return total

    # ── impactos ──────────────────────────────────────────────

    @staticmethod
    def _calcular_impactos(tom: TomResposta, contexto: str) -> Dict[str, int]:
        base = {"moral": 0, "torcida": 0, "midia": 0, "diretoria": 0}
        if tom == TomResposta.CONFIANTE:
            base["moral"] = random.randint(1, 3)
            base["torcida"] = random.randint(1, 4)
            base["midia"] = random.randint(0, 2)
            base["diretoria"] = random.randint(0, 2)
        elif tom == TomResposta.HUMILDE:
            base["moral"] = random.randint(0, 2)
            base["torcida"] = random.randint(-1, 2)
            base["midia"] = random.randint(1, 3)
            base["diretoria"] = random.randint(1, 3)
        elif tom == TomResposta.AGRESSIVO:
            base["moral"] = random.randint(2, 5)
            base["torcida"] = random.randint(2, 5)
            base["midia"] = random.randint(-3, -1)
            base["diretoria"] = random.randint(-2, 0)
        elif tom == TomResposta.DIPLOMATICO:
            base["moral"] = random.randint(0, 1)
            base["torcida"] = random.randint(0, 1)
            base["midia"] = random.randint(1, 2)
            base["diretoria"] = random.randint(1, 2)
        elif tom == TomResposta.EVASIVO:
            base["moral"] = random.randint(-1, 0)
            base["torcida"] = random.randint(-2, 0)
            base["midia"] = random.randint(-2, 0)
            base["diretoria"] = random.randint(-1, 1)

        # Bônus por contexto de derby
        if contexto == "derby" and tom == TomResposta.AGRESSIVO:
            base["torcida"] += 3
        return base

    @staticmethod
    def _gerar_texto_resposta(tom: TomResposta, pergunta: PerguntaColetiva) -> str:
        resps = {
            TomResposta.CONFIANTE: [
                "Estamos preparados e confiantes. O grupo está forte e unido.",
                "O trabalho vem sendo bem feito. Os resultados virão naturalmente.",
                "Acredito muito nesse grupo. Temos qualidade para grandes conquistas.",
            ],
            TomResposta.HUMILDE: [
                "Temos que manter os pés no chão e trabalhar dia a dia.",
                "Respeitamos todos os adversários. Cada jogo é uma batalha.",
                "Ainda temos muito o que melhorar. Mas estamos no caminho certo.",
            ],
            TomResposta.AGRESSIVO: [
                "Quem duvidar vai engolir as palavras. Esse time não brinca.",
                "Não aceito desrespeito com o nosso trabalho. Os números falam por si.",
                "Estamos aqui para ganhar. Quem não aguentar a pressão, saia.",
            ],
            TomResposta.DIPLOMATICO: [
                "Preferimos focar no nosso trabalho e deixar o campo falar.",
                "É cedo para tirar conclusões. Vamos seguir o planejamento.",
                "Cada partida tem sua história. Vamos respeitar o processo.",
            ],
            TomResposta.EVASIVO: [
                "Não vou comentar sobre isso agora.",
                "Prefiro não entrar nessa questão. Próxima pergunta.",
                "Não é o momento adequado para esse tipo de discussão.",
            ],
        }
        return random.choice(resps.get(tom, resps[TomResposta.DIPLOMATICO]))

    def to_save_dict(self) -> Dict:
        return {"historico": self.historico[-20:]}

    def from_save_dict(self, data: Dict) -> None:
        self.historico = data.get("historico", [])
