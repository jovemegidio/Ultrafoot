# -*- coding: utf-8 -*-
"""
Sistemas avançados — Promessas, Vestiário, Química Tática, Carreira,
Adaptação Cultural, Identidade do Clube, Perfis de Agente.
"""
from __future__ import annotations

import random
from typing import List, Dict, Optional, Any

from core.enums import (
    TipoPromessa, StatusPromessa,
    StatusVestiario, TipoEvtVestiario,
    NivelEntrosamento, EstiloClube, TipoAgente, NivelAdaptacao,
    TraitJogador, Posicao,
)
from core.models import (
    Time, Jogador,
    Promessa, CarreiraTreinador, DynamicaVestiario, EventoVestiario,
    QuimicaTatica, IdentidadeClube, PerfilAgente,
    AdaptacaoCultural, ObjetivoPessoalJogador,
)
from utils.logger import get_logger

log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════
#  SISTEMA DE PROMESSAS
# ══════════════════════════════════════════════════════════════

class PromiseEngine:
    """Gerencia promessas feitas a jogadores/diretoria."""

    def __init__(self) -> None:
        self.promessas: List[Promessa] = []
        self._next_id: int = 1

    def fazer_promessa(self, tipo: TipoPromessa, jogador_id: int = 0,
                       jogador_nome: str = "", prazo: int = 12,
                       valor_ref: int = 0, descricao: str = "") -> Promessa:
        desc_auto = {
            TipoPromessa.TITULAR: f"Prometido titularidade a {jogador_nome}",
            TipoPromessa.RENOVAR: f"Prometido renovação a {jogador_nome}",
            TipoPromessa.COMPRAR_REFORCO: "Prometido comprar reforços para o elenco",
            TipoPromessa.VENDER_JOGADOR: f"Prometido vender {jogador_nome}",
            TipoPromessa.AUMENTO_SALARIAL: f"Prometido aumento salarial a {jogador_nome}",
            TipoPromessa.NAO_VENDER: f"Prometido não vender {jogador_nome}",
            TipoPromessa.TITULO: "Prometido disputar o título",
            TipoPromessa.MELHORAR_ELENCO: "Prometido melhorar o elenco",
        }
        p = Promessa(
            id=self._next_id,
            tipo=tipo,
            descricao=descricao or desc_auto.get(tipo, "Promessa"),
            jogador_id=jogador_id,
            jogador_nome=jogador_nome,
            prazo_semanas=prazo,
            semanas_restantes=prazo,
            valor_referencia=valor_ref,
        )
        self._next_id += 1
        self.promessas.append(p)
        return p

    def processar_semana(self, time: Time) -> List[Dict]:
        """Avança promessas e verifica cumprimento. Retorna eventos."""
        eventos = []
        for p in self.promessas:
            if p.status != StatusPromessa.ATIVA:
                continue
            p.semanas_restantes -= 1
            # Verificar cumprimento automático
            cumprida = self._verificar_cumprimento(p, time)
            if cumprida:
                p.status = StatusPromessa.CUMPRIDA
                eventos.append({
                    "tipo": "promessa_cumprida",
                    "descricao": p.descricao,
                    "jogador_id": p.jogador_id,
                })
            elif p.semanas_restantes <= 0:
                p.status = StatusPromessa.QUEBRADA
                eventos.append({
                    "tipo": "promessa_quebrada",
                    "descricao": p.descricao,
                    "jogador_id": p.jogador_id,
                    "penalidade_moral": p.penalidade_moral,
                    "penalidade_reputacao": p.penalidade_reputacao,
                })
                # Aplicar penalidades
                if p.jogador_id:
                    j = time.jogador_por_id(p.jogador_id)
                    if j:
                        j.moral = max(0, j.moral + p.penalidade_moral)
                        j.feliz = False
        return eventos

    def _verificar_cumprimento(self, p: Promessa, time: Time) -> bool:
        if p.tipo == TipoPromessa.TITULAR:
            return p.jogador_id in time.titulares
        if p.tipo == TipoPromessa.RENOVAR:
            j = time.jogador_por_id(p.jogador_id)
            return j is not None and j.contrato.meses_restantes >= 12
        if p.tipo == TipoPromessa.COMPRAR_REFORCO:
            return len(time.jogadores) > p.valor_referencia
        return False

    def promessas_ativas(self) -> List[Promessa]:
        return [p for p in self.promessas if p.status == StatusPromessa.ATIVA]

    def to_save_dict(self) -> Dict:
        return {
            "next_id": self._next_id,
            "promessas": [{
                "id": p.id, "tipo": p.tipo.name, "status": p.status.name,
                "desc": p.descricao, "jid": p.jogador_id,
                "jnome": p.jogador_nome, "prazo": p.prazo_semanas,
                "rest": p.semanas_restantes, "pm": p.penalidade_moral,
                "pr": p.penalidade_reputacao, "vr": p.valor_referencia,
            } for p in self.promessas],
        }

    def from_save_dict(self, d: Dict) -> None:
        self._next_id = d.get("next_id", 1)
        self.promessas = []
        for pd in d.get("promessas", []):
            self.promessas.append(Promessa(
                id=pd["id"],
                tipo=TipoPromessa[pd.get("tipo", "TITULAR")],
                status=StatusPromessa[pd.get("status", "ATIVA")],
                descricao=pd.get("desc", ""),
                jogador_id=pd.get("jid", 0),
                jogador_nome=pd.get("jnome", ""),
                prazo_semanas=pd.get("prazo", 12),
                semanas_restantes=pd.get("rest", 12),
                penalidade_moral=pd.get("pm", -15),
                penalidade_reputacao=pd.get("pr", -5),
                valor_referencia=pd.get("vr", 0),
            ))


# ══════════════════════════════════════════════════════════════
#  DINÂMICA DE VESTIÁRIO
# ══════════════════════════════════════════════════════════════

