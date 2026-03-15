# -*- coding: utf-8 -*-
"""
Sistema de conquistas/achievements e premiações de fim de temporada.
"""
from __future__ import annotations

import random
from typing import List, Dict, Optional, TYPE_CHECKING

from core.enums import CategoriaConquista, TipoPremio, CategoriaNoticia
from core.models import Conquista, PremiacaoTemporada, Noticia
from utils.logger import get_logger

if TYPE_CHECKING:
    from core.models import Time, Jogador

log = get_logger(__name__)

# ══════════════════════════════════════════════════════════════
#  DEFINIÇÃO DE CONQUISTAS
# ══════════════════════════════════════════════════════════════

CONQUISTAS_DEFINICAO: List[Dict] = [
    # Títulos
    {"id": "primeiro_titulo", "titulo": "Primeiro de Muitos", "descricao": "Conquiste seu primeiro título.", "icone": "🏆", "cat": "titulo", "meta": 1},
    {"id": "penta", "titulo": "Pentacampeão", "descricao": "Conquiste 5 títulos.", "icone": "🏆", "cat": "titulo", "meta": 5},
    {"id": "deca", "titulo": "Década de Glória", "descricao": "Conquiste 10 títulos.", "icone": "👑", "cat": "titulo", "meta": 10},
    {"id": "triplice_coroa", "titulo": "Tríplice Coroa", "descricao": "Vença liga, copa nacional e competição continental na mesma temporada.", "icone": "🌟", "cat": "titulo", "meta": 1},
    {"id": "serie_a", "titulo": "Campeão Brasileiro", "descricao": "Vença o Brasileirão Série A.", "icone": "🇧🇷", "cat": "titulo", "meta": 1},
    {"id": "libertadores", "titulo": "Glória Eterna", "descricao": "Vença a Libertadores.", "icone": "🏆", "cat": "titulo", "meta": 1},
    {"id": "champions", "titulo": "Rei da Europa", "descricao": "Vença a Champions League.", "icone": "⭐", "cat": "titulo", "meta": 1},
    {"id": "copa_brasil", "titulo": "Copeiro", "descricao": "Vença a Copa do Brasil.", "icone": "🏆", "cat": "titulo", "meta": 1},
    # Carreira
    {"id": "100_jogos", "titulo": "Centenário", "descricao": "Complete 100 jogos como técnico.", "icone": "💯", "cat": "carreira", "meta": 100},
    {"id": "500_jogos", "titulo": "Lendário", "descricao": "Complete 500 jogos como técnico.", "icone": "🎖", "cat": "carreira", "meta": 500},
    {"id": "5_temporadas", "titulo": "Fidelidade", "descricao": "Fique 5 temporadas no mesmo clube.", "icone": "🤝", "cat": "carreira", "meta": 5},
    {"id": "trocar_time", "titulo": "Mala Pronta", "descricao": "Troque de time pela primeira vez.", "icone": "🧳", "cat": "carreira", "meta": 1},
    {"id": "acesso", "titulo": "Subiu!", "descricao": "Consiga um acesso à divisão superior.", "icone": "📈", "cat": "carreira", "meta": 1},
    {"id": "evitar_rebaixamento", "titulo": "Sobrevivente", "descricao": "Evite o rebaixamento após ficar na zona.", "icone": "🛡", "cat": "carreira", "meta": 1},
    # Partida
    {"id": "goleada_5", "titulo": "Goleada!", "descricao": "Vença uma partida por 5+ gols.", "icone": "⚽", "cat": "partida", "meta": 1},
    {"id": "invicto_10", "titulo": "Invicto", "descricao": "Fique 10 jogos sem perder.", "icone": "🔥", "cat": "partida", "meta": 10},
    {"id": "invicto_20", "titulo": "Muralha", "descricao": "Fique 20 jogos sem perder.", "icone": "🏰", "cat": "partida", "meta": 20},
    {"id": "virada", "titulo": "A Grande Virada", "descricao": "Vença de virada após estar perdendo por 2+ gols.", "icone": "🔄", "cat": "partida", "meta": 1},
    {"id": "sem_levar_gol_5", "titulo": "Fortaleza", "descricao": "Fique 5 jogos sem levar gol.", "icone": "🧤", "cat": "partida", "meta": 5},
    # Financeiro
    {"id": "lucro_100m", "titulo": "Cofre Cheio", "descricao": "Tenha R$100M de saldo.", "icone": "💰", "cat": "financeiro", "meta": 1},
    {"id": "venda_recorde", "titulo": "Negociante", "descricao": "Venda um jogador por R$50M+.", "icone": "🤝", "cat": "financeiro", "meta": 1},
    # Jogador
    {"id": "revelar_jovem", "titulo": "Olheiro da Base", "descricao": "Revele 5 jogadores da base.", "icone": "🌱", "cat": "jogador", "meta": 5},
    {"id": "jogador_99", "titulo": "Perfeição", "descricao": "Tenha um jogador com OVR 99.", "icone": "💎", "cat": "jogador", "meta": 1},
    # Especial
    {"id": "primeiro_jogo", "titulo": "Estreia", "descricao": "Jogue sua primeira partida.", "icone": "🎬", "cat": "especial", "meta": 1},
    {"id": "demitido", "titulo": "Seguro Desemprego", "descricao": "Seja demitido pela primeira vez.", "icone": "📋", "cat": "especial", "meta": 1},
]


