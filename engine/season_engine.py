# -*- coding: utf-8 -*-
"""
Motor de progressão semanal: treinamento, evolução, lesões, moral, base juvenil.
"""
from __future__ import annotations

import random
from typing import Dict, List

from core.enums import StatusLesao, TipoStaff, NivelTreinamento, CategoriaNoticia, TraitJogador
from core.models import Time, Jogador, Noticia, Historico
from config import (
    EVO_FATOR_JOVEM, EVO_FATOR_PRIME, EVO_FATOR_VETERANO, EVO_FATOR_DECLINIO,
    EVO_CHANCE_EVOLUCAO, EVO_CHANCE_DECLINIO, IDADE_APOSENTADORIA,
    CHANCE_APOSENTADORIA,
)
from utils.name_generator import gerar_nome_brasileiro
from utils.logger import get_logger

log = get_logger(__name__)


class MotorTemporada:
    """Processa a progressão semanal e de fim de temporada."""

    def __init__(self) -> None:
        self.noticias: List[Noticia] = []
        self.pre_temporada_ativa: bool = False
        self.pre_temporada_semanas_restantes: int = 0

    # ═══════════════════════════════════════════════════════════
    #  SEMANA
    # ═══════════════════════════════════════════════════════════

    def processar_semana(self, times: List[Time]) -> List[Noticia]:
        self.noticias = []
        for time in times:
            self._recuperar_condicao(time)
            self._processar_lesoes(time)
            self._processar_suspensoes(time)
            self._processar_treinamento(time)
            self._verificar_moral(time)
            self._processar_base_juvenil(time)
        return self.noticias

    # ── recuperação ───────────────────────────────────────────

    def _recuperar_condicao(self, time: Time) -> None:
        medico = time.staff_por_tipo(TipoStaff.MEDICO)
        bonus = (medico.habilidade - 50) / 100 if medico else 0
        for j in time.jogadores:
            if j.condicao_fisica < 100:
                rec = random.randint(10, 25) + int(bonus * 10)
                if j.tem_trait(TraitJogador.MOTOR):
                    rec = int(rec * 1.3)
                j.condicao_fisica = min(100, j.condicao_fisica + rec)

    # ── lesões ────────────────────────────────────────────────

    def _processar_lesoes(self, time: Time) -> None:
        medico = time.staff_por_tipo(TipoStaff.MEDICO)
        bonus = 1.0 + (medico.habilidade - 50) / 200 if medico else 1.0
        for j in time.jogadores:
            if j.status_lesao != StatusLesao.SAUDAVEL and j.dias_lesao > 0:
                j.dias_lesao = max(0, j.dias_lesao - int(7 * bonus))
                if j.dias_lesao == 0:
                    j.status_lesao = StatusLesao.SAUDAVEL
                    j.condicao_fisica = 60
                    self.noticias.append(Noticia(
                        titulo=f"RECUPERADO: {j.nome}",
                        texto=f"{j.nome} do {time.nome} está recuperado!",
                        categoria=CategoriaNoticia.LESAO,
                    ))

    # ── suspensões ────────────────────────────────────────────

    @staticmethod
    def _processar_suspensoes(time: Time) -> None:
        for j in time.jogadores:
            if j.suspensao_jogos > 0:
                j.suspensao_jogos -= 1
            if j.cartao_amarelo_acumulado >= 3:
                j.suspensao_jogos += 1
                j.cartao_amarelo_acumulado = 0

    # ── treinamento ───────────────────────────────────────────

    def _processar_treinamento(self, time: Time) -> None:
        if not time.treinamento:
            return
        treinador = time.staff_por_tipo(TipoStaff.TREINADOR)
        preparador = time.staff_por_tipo(TipoStaff.PREPARADOR)
        f_treinador = (treinador.habilidade / 50) if treinador else 1.0
        f_preparador = (preparador.habilidade / 50) if preparador else 1.0
        f_intensidade = time.treinamento.fator_evolucao
        risco = time.treinamento.risco_lesao

        for j in time.jogadores:
            if j.status_lesao != StatusLesao.SAUDAVEL:
                continue
            # Risco de lesão no treino
            risco_j = risco
            if j.tem_trait(TraitJogador.VIDRACEIRO):
                risco_j *= 1.5
            if random.random() < risco_j:
                j.status_lesao = StatusLesao.LEVE
                j.dias_lesao = random.randint(3, 14)
                j.condicao_fisica = max(0, j.condicao_fisica - 20)
                continue

            fator_idade = self._fator_idade(j.idade)
            margem = max(0, j.potencial - j.overall)
            fator_potencial = margem / 50
            # Desenvolvimento por minutos: titulares evoluem mais
            fator_minutos = 1.3 if j.id in time.titulares else 0.7
            evolucao = f_intensidade * f_treinador * fator_idade * fator_potencial * fator_minutos * 0.3

            # ── Treino individualizado (FM-style) ──
            plano_ind = time.treinamento.planos_individuais.get(j.id)

            if evolucao > 0 and random.random() < EVO_CHANCE_EVOLUCAO:
                if plano_ind:
                    self._evoluir_individual(j, plano_ind, evolucao * 1.15)
                else:
                    self._evoluir_jogador(j, time.treinamento, evolucao)
            elif fator_idade < 0 and random.random() < EVO_CHANCE_DECLINIO:
                self._declinar_jogador(j)

    @staticmethod
    def _fator_idade(idade: int) -> float:
        if idade <= 23:
            return EVO_FATOR_JOVEM
        if idade <= 28:
            return EVO_FATOR_PRIME
        if idade <= 32:
            return EVO_FATOR_VETERANO
        return EVO_FATOR_DECLINIO

    @staticmethod
    def _evoluir_jogador(j: Jogador, treino, fator: float) -> None:
        pontos = max(1, int(fator * 2))
        fp = getattr(treino, 'foco_principal', 'finalizacao')
        fs = getattr(treino, 'foco_secundario', 'velocidade')

        for _ in range(pontos):
            # Primary focus (stronger effect)
            if fp == "gol":
                if j.posicao.name == "GOL" and j.goleiro:
                    attr = random.choice(["reflexos", "posicionamento_gol", "defesa_1v1", "elasticidade"])
                    setattr(j.goleiro, attr, min(99, getattr(j.goleiro, attr) + 1))
                else:
                    attr = random.choice(["desarme", "marcacao"])
                    setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))
            elif fp == "desarme":
                attr = random.choice(["desarme", "marcacao"])
                setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))
            elif fp == "armacao":
                attr = random.choice(["passe_curto", "passe_longo", "lancamento"])
                setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))
                if random.random() < 0.4:
                    j.mentais.visao_jogo = min(99, j.mentais.visao_jogo + 1)
            elif fp == "finalizacao":
                attr = random.choice(["finalizacao", "chute_longa_dist", "cabeceio"])
                setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))

            # Secondary focus (lighter effect — 50% chance per point)
            if random.random() < 0.5:
                if fs == "velocidade":
                    attr = random.choice(["velocidade", "aceleracao"])
                    setattr(j.fisicos, attr, min(99, getattr(j.fisicos, attr) + 1))
                elif fs == "tecnica":
                    attr = random.choice(["drible", "controle_bola"])
                    setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))
                elif fs == "passe":
                    attr = random.choice(["passe_curto", "passe_longo"])
                    setattr(j.tecnicos, attr, min(99, getattr(j.tecnicos, attr) + 1))

            # Always some base fitness improvement
            if random.random() < 0.3:
                j.fisicos.resistencia = min(99, j.fisicos.resistencia + 1)

    @staticmethod
    def _declinar_jogador(j: Jogador) -> None:
        if not j.fisicos:
            return
        attr = random.choice(["velocidade", "aceleracao", "resistencia", "agilidade"])
        setattr(j.fisicos, attr, max(1, getattr(j.fisicos, attr) - 1))

    # ── treino individualizado (FM-style) ─────────────────────

    _INDIVIDUAL_MAP = {
        "finalizacao": ("tecnicos", ["finalizacao", "chute_longa_dist"]),
        "desarme": ("tecnicos", ["desarme", "marcacao"]),
        "armacao": ("tecnicos", ["passe_curto", "passe_longo", "lancamento"]),
        "gol": ("goleiro", ["reflexos", "posicionamento_gol", "defesa_1v1"]),
        "cabecear": ("tecnicos", ["cabeceio"]),
        "drible": ("tecnicos", ["drible", "controle_bola"]),
        "passe": ("tecnicos", ["passe_curto", "passe_longo"]),
        "cruzamento": ("tecnicos", ["cruzamento"]),
        "velocidade": ("fisicos", ["velocidade", "aceleracao"]),
        "forca": ("fisicos", ["forca", "equilibrio"]),
        "resistencia": ("fisicos", ["resistencia"]),
        "agilidade": ("fisicos", ["agilidade", "salto"]),
        "mentalidade": ("mentais", ["compostura", "concentracao", "determinacao"]),
        "lideranca": ("mentais", ["lideranca", "trabalho_equipe"]),
        "visao": ("mentais", ["visao_jogo", "decisao", "criatividade"]),
        "posicionamento": ("mentais", ["posicionamento", "antecipacao"]),
    }

    @staticmethod
    def _evoluir_individual(j: Jogador, plano: Dict[str, str], fator: float) -> None:
        """Evolui jogador com base em seu plano individual de treino."""
        foco = plano.get("foco", "finalizacao")
        info = MotorTemporada._INDIVIDUAL_MAP.get(foco)
        if not info:
            return
        grupo, attrs = info
        obj = getattr(j, grupo, None)
        if obj is None:
            return
        pontos = max(1, int(fator * 2))
        for _ in range(pontos):
            attr = random.choice(attrs)
            current = getattr(obj, attr, 0)
            setattr(obj, attr, min(99, current + 1))
        # 30% chance extra fitness
        if j.fisicos and random.random() < 0.3:
            j.fisicos.resistencia = min(99, j.fisicos.resistencia + 1)

    # ── treinamento individual (sessão avulsa) ────────────────

    @staticmethod
    def processar_treino_individual(jogador: Jogador, atributo: str, intensidade: float = 1.0) -> str:
        """Treina um atributo específico de um jogador. Retorna mensagem."""
        MAPA = {
            "finalizacao": ("tecnicos", "finalizacao"),
            "passe_curto": ("tecnicos", "passe_curto"),
            "passe_longo": ("tecnicos", "passe_longo"),
            "drible": ("tecnicos", "drible"),
            "desarme": ("tecnicos", "desarme"),
            "marcacao": ("tecnicos", "marcacao"),
            "cabeceio": ("tecnicos", "cabeceio"),
            "velocidade": ("fisicos", "velocidade"),
            "resistencia": ("fisicos", "resistencia"),
            "forca": ("fisicos", "forca"),
            "agilidade": ("fisicos", "agilidade"),
            "visao_jogo": ("mentais", "visao_jogo"),
            "posicionamento": ("mentais", "posicionamento"),
            "compostura": ("mentais", "compostura"),
            "reflexos": ("goleiro", "reflexos"),
            "defesa_1v1": ("goleiro", "defesa_1v1"),
        }
        if atributo not in MAPA:
            return f"Atributo '{atributo}' não treinável."
        grupo, campo = MAPA[atributo]
        obj = getattr(jogador, grupo)
        atual = getattr(obj, campo)
        if atual >= 99:
            return f"{jogador.nome}: {atributo} já está no máximo."
        chance = 0.35 * intensidade * (1.0 + (jogador.potencial - jogador.overall) / 100)
        if random.random() < chance:
            setattr(obj, campo, min(99, atual + 1))
            return f"{jogador.nome}: {atributo} +1 ({atual} → {atual + 1})"
        return f"{jogador.nome}: treino de {atributo} sem evolução desta vez."

    # ── pré-temporada ─────────────────────────────────────────

    def iniciar_pre_temporada(self, times: List[Time], semanas: int = 4) -> None:
        """Inicia período de pré-temporada com treinos intensivos."""
        self.pre_temporada_ativa = True
        self.pre_temporada_semanas_restantes = semanas
        for t in times:
            for j in t.jogadores:
                j.condicao_fisica = min(100, j.condicao_fisica + 15)

    def processar_pre_temporada(self, times: List[Time]) -> List[Noticia]:
        """Processa uma semana de pré-temporada (treino 2x)."""
        self.noticias = []
        if not self.pre_temporada_ativa:
            return self.noticias
        self.pre_temporada_semanas_restantes -= 1
        for t in times:
            self._recuperar_condicao(t)
            self._processar_treinamento(t)
            self._processar_treinamento(t)  # treino duplo
            self._processar_base_juvenil(t)
        if self.pre_temporada_semanas_restantes <= 0:
            self.pre_temporada_ativa = False
            self.noticias.append(Noticia(
                titulo="PRÉ-TEMPORADA ENCERRADA",
                texto="A pré-temporada chegou ao fim. Jogadores estão em melhor forma!",
                categoria=CategoriaNoticia.GERAL,
            ))
        return self.noticias

    # ── moral ─────────────────────────────────────────────────

    @staticmethod
    def _verificar_moral(time: Time) -> None:
        for j in time.jogadores:
            if j.id not in time.titulares and j.overall > 60:
                if random.random() < 0.1:
                    j.moral = max(0, j.moral - 3)
                    if j.moral < 30:
                        j.quer_sair = True
            if j.contrato.meses_restantes <= 6 and random.random() < 0.2:
                j.moral = max(0, j.moral - 2)
            # PANELEIRO: moral baixa contagia outros jogadores
            if j.tem_trait(TraitJogador.PANELEIRO) and j.moral < 40:
                for outro in time.jogadores:
                    if outro.id != j.id and outro.id in time.titulares:
                        if random.random() < 0.15:
                            outro.moral = max(0, outro.moral - 2)
            # Tende a normalizar
            if j.moral > 70:
                j.moral = max(60, j.moral - 1)
            elif j.moral < 40:
                j.moral = min(50, j.moral + 1)

    # ── base juvenil ──────────────────────────────────────────

    def _processar_base_juvenil(self, time: Time) -> None:
        if not time.base_juvenil:
            return
        if random.random() > 0.95:
            return
        max_id = max((j.id for j in time.jogadores), default=0) + 1
        nivel = time.base_juvenil.nivel
        chance = time.base_juvenil.chance_revelar * (nivel / 50)
        if random.random() > chance:
            return
        from core.models import ContratoJogador
        from core.enums import Posicao, TipoContrato
        nome = gerar_nome_brasileiro()
        idade = random.randint(15, 19)
        posicao = random.choice(list(Posicao))
        base_attr = max(25, min(60, nivel // 2 + random.randint(-10, 15)))
        potencial = min(99, base_attr + random.randint(10, 35))

        # Reutiliza a lógica de geração do seed_loader (importação tardia)
        from data.seeds.seed_loader import gerar_atributos_jogador
        jogador = Jogador(
            id=max_id, nome=nome, idade=idade, posicao=posicao,
            potencial=potencial,
            contrato=ContratoJogador(
                tipo=TipoContrato.JUVENIL,
                salario=random.randint(5000, 20000),
                multa_rescisoria=random.randint(500000, 5000000),
                duracao_meses=36, meses_restantes=36,
            ),
        )
        gerar_atributos_jogador(jogador, base_attr)
        time.jogadores.append(jogador)
        self.noticias.append(Noticia(
            titulo=f"REVELAÇÃO: {nome}",
            texto=(f"A base do {time.nome} revelou {nome} ({idade} anos), "
                   f"promissor {posicao.value} com OVR {jogador.overall}!"),
            categoria=CategoriaNoticia.GERAL,
        ))

    # ═══════════════════════════════════════════════════════════
    #  FIM DE TEMPORADA
    # ═══════════════════════════════════════════════════════════

    def processar_fim_temporada(self, times: List[Time]) -> List[Noticia]:
        """Versão corrigida: envelhece e trata aposentadorias sem duplicar contratos."""
        self.noticias = []
        for time in times:
            for j in time.jogadores[:]:
                j.idade += 1
                if j.idade >= IDADE_APOSENTADORIA and random.random() < CHANCE_APOSENTADORIA:
                    self.noticias.append(Noticia(
                        titulo=f"APOSENTADORIA: {j.nome}",
                        texto=f"{j.nome} ({j.idade}) anunciou aposentadoria.",
                        categoria=CategoriaNoticia.GERAL,
                    ))
                    time.jogadores.remove(j)
                    if j.id in time.titulares:
                        time.titulares.remove(j.id)
        return self.noticias