class LockerRoomEngine:
    """Gerencia a dinâmica de grupo no vestiário."""

    def __init__(self) -> None:
        self.vestiario = DynamicaVestiario()

    def processar_semana(self, time: Time, resultado_semana: Optional[Dict] = None) -> List[Dict]:
        """Processa dinâmica semanal do vestiário."""
        eventos = []
        v = self.vestiario

        # Detectar líder natural (maior liderança entre titulares)
        tits = [j for j in time.jogadores if j.id in time.titulares]
        if tits:
            lider = max(tits, key=lambda j: j.mentais.lideranca)
            v.lider_id = lider.id

        # Efeito Paneleiro — jogador com moral baixa contamina
        for j in time.jogadores:
            if j.tem_trait(TraitJogador.PANELEIRO) and j.moral < 40:
                v.harmonia = max(0, v.harmonia - 3)
                eventos.append({
                    "tipo": "panelinha",
                    "msg": f"{j.nome} está insatisfeito e contaminando o ambiente.",
                })

        # Efeito Líder Nato — melhora harmonia
        for j in time.jogadores:
            if j.tem_trait(TraitJogador.LIDERANCA_NATO) and j.moral >= 60:
                v.harmonia = min(100, v.harmonia + 1)

        # Resultado da semana afeta harmonia
        if resultado_semana:
            tipo = resultado_semana.get("tipo")
            if tipo == "vitoria":
                v.harmonia = min(100, v.harmonia + 3)
                v.coesao = min(100, v.coesao + 2)
                if random.random() < 0.3:
                    eventos.append(self._gerar_evt_uniao(time))
            elif tipo == "goleada_sofrida":
                v.harmonia = max(0, v.harmonia - 5)
                v.coesao = max(0, v.coesao - 3)
                if random.random() < 0.4:
                    eventos.append(self._gerar_evt_conflito(time))
            elif tipo == "derrota":
                v.harmonia = max(0, v.harmonia - 2)
                if random.random() < 0.15:
                    eventos.append(self._gerar_evt_critica(time))

        # Detectar tensões entre jogadores (mesma posição, moral diferente)
        v.tensoes = []
        posicao_grupos: Dict[str, List[Jogador]] = {}
        for j in time.jogadores:
            posicao_grupos.setdefault(j.posicao.name, []).append(j)
        for pos, grupo in posicao_grupos.items():
            if len(grupo) >= 2:
                grupo_sorted = sorted(grupo, key=lambda j: j.moral)
                if grupo_sorted[-1].moral - grupo_sorted[0].moral > 30:
                    v.tensoes.append({
                        "jogador_a": grupo_sorted[0].id,
                        "jogador_b": grupo_sorted[-1].id,
                        "nivel": grupo_sorted[-1].moral - grupo_sorted[0].moral,
                    })

        # Manter apenas últimos 10 eventos
        v.eventos_recentes = v.eventos_recentes[-10:]
        return eventos

    def _gerar_evt_uniao(self, time: Time) -> Dict:
        tits = [j for j in time.jogadores if j.id in time.titulares]
        nomes = [j.nome for j in random.sample(tits, min(3, len(tits)))]
        evt = EventoVestiario(
            tipo=TipoEvtVestiario.UNIAO,
            descricao=f"Grande clima no vestiário! {', '.join(nomes)} comemorando juntos.",
            impacto_moral=5,
        )
        self.vestiario.eventos_recentes.append(evt)
        for j in time.jogadores:
            j.moral = min(100, j.moral + 2)
        return {"tipo": "uniao", "msg": evt.descricao}

    def _gerar_evt_conflito(self, time: Time) -> Dict:
        insatisfeitos = [j for j in time.jogadores if j.moral < 50]
        if not insatisfeitos:
            insatisfeitos = time.jogadores[:2]
        j1 = random.choice(insatisfeitos)
        evt = EventoVestiario(
            tipo=TipoEvtVestiario.CONFLITO,
            descricao=f"{j1.nome} demonstrou insatisfação no vestiário após a derrota.",
            jogadores_envolvidos=[j1.id],
            impacto_moral=-5,
        )
        self.vestiario.eventos_recentes.append(evt)
        j1.moral = max(0, j1.moral - 5)
        return {"tipo": "conflito", "msg": evt.descricao}

    def _gerar_evt_critica(self, time: Time) -> Dict:
        j = random.choice(time.jogadores) if time.jogadores else None
        if not j:
            return {"tipo": "critica", "msg": "Tensão no vestiário."}
        evt = EventoVestiario(
            tipo=TipoEvtVestiario.CRITICA,
            descricao=f"{j.nome} criticou o desempenho coletivo em entrevista.",
            jogadores_envolvidos=[j.id],
            impacto_moral=-3,
        )
        self.vestiario.eventos_recentes.append(evt)
        return {"tipo": "critica", "msg": evt.descricao}

    def to_save_dict(self) -> Dict:
        v = self.vestiario
        return {
            "harmonia": v.harmonia, "coesao": v.coesao,
            "lider_id": v.lider_id,
            "tensoes": v.tensoes,
            "eventos": [{
                "tipo": e.tipo.name, "desc": e.descricao,
                "jids": e.jogadores_envolvidos, "imp": e.impacto_moral,
                "sem": e.semana,
            } for e in v.eventos_recentes[-10:]],
        }

    def from_save_dict(self, d: Dict) -> None:
        v = self.vestiario
        v.harmonia = d.get("harmonia", 70)
        v.coesao = d.get("coesao", 60)
        v.lider_id = d.get("lider_id", 0)
        v.tensoes = d.get("tensoes", [])
        v.eventos_recentes = []
        for ed in d.get("eventos", []):
            v.eventos_recentes.append(EventoVestiario(
                tipo=TipoEvtVestiario[ed.get("tipo", "UNIAO")],
                descricao=ed.get("desc", ""),
                jogadores_envolvidos=ed.get("jids", []),
                impacto_moral=ed.get("imp", 0),
                semana=ed.get("sem", 0),
            ))