class AchievementEngine:
    """Gerencia conquistas/achievements."""

    def __init__(self) -> None:
        self.conquistas: Dict[str, Conquista] = {}
        self._inicializar()

    def _inicializar(self) -> None:
        cat_map = {
            "titulo": CategoriaConquista.TITULO,
            "carreira": CategoriaConquista.CARREIRA,
            "partida": CategoriaConquista.PARTIDA,
            "financeiro": CategoriaConquista.FINANCEIRO,
            "jogador": CategoriaConquista.JOGADOR,
            "especial": CategoriaConquista.ESPECIAL,
        }
        for d in CONQUISTAS_DEFINICAO:
            self.conquistas[d["id"]] = Conquista(
                id=d["id"], titulo=d["titulo"], descricao=d["descricao"],
                icone=d.get("icone", "🏆"),
                categoria=cat_map.get(d.get("cat", "especial"), CategoriaConquista.ESPECIAL),
                meta=d.get("meta", 1),
            )

    def verificar(self, chave: str, progresso: int = 1) -> Optional[Conquista]:
        """Incrementa progresso e retorna conquista se desbloqueada agora."""
        c = self.conquistas.get(chave)
        if not c or c.desbloqueada:
            return None
        c.progresso = min(c.meta, c.progresso + progresso)
        if c.progresso >= c.meta:
            c.desbloqueada = True
            return c
        return None

    def set_progresso(self, chave: str, valor: int) -> Optional[Conquista]:
        """Define progresso absoluto (para invicto, sequências)."""
        c = self.conquistas.get(chave)
        if not c or c.desbloqueada:
            return None
        c.progresso = valor
        if c.progresso >= c.meta:
            c.desbloqueada = True
            return c
        return None

    def get_todas(self) -> List[Dict]:
        return [
            {
                "id": c.id, "titulo": c.titulo, "descricao": c.descricao,
                "icone": c.icone, "categoria": c.categoria.value,
                "desbloqueada": c.desbloqueada, "progresso": c.progresso,
                "meta": c.meta, "data": c.data_desbloqueio,
            }
            for c in self.conquistas.values()
        ]

    def get_recentes(self, limite: int = 5) -> List[Dict]:
        desbloqueadas = [c for c in self.conquistas.values() if c.desbloqueada]
        desbloqueadas.sort(key=lambda c: c.data_desbloqueio, reverse=True)
        return [{"id": c.id, "titulo": c.titulo, "icone": c.icone} for c in desbloqueadas[:limite]]

    def to_save_dict(self) -> Dict:
        return {
            cid: {"d": c.desbloqueada, "p": c.progresso, "dt": c.data_desbloqueio}
            for cid, c in self.conquistas.items()
            if c.desbloqueada or c.progresso > 0
        }

    def from_save_dict(self, data: Dict) -> None:
        for cid, vals in data.items():
            c = self.conquistas.get(cid)
            if c:
                c.desbloqueada = vals.get("d", False)
                c.progresso = vals.get("p", 0)
                c.data_desbloqueio = vals.get("dt", "")


# ══════════════════════════════════════════════════════════════
#  PREMIAÇÕES DE FIM DE TEMPORADA
# ══════════════════════════════════════════════════════════════