# ══════════════════════════════════════════════════════════════
#  QUÍMICA TÁTICA / ENTROSAMENTO
# ══════════════════════════════════════════════════════════════

class TacticalChemistryEngine:
    """Gerencia entrosamento tático do time."""

    def __init__(self) -> None:
        self.quimica = QuimicaTatica()

    def processar_semana(self, time: Time) -> None:
        q = self.quimica
        form_atual = time.tatica.formacao.value

        if form_atual == q.formacao_usada:
            q.semanas_mesma_formacao += 1
            q.familiaridade_formacao = min(100, q.familiaridade_formacao + 2)
        else:
            q.semanas_mesma_formacao = 0
            q.familiaridade_formacao = max(20, q.familiaridade_formacao - 15)
            q.formacao_usada = form_atual

        # Parcerias entre titulares que jogam juntos
        tit_ids = set(time.titulares)
        for p in q.parcerias:
            if p["j1_id"] in tit_ids and p["j2_id"] in tit_ids:
                p["nivel"] = min(100, p["nivel"] + 1)
            else:
                p["nivel"] = max(0, p["nivel"] - 1)

        # Criar novas parcerias para pares de titulares adjacentes
        tits = [j for j in time.jogadores if j.id in tit_ids]
        existing_pairs = {(p["j1_id"], p["j2_id"]) for p in q.parcerias}
        for i, ja in enumerate(tits):
            for jb in tits[i + 1:]:
                if self._sao_adjacentes(ja, jb):
                    pair = (min(ja.id, jb.id), max(ja.id, jb.id))
                    if pair not in existing_pairs:
                        q.parcerias.append({"j1_id": pair[0], "j2_id": pair[1], "nivel": 20})
                        existing_pairs.add(pair)

        # Limitar parcerias (remover as mais fracas se muitas)
        if len(q.parcerias) > 30:
            q.parcerias.sort(key=lambda p: p["nivel"], reverse=True)
            q.parcerias = q.parcerias[:30]

        # Calcular entrosamento geral
        if q.parcerias:
            media_parc = sum(p["nivel"] for p in q.parcerias) / len(q.parcerias)
        else:
            media_parc = 30
        q.entrosamento_geral = int(q.familiaridade_formacao * 0.5 + media_parc * 0.5)

    def _sao_adjacentes(self, ja: Jogador, jb: Jogador) -> bool:
        """Verifica se dois jogadores atuam em setores adjacentes."""
        setores = {
            Posicao.GOL: 0, Posicao.ZAG: 1, Posicao.LD: 1, Posicao.LE: 1,
            Posicao.VOL: 2, Posicao.MC: 2, Posicao.ME: 2, Posicao.MD: 2,
            Posicao.MEI: 3, Posicao.PE: 3, Posicao.PD: 3,
            Posicao.CA: 4, Posicao.SA: 4,
        }
        sa = setores.get(ja.posicao, 2)
        sb = setores.get(jb.posicao, 2)
        return abs(sa - sb) <= 1

    def to_save_dict(self) -> Dict:
        q = self.quimica
        return {
            "fam": q.familiaridade_formacao,
            "form": q.formacao_usada,
            "sem": q.semanas_mesma_formacao,
            "parc": q.parcerias,
            "ent": q.entrosamento_geral,
        }

    def from_save_dict(self, d: Dict) -> None:
        q = self.quimica
        q.familiaridade_formacao = d.get("fam", 50)
        q.formacao_usada = d.get("form", "4-4-2")
        q.semanas_mesma_formacao = d.get("sem", 0)
        q.parcerias = d.get("parc", [])
        q.entrosamento_geral = d.get("ent", 50)


# ══════════════════════════════════════════════════════════════
#  CARREIRA DO TREINADOR
# ══════════════════════════════════════════════════════════════

class CoachCareerEngine:
    """Gerencia legado e carreira do treinador."""

    def __init__(self) -> None:
        self.carreira = CarreiraTreinador()

    def registrar_semana(self, time: Time, resultados: Dict) -> None:
        c = self.carreira
        c.experiencia += 1
        nome = time.nome
        for comp, lista in resultados.items():
            for r in lista:
                if r.time_casa == nome:
                    if r.gols_casa > r.gols_fora:
                        c.vitorias_total += 1
                    elif r.gols_casa == r.gols_fora:
                        c.empates_total += 1
                    else:
                        c.derrotas_total += 1
                elif r.time_fora == nome:
                    if r.gols_fora > r.gols_casa:
                        c.vitorias_total += 1
                    elif r.gols_fora == r.gols_casa:
                        c.empates_total += 1
                    else:
                        c.derrotas_total += 1

    def registrar_titulo(self, titulo_nome: str, temporada: int, time_nome: str) -> None:
        self.carreira.titulos.append({
            "nome": titulo_nome, "temporada": temporada, "time": time_nome,
        })
        self.carreira.reputacao = min(100, self.carreira.reputacao + 5)

    def registrar_demissao(self, time_nome: str, semanas: int, motivo: str = "demissao") -> None:
        self.carreira.times_anteriores.append({
            "nome": time_nome, "semanas": semanas, "motivo_saida": motivo,
        })
        if motivo == "demissao":
            self.carreira.reputacao = max(0, self.carreira.reputacao - 10)
        else:
            self.carreira.reputacao = max(0, self.carreira.reputacao - 3)

    def registrar_novo_time(self, time_nome: str, old_time: str, semanas: int) -> None:
        if old_time:
            self.carreira.times_anteriores.append({
                "nome": old_time, "semanas": semanas, "motivo_saida": "resignou",
            })

    def atualizar_reputacao_semanal(self, time: Time) -> None:
        """Ajuste sutil de reputação baseado em resultados recentes."""
        c = self.carreira
        jogos = time.vitorias + time.empates + time.derrotas
        if jogos < 3:
            return
        aprov = (time.vitorias * 3 + time.empates) / (jogos * 3) if jogos else 0
        if aprov > 0.65:
            c.reputacao = min(100, c.reputacao + 1)
        elif aprov < 0.30:
            c.reputacao = max(0, c.reputacao - 1)

    def to_save_dict(self) -> Dict:
        c = self.carreira
        return {
            "nome": c.nome, "rep": c.reputacao, "exp": c.experiencia,
            "tit": c.titulos, "times_ant": c.times_anteriores,
            "v": c.vitorias_total, "e": c.empates_total, "d": c.derrotas_total,
            "mp": c.melhor_posicao, "pp": c.pior_posicao,
            "est": c.estilo_preferido, "espec": c.especialidade,
        }

    def from_save_dict(self, d: Dict) -> None:
        c = self.carreira
        c.nome = d.get("nome", "Treinador")
        c.reputacao = d.get("rep", 50)
        c.experiencia = d.get("exp", 0)
        c.titulos = d.get("tit", [])
        c.times_anteriores = d.get("times_ant", [])
        c.vitorias_total = d.get("v", 0)
        c.empates_total = d.get("e", 0)
        c.derrotas_total = d.get("d", 0)
        c.melhor_posicao = d.get("mp", "")
        c.pior_posicao = d.get("pp", "")
        c.estilo_preferido = d.get("est", "equilibrado")
        c.especialidade = d.get("espec", "")


# ══════════════════════════════════════════════════════════════
#  ADAPTAÇÃO CULTURAL
# ══════════════════════════════════════════════════════════════

class CulturalAdaptationEngine:
    """Gerencia adaptação de jogadores estrangeiros."""

    # Afinidades culturais (mais fácil adaptar)
    _AFINIDADES = {
        "Brasil": {"Portugal", "Argentina", "Colômbia", "Uruguai", "Chile", "Paraguai"},
        "Argentina": {"Brasil", "Uruguai", "Paraguai", "Chile", "Colômbia"},
        "Espanha": {"Argentina", "Colômbia", "México", "Portugal", "Chile"},
        "Portugal": {"Brasil", "Espanha", "Angola", "Moçambique"},
        "Inglaterra": {"Escócia", "Irlanda", "EUA", "Austrália"},
        "Alemanha": {"Áustria", "Suíça", "Holanda"},
        "França": {"Bélgica", "Suíça", "Senegal", "Costa do Marfim"},
        "Itália": {"Argentina", "Espanha", "Portugal"},
    }

    def __init__(self) -> None:
        self.adaptacoes: List[AdaptacaoCultural] = []

    def registrar_transferencia(self, jogador: Jogador, pais_destino: str = "Brasil") -> None:
        """Registra que um jogador estrangeiro chegou ao país."""
        if jogador.nacionalidade == pais_destino:
            return
        # Verificar se já tem adaptação
        for a in self.adaptacoes:
            if a.jogador_id == jogador.id:
                return
        afinidades = self._AFINIDADES.get(pais_destino, set())
        progresso_inicial = 50 if jogador.nacionalidade in afinidades else 20
        self.adaptacoes.append(AdaptacaoCultural(
            jogador_id=jogador.id,
            pais_origem=jogador.nacionalidade,
            pais_atual=pais_destino,
            progresso=progresso_inicial,
            fala_idioma=jogador.nacionalidade in afinidades,
        ))

    def processar_semana(self) -> List[Dict]:
        eventos = []
        for a in self.adaptacoes:
            a.semanas_no_pais += 1
            ganho = 2
            if a.fala_idioma:
                ganho += 1
            if a.tem_familia:
                ganho += 1
            a.progresso = min(100, a.progresso + ganho)
            # Atualizar nível
            if a.progresso >= 90:
                old_nivel = a.nivel
                a.nivel = NivelAdaptacao.TOTALMENTE_ADAPTADO
                a.penalidade_overall = 0
                if old_nivel != NivelAdaptacao.TOTALMENTE_ADAPTADO:
                    eventos.append({
                        "tipo": "adaptacao_completa",
                        "jogador_id": a.jogador_id,
                    })
            elif a.progresso >= 60:
                a.nivel = NivelAdaptacao.ADAPTADO
                a.penalidade_overall = -2
            elif a.progresso >= 30:
                a.nivel = NivelAdaptacao.EM_ADAPTACAO
                a.penalidade_overall = -5
            else:
                a.nivel = NivelAdaptacao.INADAPTADO
                a.penalidade_overall = -8
        # Remover adaptações completas com progresso 100
        self.adaptacoes = [a for a in self.adaptacoes if a.progresso < 100]
        return eventos

    def get_adaptacao(self, jogador_id: int) -> Optional[AdaptacaoCultural]:
        for a in self.adaptacoes:
            if a.jogador_id == jogador_id:
                return a
        return None

    def fator_rendimento(self, jogador_id: int) -> float:
        a = self.get_adaptacao(jogador_id)
        return a.fator_rendimento if a else 1.0

    def to_save_dict(self) -> Dict:
        return {
            "adaptacoes": [{
                "jid": a.jogador_id, "po": a.pais_origem, "pa": a.pais_atual,
                "niv": a.nivel.name, "prog": a.progresso, "sem": a.semanas_no_pais,
                "idioma": a.fala_idioma, "fam": a.tem_familia, "pen": a.penalidade_overall,
            } for a in self.adaptacoes],
        }

    def from_save_dict(self, d: Dict) -> None:
        self.adaptacoes = []
        for ad in d.get("adaptacoes", []):
            self.adaptacoes.append(AdaptacaoCultural(
                jogador_id=ad.get("jid", 0),
                pais_origem=ad.get("po", ""),
                pais_atual=ad.get("pa", "Brasil"),
                nivel=NivelAdaptacao[ad.get("niv", "EM_ADAPTACAO")],
                progresso=ad.get("prog", 30),
                semanas_no_pais=ad.get("sem", 0),
                fala_idioma=ad.get("idioma", False),
                tem_familia=ad.get("fam", True),
                penalidade_overall=ad.get("pen", -5),
            ))