class AwardsEngine:
    """Determina premiações de fim de temporada."""

    def __init__(self) -> None:
        self.premiacoes: List[PremiacaoTemporada] = []

    def calcular_premiacoes(
        self,
        temporada: int,
        todos_times: List["Time"],
        artilharia: Dict[str, int],
        notas_medias: Dict[int, float],
        competicao_principal: str = "serie_a",
    ) -> List[PremiacaoTemporada]:
        """Calcula todas as premiações da temporada."""
        premios: List[PremiacaoTemporada] = []

        # Artilheiro
        if artilharia:
            top_gol = max(artilharia.items(), key=lambda x: x[1])
            nome_artilheiro = top_gol[0]
            gols = top_gol[1]
            time_art = self._encontrar_time_jogador(nome_artilheiro, todos_times)
            premios.append(PremiacaoTemporada(
                tipo=TipoPremio.ARTILHEIRO, temporada=temporada,
                jogador_nome=nome_artilheiro, time_nome=time_art,
                competicao=competicao_principal, valor=f"{gols} gols",
            ))

        # Bola de Ouro (melhor nota média)
        if notas_medias:
            melhor_id = max(notas_medias.items(), key=lambda x: x[1])
            jog = self._encontrar_jogador_por_id(melhor_id[0], todos_times)
            if jog:
                premios.append(PremiacaoTemporada(
                    tipo=TipoPremio.BOLA_OURO, temporada=temporada,
                    jogador_nome=jog.nome, jogador_id=jog.id,
                    time_nome=self._encontrar_time_jogador(jog.nome, todos_times),
                    competicao=competicao_principal,
                    valor=f"Nota {melhor_id[1]:.1f}",
                ))

        # Revelação (melhor jovem ≤21)
        jovens = []
        for t in todos_times:
            for j in t.jogadores:
                if j.idade <= 21 and j.id in notas_medias:
                    jovens.append((j, notas_medias[j.id], t.nome))
        if jovens:
            melhor_jovem = max(jovens, key=lambda x: x[1])
            premios.append(PremiacaoTemporada(
                tipo=TipoPremio.REVELACAO, temporada=temporada,
                jogador_nome=melhor_jovem[0].nome, jogador_id=melhor_jovem[0].id,
                time_nome=melhor_jovem[2], competicao=competicao_principal,
                valor=f"Nota {melhor_jovem[1]:.1f}",
            ))

        # Melhor Goleiro
        goleiros = []
        for t in todos_times:
            for j in t.jogadores:
                if j.posicao.name == "GOL" and j.id in notas_medias:
                    goleiros.append((j, notas_medias[j.id], t.nome))
        if goleiros:
            melhor_gol = max(goleiros, key=lambda x: x[1])
            premios.append(PremiacaoTemporada(
                tipo=TipoPremio.MELHOR_GOLEIRO, temporada=temporada,
                jogador_nome=melhor_gol[0].nome, jogador_id=melhor_gol[0].id,
                time_nome=melhor_gol[2], competicao=competicao_principal,
                valor=f"Nota {melhor_gol[1]:.1f}",
            ))

        self.premiacoes.extend(premios)
        return premios

    @staticmethod
    def _encontrar_time_jogador(nome: str, times: List["Time"]) -> str:
        for t in times:
            for j in t.jogadores:
                if j.nome == nome:
                    return t.nome
        return ""

    @staticmethod
    def _encontrar_jogador_por_id(jid: int, times: List["Time"]) -> Optional["Jogador"]:
        for t in times:
            for j in t.jogadores:
                if j.id == jid:
                    return j
        return None

    def get_premiacoes(self, temporada: int = 0) -> List[Dict]:
        prems = self.premiacoes if not temporada else [p for p in self.premiacoes if p.temporada == temporada]
        return [
            {
                "tipo": p.tipo.value, "temporada": p.temporada,
                "jogador_nome": p.jogador_nome, "jogador_id": p.jogador_id,
                "time_nome": p.time_nome, "competicao": p.competicao,
                "valor": p.valor,
            }
            for p in prems
        ]

    def to_save_dict(self) -> List[Dict]:
        return self.get_premiacoes()

    def from_save_dict(self, data: List[Dict]) -> None:
        self.premiacoes = []
        for d in data:
            self.premiacoes.append(PremiacaoTemporada(
                tipo=TipoPremio(d.get("tipo", "Artilheiro")),
                temporada=d.get("temporada", 2026),
                jogador_nome=d.get("jogador_nome", ""),
                jogador_id=d.get("jogador_id", 0),
                time_nome=d.get("time_nome", ""),
                competicao=d.get("competicao", ""),
                valor=d.get("valor", ""),
            ))


# ══════════════════════════════════════════════════════════════
#  RECORDES DE CARREIRA
# ══════════════════════════════════════════════════════════════