# ══════════════════════════════════════════════════════════════
#  IDENTIDADE DO CLUBE
# ══════════════════════════════════════════════════════════════

class ClubIdentityEngine:
    """Atribui e gerencia a identidade/DNA do clube."""

    _ESTILOS_POR_TIPO = {
        "grande_br": EstiloClube.OFENSIVO,
        "grande_posse": EstiloClube.POSSE_DE_BOLA,
        "medio_br": EstiloClube.CONTRA_ATAQUE,
        "pequeno_br": EstiloClube.DEFENSIVO,
        "formador": EstiloClube.BASE_FORTE,
        "rico": EstiloClube.COMPRADOR,
    }

    def atribuir_identidade(self, time: Time) -> IdentidadeClube:
        """Define identidade com base no perfil do clube."""
        ident = IdentidadeClube()
        if time.prestigio >= 80:
            ident.estilo = EstiloClube.OFENSIVO
            ident.torcida_exigente = True
        elif time.prestigio >= 60:
            ident.estilo = random.choice([EstiloClube.POSSE_DE_BOLA, EstiloClube.CONTRA_ATAQUE])
        else:
            ident.estilo = random.choice([EstiloClube.DEFENSIVO, EstiloClube.JOGO_DIRETO, EstiloClube.BASE_FORTE])

        ident.formacao_raiz = time.tatica.formacao.value
        ident.valoriza_base = time.base_juvenil.nivel >= 60
        return ident

    def verificar_aderencia(self, time: Time, identidade: IdentidadeClube) -> float:
        """Retorna 0-1 de quanto o técnico adere à identidade do clube."""
        score = 0.5
        est = time.tatica.estilo.name
        if identidade.estilo == EstiloClube.OFENSIVO and est in ("OFENSIVO", "MUITO_OFENSIVO"):
            score += 0.3
        elif identidade.estilo == EstiloClube.DEFENSIVO and est in ("DEFENSIVO", "MUITO_DEFENSIVO"):
            score += 0.3
        elif identidade.estilo == EstiloClube.POSSE_DE_BOLA and time.tatica.toque_curto:
            score += 0.3
        elif identidade.estilo == EstiloClube.CONTRA_ATAQUE and time.tatica.contra_ataque:
            score += 0.3
        if identidade.valoriza_base:
            jovens = [j for j in time.jogadores if j.idade <= 21 and j.id in time.titulares]
            if len(jovens) >= 2:
                score += 0.2
        return min(1.0, score)


# ══════════════════════════════════════════════════════════════
#  PERFIS DE AGENTE
# ══════════════════════════════════════════════════════════════

class AgentProfileEngine:
    """Gerencia perfis de agentes/empresários."""

    _NOMES = [
        "Jorge Mendes", "Mino Raiola Jr", "Giuliano Bertolucci",
        "Wagner Ribeiro", "Fernando Felicevich", "Pini Zahavi",
        "Jonathan Barnett", "Volker Struth", "Eduardo Uram",
        "Marcos Motta", "André Cury", "Kia Joorabchian",
        "Fabio Giuffrida", "Bruno Macedo", "Nicolas Anelka Jr",
    ]

    def __init__(self) -> None:
        self.agentes: List[PerfilAgente] = []
        self._gerados = False

    def gerar_agentes(self, todos_jogadores_ids: List[int]) -> None:
        """Gera pool de agentes e atribui jogadores."""
        if self._gerados:
            return
        n_agentes = min(12, max(5, len(todos_jogadores_ids) // 200))
        nomes = random.sample(self._NOMES, min(n_agentes, len(self._NOMES)))
        tipos = list(TipoAgente)
        for i, nome in enumerate(nomes):
            ag = PerfilAgente(
                nome=nome,
                tipo=random.choice(tipos),
                influencia=random.randint(30, 90),
                comissao_pct=round(random.uniform(0.05, 0.15), 2),
                dificuldade_negociacao=random.randint(20, 80),
            )
            self.agentes.append(ag)
        # Distribui jogadores entre agentes
        random.shuffle(todos_jogadores_ids)
        for i, jid in enumerate(todos_jogadores_ids):
            agente = self.agentes[i % len(self.agentes)]
            agente.jogadores_representados.append(jid)
        self._gerados = True

    def get_agente_jogador(self, jogador_id: int) -> Optional[PerfilAgente]:
        for ag in self.agentes:
            if jogador_id in ag.jogadores_representados:
                return ag
        return None

    def multiplicador_negociacao(self, jogador_id: int) -> float:
        ag = self.get_agente_jogador(jogador_id)
        return ag.multiplicador_pedido if ag else 1.0

    def to_save_dict(self) -> Dict:
        return {
            "gerados": self._gerados,
            "agentes": [{
                "nome": a.nome, "tipo": a.tipo.name, "inf": a.influencia,
                "com": a.comissao_pct, "dif": a.dificuldade_negociacao,
                "jids": a.jogadores_representados,
            } for a in self.agentes],
        }

    def from_save_dict(self, d: Dict) -> None:
        self._gerados = d.get("gerados", False)
        self.agentes = []
        for ad in d.get("agentes", []):
            self.agentes.append(PerfilAgente(
                nome=ad.get("nome", ""),
                tipo=TipoAgente[ad.get("tipo", "AMIGAVEL")],
                influencia=ad.get("inf", 50),
                comissao_pct=ad.get("com", 0.10),
                dificuldade_negociacao=ad.get("dif", 50),
                jogadores_representados=ad.get("jids", []),
            ))


# ══════════════════════════════════════════════════════════════
#  OBJETIVOS PESSOAIS DOS JOGADORES
# ══════════════════════════════════════════════════════════════

class PlayerObjectivesEngine:
    """Gerencia objetivos pessoais dos jogadores."""

    def __init__(self) -> None:
        self.objetivos: List[ObjetivoPessoalJogador] = []

    def gerar_objetivos_temporada(self, time: Time) -> None:
        """Gera objetivos individuais no início da temporada."""
        self.objetivos = []
        for j in time.jogadores:
            tipo, meta, desc = self._escolher_objetivo(j)
            self.objetivos.append(ObjetivoPessoalJogador(
                jogador_id=j.id,
                descricao=desc,
                tipo=tipo,
                meta=meta,
            ))

    def _escolher_objetivo(self, j: Jogador):
        if j.posicao in (Posicao.CA, Posicao.SA, Posicao.PD, Posicao.PE):
            meta = random.randint(5, 20)
            return "gols", meta, f"Marcar {meta} gols na temporada"
        elif j.posicao in (Posicao.MEI, Posicao.MC, Posicao.ME, Posicao.MD):
            meta = random.randint(5, 15)
            return "assists", meta, f"Dar {meta} assistências na temporada"
        elif j.posicao in (Posicao.ZAG, Posicao.LD, Posicao.LE, Posicao.VOL):
            return "titular", 20, "Ser titular em 20 jogos"
        else:
            return "titular", 15, "Ser titular em 15 jogos"

    def atualizar_progresso(self, time: Time, resultados: Dict) -> List[Dict]:
        eventos = []
        nome = time.nome
        for obj in self.objetivos:
            j = time.jogador_por_id(obj.jogador_id)
            if not j:
                continue
            if obj.tipo == "gols":
                obj.progresso = j.historico_temporada.gols
            elif obj.tipo == "assists":
                obj.progresso = j.historico_temporada.assistencias
            elif obj.tipo == "titular":
                obj.progresso = j.historico_temporada.jogos
            if obj.progresso >= obj.meta:
                eventos.append({
                    "tipo": "objetivo_atingido",
                    "jogador_id": obj.jogador_id,
                    "descricao": obj.descricao,
                })
                j.moral = min(100, j.moral + obj.impacto_moral_sucesso)
        return eventos

    def to_save_dict(self) -> Dict:
        return {
            "objs": [{
                "jid": o.jogador_id, "desc": o.descricao, "tipo": o.tipo,
                "meta": o.meta, "prog": o.progresso,
                "ims": o.impacto_moral_sucesso, "imf": o.impacto_moral_falha,
            } for o in self.objetivos],
        }

    def from_save_dict(self, d: Dict) -> None:
        self.objetivos = []
        for od in d.get("objs", []):
            self.objetivos.append(ObjetivoPessoalJogador(
                jogador_id=od.get("jid", 0),
                descricao=od.get("desc", ""),
                tipo=od.get("tipo", "gols"),
                meta=od.get("meta", 10),
                progresso=od.get("prog", 0),
                impacto_moral_sucesso=od.get("ims", 15),
                impacto_moral_falha=od.get("imf", -10),
            ))


# ══════════════════════════════════════════════════════════════
#  DEADLINE DAY — último dia da janela de transferências
# ══════════════════════════════════════════════════════════════

class DeadlineDayEngine:
    """Gera eventos dramáticos no último dia da janela de transferências."""

    def processar_deadline(self, todos_times: List[Time],
                           time_jogador: Optional[Time],
                           mercado) -> List[Dict]:
        """Chamado na última semana de cada janela. Retorna eventos."""
        eventos: List[Dict] = []

        # IA faz ofertas de última hora com urgência
        for _ in range(random.randint(3, 8)):
            comprador = random.choice(todos_times)
            vendedor = random.choice([t for t in todos_times if t.nome != comprador.nome])
            alvo = None
            for j in vendedor.jogadores:
                if j.overall >= 60 and not j.quer_sair:
                    alvo = j
                    break
            if not alvo:
                continue

            # Oferta 20-50% acima do mercado (desespero deadline)
            fator = random.uniform(1.2, 1.5)
            valor = int(alvo.valor_mercado * fator)

            aceito = random.random() < 0.35  # 35% chance de aceitar no deadline
            eventos.append({
                "tipo": "deadline_oferta",
                "comprador": comprador.nome,
                "vendedor": vendedor.nome,
                "jogador": alvo.nome,
                "valor": valor,
                "aceito": aceito,
                "urgente": True,
            })

            if aceito:
                # Efetuar transferência
                vendedor.jogadores.remove(alvo)
                if alvo.id in vendedor.titulares:
                    vendedor.titulares.remove(alvo.id)
                comprador.jogadores.append(alvo)
                vendedor.financas.saldo += valor
                comprador.financas.saldo -= valor
                eventos.append({
                    "tipo": "deadline_fechado",
                    "comprador": comprador.nome,
                    "jogador": alvo.nome,
                    "valor": valor,
                })

        # Ofertas surpresa para o jogador humano
        if time_jogador:
            for j in time_jogador.jogadores:
                if j.overall >= 70 and random.random() < 0.15:
                    clube = random.choice([t for t in todos_times
                                          if t.nome != time_jogador.nome])
                    valor = int(j.valor_mercado * random.uniform(1.3, 1.8))
                    eventos.append({
                        "tipo": "deadline_oferta_recebida",
                        "de": clube.nome,
                        "jogador": j.nome,
                        "jogador_id": j.id,
                        "valor": valor,
                    })

        return eventos


# ══════════════════════════════════════════════════════════════
#  REUNIÕES DE STAFF — análise semanal da comissão técnica
# ══════════════════════════════════════════════════════════════

class StaffMeetingEngine:
    """Gera reuniões periódicas com a comissão técnica (FM-style)."""

    def gerar_reuniao(self, time: Time, semana: int,
                      resultados_recentes: List = None) -> Optional[Dict]:
        """Gera reunião de staff a cada 4 semanas."""
        if semana % 4 != 0:
            return None

        itens: List[Dict] = []

        # 1. Preparador físico: relatório de condição
        preparador = time.staff_por_tipo(TipoStaff.PREPARADOR)
        fatigados = [j for j in time.jogadores
                     if j.condicao_fisica < 60 and j.pode_jogar()]
        if fatigados:
            nomes = [j.nome for j in fatigados[:3]]
            itens.append({
                "remetente": "Preparador Físico",
                "tipo": "fadiga",
                "mensagem": f"Atenção: {', '.join(nomes)} estão com condição "
                            f"física baixa. Recomendo reduzir intensidade do treino.",
                "acao": "reduzir_treino",
            })

        # 2. Médico: relatório de lesões
        medico = time.staff_por_tipo(TipoStaff.MEDICO)
        lesionados = [j for j in time.jogadores
                      if j.status_lesao.name != "SAUDAVEL"]
        if lesionados:
            for j in lesionados[:2]:
                itens.append({
                    "remetente": "Departamento Médico",
                    "tipo": "lesao",
                    "mensagem": f"{j.nome} — {j.status_lesao.value}, "
                                f"previsão de {j.dias_lesao} dias para retorno.",
                    "acao": None,
                })

        # 3. Scout: recomendação de reforço
        scout = time.staff_por_tipo(TipoStaff.SCOUT)
        if scout:
            posicoes_fracas = self._detectar_posicoes_fracas(time)
            if posicoes_fracas:
                itens.append({
                    "remetente": "Olheiro",
                    "tipo": "recomendacao",
                    "mensagem": f"Detectei carência na posição de "
                                f"{posicoes_fracas[0]}. Recomendo buscar reforço.",
                    "acao": "abrir_mercado",
                })

        # 4. Auxiliar: análise tática
        auxiliar = time.staff_por_tipo(TipoStaff.AUXILIAR)
        if auxiliar and resultados_recentes:
            derrotas = sum(1 for r in resultados_recentes[-5:]
                          if r.get("resultado") == "derrota")
            if derrotas >= 3:
                itens.append({
                    "remetente": "Auxiliar Técnico",
                    "tipo": "tatica",
                    "mensagem": "Estamos em má fase. Sugiro mudar a formação "
                                "ou o estilo de jogo para quebrar a sequência.",
                    "acao": "mudar_tatica",
                })

        # 5. Diretor: situação financeira
        if time.financas.saldo < 0:
            itens.append({
                "remetente": "Diretor de Futebol",
                "tipo": "financeiro",
                "mensagem": f"Atenção: saldo negativo de "
                            f"R$ {abs(time.financas.saldo):,.0f}. "
                            f"Precisamos vender jogadores ou cortar custos.",
                "acao": "vender_jogador",
            })

        # 6. Treinador de goleiros
        treinador_gol = time.staff_por_tipo(TipoStaff.TREINADOR_GOL)
        goleiros = [j for j in time.jogadores if j.posicao.name == "GOL"]
        if treinador_gol and goleiros:
            melhor_gol = max(goleiros, key=lambda g: g.overall)
            if melhor_gol.overall < 65:
                itens.append({
                    "remetente": "Treinador de Goleiros",
                    "tipo": "recomendacao",
                    "mensagem": f"Nosso goleiro titular {melhor_gol.nome} "
                                f"(OVR {melhor_gol.overall}) está abaixo do "
                                f"nível ideal. Recomendo buscar um substituto.",
                    "acao": "abrir_mercado",
                })

        if not itens:
            return None

        return {
            "semana": semana,
            "titulo": "Reunião da Comissão Técnica",
            "itens": itens,
        }

    @staticmethod
    def _detectar_posicoes_fracas(time: Time) -> List[str]:
        """Detecta posições com poucos jogadores ou baixo overall."""
        contagem: Dict[str, List[int]] = {}
        for j in time.jogadores:
            pos = j.posicao.value
            contagem.setdefault(pos, []).append(j.overall)
        fracas = []
        for pos, overalls in contagem.items():
            if len(overalls) < 2 or max(overalls) < 60:
                fracas.append(pos)
        return fracas


# ══════════════════════════════════════════════════════════════
#  NEWGEN AVATAR — geração procedural de aparência
# ══════════════════════════════════════════════════════════════

class NewgenAvatarEngine:
    """Gera aparência procedural para jogadores revelados/regens."""

    # Cores de pele por região
    _SKIN_TONES = {
        "Brasil": ["#8D5524", "#C68642", "#F1C27D", "#6B3E26", "#FFDBAC", "#D4A574"],
        "Argentina": ["#FFDBAC", "#F1C27D", "#C68642", "#E0AC69"],
        "Europa": ["#FFDBAC", "#F1C27D", "#FFE0BD", "#E0AC69"],
        "Africa": ["#8D5524", "#6B3E26", "#4E2A0A", "#7C4A1E"],
        "Asia": ["#F1C27D", "#FFDBAC", "#D4A574", "#C68642"],
        "default": ["#C68642", "#F1C27D", "#FFDBAC", "#8D5524"],
    }

    _HAIR_COLORS = ["#1C1C1C", "#3B2F2F", "#654321", "#8B4513",
                     "#DAA520", "#B8860B", "#FFFDD0", "#FF4500"]

    _HAIR_STYLES = ["curto", "medio", "longo", "raspado", "moicano",
                     "black_power", "dreadlocks", "careca", "topete",
                     "crespo", "coque", "tranças"]

    _FACE_SHAPES = ["oval", "redondo", "quadrado", "losango", "triangular"]

    _BEARD_TYPES = ["sem", "cavanhaque", "barba_cheia", "barba_rala",
                     "bigode", "costeleta"]

    def gerar_avatar(self, jogador: Jogador) -> Dict:
        """Gera aparência procedural baseada em nacionalidade e seed do jogador."""
        rng = random.Random(jogador.id * 31 + hash(jogador.nome))

        # Selecionar tons de pele por nacionalidade
        region = "default"
        nac = jogador.nacionalidade
        if nac in ("Brasil",):
            region = "Brasil"
        elif nac in ("Argentina", "Uruguai", "Chile", "Paraguai"):
            region = "Argentina"
        elif nac in ("Nigéria", "Senegal", "Gana", "Camarões", "Costa do Marfim",
                      "África do Sul", "Marrocos", "Egito"):
            region = "Africa"
        elif nac in ("Japão", "China", "Coreia do Sul"):
            region = "Asia"
        elif nac in ("Inglaterra", "França", "Alemanha", "Espanha", "Itália",
                      "Portugal", "Holanda", "Bélgica", "Suíça", "Croácia",
                      "Sérvia", "Áustria", "Suécia", "Noruega", "Dinamarca",
                      "Rússia", "Turquia", "Ucrânia", "Grécia"):
            region = "Europa"

        tones = self._SKIN_TONES[region]

        # Deterministic but varied
        skin = rng.choice(tones)
        hair_color = rng.choice(self._HAIR_COLORS)
        hair_style = rng.choice(self._HAIR_STYLES)
        face = rng.choice(self._FACE_SHAPES)
        beard = rng.choice(self._BEARD_TYPES)
        altura_cm = int(jogador.altura * 100)

        # Acessórios
        headband = rng.random() < 0.08
        glasses = False  # jogadores não usam óculos
        sleeve_tattoo = rng.random() < 0.25
        wristband = rng.random() < 0.15

        return {
            "skin_tone": skin,
            "hair_color": hair_color,
            "hair_style": hair_style,
            "face_shape": face,
            "beard": beard,
            "height_cm": altura_cm,
            "weight_kg": int(jogador.peso),
            "headband": headband,
            "sleeve_tattoo": sleeve_tattoo,
            "wristband": wristband,
            "seed": jogador.id,
        }


# ══════════════════════════════════════════════════════════════
#  ANÁLISE PÓS-JOGO INTELIGENTE
# ══════════════════════════════════════════════════════════════

class PostMatchAnalysisEngine:
    """Gera análise tática inteligente pós-jogo."""

    def analisar(self, resultado, time_jogador_nome: str,
                 casa_time=None, fora_time=None) -> Dict:
        """Gera análise completa do jogo."""
        r = resultado
        eh_casa = r.time_casa == time_jogador_nome
        meu_gols = r.gols_casa if eh_casa else r.gols_fora
        adv_gols = r.gols_fora if eh_casa else r.gols_casa
        meu_fin = r.finalizacoes_casa if eh_casa else r.finalizacoes_fora
        adv_fin = r.finalizacoes_fora if eh_casa else r.finalizacoes_casa
        meu_fin_gol = r.finalizacoes_gol_casa if eh_casa else r.finalizacoes_gol_fora
        adv_fin_gol = r.finalizacoes_gol_fora if eh_casa else r.finalizacoes_gol_casa

        # xG estimado baseado em finalizações no gol
        xg_meu = round(meu_fin_gol * 0.35 + (meu_fin - meu_fin_gol) * 0.08, 2)
        xg_adv = round(adv_fin_gol * 0.35 + (adv_fin - adv_fin_gol) * 0.08, 2)

        posse_meu = r.posse_casa if eh_casa else round(100 - r.posse_casa, 1)
        dominio = "casa" if r.posse_casa > 55 else "fora" if r.posse_casa < 45 else "equilibrado"

        # Recomendações
        recomendacoes = []
        if meu_gols < xg_meu - 0.5:
            recomendacoes.append("Falta eficiência nas finalizações. Considere treinar finalização.")
        if adv_gols > xg_adv + 0.5:
            recomendacoes.append("O adversário foi mais eficiente que o esperado. Reforçar a defesa.")
        if posse_meu < 40:
            recomendacoes.append("Pouca posse de bola. Considere toque curto e mais meio-campistas.")
        if meu_fin < 5:
            recomendacoes.append("Poucas finalizações. Tente um estilo mais ofensivo.")
        faltas_meu = r.faltas_casa if eh_casa else r.faltas_fora
        if faltas_meu > 15:
            recomendacoes.append("Muitas faltas cometidas. Risco de cartões. Reduza a agressividade.")
        if meu_gols > adv_gols:
            recomendacoes.append("Ótima vitória! Mantenha a estratégia atual.")
        elif meu_gols == adv_gols:
            recomendacoes.append("Empate. Analise se faltou ambição ofensiva ou sobrou vulnerabilidade defensiva.")

        # Notas táticas
        notas = []
        if posse_meu > 60:
            notas.append(f"Domínio territorial claro ({posse_meu}% de posse).")
        if meu_fin_gol > 5:
            notas.append(f"Alta precisão nas finalizações ({meu_fin_gol} no gol de {meu_fin} totais).")

        # Jogador destaque/fraco
        destaque = ""
        fraco = ""
        notas_j = r.notas_jogadores or {}
        if notas_j:
            time_ref = casa_time if eh_casa else fora_time
            if time_ref:
                meus_ids = set(time_ref.titulares)
                meus_notas = {jid: nota for jid, nota in notas_j.items() if jid in meus_ids}
                if meus_notas:
                    best_id = max(meus_notas, key=meus_notas.get)
                    worst_id = min(meus_notas, key=meus_notas.get)
                    j_best = time_ref.jogador_por_id(best_id)
                    j_worst = time_ref.jogador_por_id(worst_id)
                    if j_best:
                        destaque = f"{j_best.nome} ({meus_notas[best_id]:.1f})"
                    if j_worst:
                        fraco = f"{j_worst.nome} ({meus_notas[worst_id]:.1f})"

        return {
            "xg_meu": xg_meu, "xg_adv": xg_adv,
            "posse_meu": posse_meu,
            "dominio": dominio,
            "finalizacoes_meu": meu_fin,
            "finalizacoes_gol_meu": meu_fin_gol,
            "recomendacoes": recomendacoes,
            "notas_taticas": notas,
            "destaque": destaque,
            "fraco": fraco,
            "resultado": "vitoria" if meu_gols > adv_gols else "empate" if meu_gols == adv_gols else "derrota",
        }