class RecordsEngine:
    """Rastreia recordes da carreira do técnico."""

    def __init__(self) -> None:
        self.recordes: Dict[str, Dict] = {
            "maior_goleada": {"desc": "Maior goleada aplicada", "valor": 0, "detalhe": ""},
            "maior_sequencia_vitorias": {"desc": "Maior sequência de vitórias", "valor": 0, "detalhe": ""},
            "maior_sequencia_invicta": {"desc": "Maior invencibilidade", "valor": 0, "detalhe": ""},
            "total_titulos": {"desc": "Total de títulos", "valor": 0, "detalhe": ""},
            "total_jogos": {"desc": "Total de jogos", "valor": 0, "detalhe": ""},
            "total_vitorias": {"desc": "Total de vitórias", "valor": 0, "detalhe": ""},
            "total_gols_marcados": {"desc": "Total gols marcados", "valor": 0, "detalhe": ""},
            "melhor_contratacao": {"desc": "Melhor contratação (OVR)", "valor": 0, "detalhe": ""},
            "maior_venda": {"desc": "Maior venda (R$)", "valor": 0, "detalhe": ""},
            "temporadas_no_clube": {"desc": "Mais temporadas no mesmo clube", "valor": 0, "detalhe": ""},
        }
        # Contadores correntes
        self._seq_vitorias: int = 0
        self._seq_invicta: int = 0

    def registrar_resultado(self, gols_favor: int, gols_contra: int, competicao: str, temporada: int) -> None:
        """Registra resultado e atualiza recordes."""
        self.recordes["total_jogos"]["valor"] += 1

        if gols_favor > gols_contra:
            self.recordes["total_vitorias"]["valor"] += 1
            self._seq_vitorias += 1
            self._seq_invicta += 1
        elif gols_favor == gols_contra:
            self._seq_vitorias = 0
            self._seq_invicta += 1
        else:
            self._seq_vitorias = 0
            self._seq_invicta = 0

        self.recordes["total_gols_marcados"]["valor"] += gols_favor

        diff = gols_favor - gols_contra
        if diff > self.recordes["maior_goleada"]["valor"]:
            self.recordes["maior_goleada"]["valor"] = diff
            self.recordes["maior_goleada"]["detalhe"] = f"{gols_favor}x{gols_contra} ({competicao}, T{temporada})"

        if self._seq_vitorias > self.recordes["maior_sequencia_vitorias"]["valor"]:
            self.recordes["maior_sequencia_vitorias"]["valor"] = self._seq_vitorias
            self.recordes["maior_sequencia_vitorias"]["detalhe"] = f"T{temporada}"

        if self._seq_invicta > self.recordes["maior_sequencia_invicta"]["valor"]:
            self.recordes["maior_sequencia_invicta"]["valor"] = self._seq_invicta
            self.recordes["maior_sequencia_invicta"]["detalhe"] = f"T{temporada}"

    def registrar_titulo(self, competicao: str, temporada: int) -> None:
        self.recordes["total_titulos"]["valor"] += 1
        self.recordes["total_titulos"]["detalhe"] = f"Último: {competicao} (T{temporada})"

    def registrar_venda(self, valor: int, jogador_nome: str) -> None:
        if valor > self.recordes["maior_venda"]["valor"]:
            self.recordes["maior_venda"]["valor"] = valor
            self.recordes["maior_venda"]["detalhe"] = f"{jogador_nome} - R${valor:,.0f}"

    def registrar_contratacao(self, ovr: int, jogador_nome: str) -> None:
        if ovr > self.recordes["melhor_contratacao"]["valor"]:
            self.recordes["melhor_contratacao"]["valor"] = ovr
            self.recordes["melhor_contratacao"]["detalhe"] = f"{jogador_nome} (OVR {ovr})"

    def get_todos(self) -> List[Dict]:
        return [
            {"chave": k, "descricao": v["desc"], "valor": v["valor"], "detalhe": v["detalhe"]}
            for k, v in self.recordes.items()
        ]

    def to_save_dict(self) -> Dict:
        return {
            "recordes": self.recordes,
            "seq_v": self._seq_vitorias,
            "seq_i": self._seq_invicta,
        }

    def from_save_dict(self, data: Dict) -> None:
        self.recordes.update(data.get("recordes", {}))
        self._seq_vitorias = data.get("seq_v", 0)
        self._seq_invicta = data.get("seq_i", 0)
