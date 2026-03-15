# -*- coding: utf-8 -*-
"""
GameManager — orquestrador central do jogo.
Conecta todos os engines, managers e o estado de jogo.
"""
from __future__ import annotations

import copy
import json
import random
import unicodedata
from typing import List, Dict, Optional

from core.models import Time, Noticia, ResultadoPartida
from core.enums import CategoriaNoticia
from engine.season_engine import MotorTemporada
from engine.transfer_engine import MotorTransferencias
from fantasy.manager import FantasyManager
from managers.competition_manager import GerenciadorCompeticoes
from services.asset_registry import AssetRegistryService
from services.inbox_engine import InboxEngine
from services.license_service import LicenseService
from services.licensing_engine import LicensingEngine
from services.music_manager import MusicManager
from services.press_conference import PressConferenceEngine
from services.save_integrity import SaveIntegrityService
from services.achievements_awards import AchievementEngine, AwardsEngine, RecordsEngine
from services.advanced_systems import (
    PromiseEngine, LockerRoomEngine, TacticalChemistryEngine,
    CoachCareerEngine, CulturalAdaptationEngine, ClubIdentityEngine,
    AgentProfileEngine, PlayerObjectivesEngine, PostMatchAnalysisEngine,
    DeadlineDayEngine, StaffMeetingEngine, NewgenAvatarEngine,
)
from services.ffp_engine import FFPEngine
from services.world_rankings import WorldRankingsEngine
from services.hall_of_fame import HallOfFameEngine
from config import TEMPORADA_INICIAL, SEMANAS_POR_TEMPORADA, SAVES_DIR
from utils.logger import get_logger

log = get_logger(__name__)


_SOUTH_AMERICA_CODES = {"BRA", "ARG", "BOL", "CHI", "COL", "EQU", "PAR", "PER", "URU", "VEN"}
_EUROPE_CODES = {"ING", "ESP", "ITA", "ALE", "FRA", "POR", "HOL", "BEL", "TUR", "RUS", "ESC", "SUI", "AUT", "GRE"}
_COUNTRY_NAME_BY_CODE = {
    "BRA": "Brasil",
    "ARG": "Argentina",
    "BOL": "Bolivia",
    "CHI": "Chile",
    "COL": "Colombia",
    "EQU": "Equador",
    "PAR": "Paraguai",
    "PER": "Peru",
    "URU": "Uruguai",
    "VEN": "Venezuela",
    "ING": "Inglaterra",
    "ESP": "Espanha",
    "ITA": "Italia",
    "ALE": "Alemanha",
    "FRA": "Franca",
    "POR": "Portugal",
    "HOL": "Holanda",
    "BEL": "Belgica",
    "TUR": "Turquia",
    "RUS": "Russia",
    "ESC": "Escocia",
    "SUI": "Suica",
    "AUT": "Austria",
    "GRE": "Grecia",
    "MEX": "Mexico",
    "EUA": "Estados Unidos",
}
_COUNTRY_CODE_BY_NAME = {
    "".join(c for c in unicodedata.normalize("NFKD", nome.lower()) if ord(c) < 128): code
    for code, nome in _COUNTRY_NAME_BY_CODE.items()
}


class GameManager:
    """Ponto central que coordena todos os subsistemas do jogo."""

    def __init__(self) -> None:
        self.times_serie_a: List[Time] = []
        self.times_serie_b: List[Time] = []
        self.times_serie_c: List[Time] = []
        self.times_serie_d: List[Time] = []
        self.times_sem_divisao: List[Time] = []
        self.times_europeus: Dict[str, Dict[int, List[Time]]] = {}  # {pais: {div: [Time]}}
        self._serie_d_target: int = 64
        self.time_jogador: Optional[Time] = None

        self.temporada: int = TEMPORADA_INICIAL
        self.semana: int = 0
        self.noticias: List[Noticia] = []
        self.ultimo_resultado: Optional[Dict[str, List[ResultadoPartida]]] = None

        self.motor_temporada = MotorTemporada()
        self.mercado = MotorTransferencias()
        self.competicoes = GerenciadorCompeticoes()

        self.save_nome: Optional[str] = None
        self.artilharia_memoria: Dict[int, Dict] = {}  # id -> {gols, assists, nome, time}
        self._lib_qualificados: List[Time] = []
        self._supercopa_times: Optional[tuple] = None  # (campeão brasileiro, campeão copa)
        self._selecoes_pool_base: Dict[str, List] = {}
        self.tecnicos_demitidos: List[Dict] = []  # [{nome, time, semana, temporada}]

        # Central de notificações e licenciamento
        self.inbox = InboxEngine()
        self.licensing = LicensingEngine()
        self.asset_registry = AssetRegistryService()
        self.save_integrity = SaveIntegrityService()
        self.license_service = LicenseService()

        # Novos subsistemas
        self.music = MusicManager()
        self.fantasy = FantasyManager()
        self.coletiva = PressConferenceEngine()
        self.conquistas = AchievementEngine()
        self.premiacoes = AwardsEngine()
        self.recordes = RecordsEngine()
        self.auto_save_ativo: bool = True
        self.auto_save_intervalo_semanas: int = 12
        self.modo_performance: bool = False
        self._mercado_ia_intervalo_semanas: int = 4
        self._ranking_intervalo_semanas: int = 1
        self._inbox_intervalo_semanas: int = 1
        self.tutorial_visto: bool = False

        # Sistemas avançados
        self.promessas_engine = PromiseEngine()
        self.vestiario_engine = LockerRoomEngine()
        self.quimica_engine = TacticalChemistryEngine()
        self.carreira_engine = CoachCareerEngine()
        self.adaptacao_engine = CulturalAdaptationEngine()
        self.identidade_engine = ClubIdentityEngine()
        self.agentes_engine = AgentProfileEngine()
        self.objetivos_engine = PlayerObjectivesEngine()
        self.analise_engine = PostMatchAnalysisEngine()
        self.ultima_analise: Optional[Dict] = None

        # Novos engines (FFP, Ranking, Hall of Fame)
        self.ffp_engine = FFPEngine()
        self.rankings_engine = WorldRankingsEngine()
        self.hall_of_fame = HallOfFameEngine()

        # Desemprego
        self._desempregado: bool = False
        self._semanas_desempregado: int = 0
        self._ofertas_emprego: List[Dict] = []
        self._ultimo_relatorio_save: Optional[Dict] = None
        self._resumo_semana: Dict = {}
        self._janelas_transferencia: tuple[tuple[int, int], ...] = ((0, 10), (30, 38))
        self._comp_selecoes: bool = False

        # Amistosos
        self.amistoso_agendado: Optional[Time] = None

        # Novos engines FM-style
        self.deadline_engine = DeadlineDayEngine()
        self.staff_meeting_engine = StaffMeetingEngine()
        self.newgen_avatar_engine = NewgenAvatarEngine()
        self._ultima_reuniao_staff: Optional[Dict] = None

        # Dados de rivalidade (derby)
        self._rivalidades: Dict[str, List[str]] = {
            "Flamengo": ["Fluminense", "Vasco da Gama", "Botafogo"],
            "Fluminense": ["Flamengo", "Vasco da Gama", "Botafogo"],
            "Vasco da Gama": ["Flamengo", "Fluminense", "Botafogo"],
            "Botafogo": ["Flamengo", "Fluminense", "Vasco da Gama"],
            "Corinthians": ["Palmeiras", "São Paulo", "Santos"],
            "Palmeiras": ["Corinthians", "São Paulo", "Santos"],
            "São Paulo": ["Corinthians", "Palmeiras", "Santos"],
            "Santos": ["Corinthians", "Palmeiras", "São Paulo"],
            "Grêmio": ["Internacional"],
            "Internacional": ["Grêmio"],
            "Atlético-MG": ["Cruzeiro", "América-MG"],
            "Cruzeiro": ["Atlético-MG", "América-MG"],
            "América-MG": ["Atlético-MG", "Cruzeiro"],
            "Athletico-PR": ["Coritiba", "Paraná Clube"],
            "Coritiba": ["Athletico-PR", "Paraná Clube"],
            "Sport": ["Náutico", "Santa Cruz"],
            "Náutico": ["Sport", "Santa Cruz"],
            "Santa Cruz": ["Sport", "Náutico"],
            "Vitória": ["Bahia"],
            "Bahia": ["Vitória"],
            "Goiás": ["Vila Nova", "Atlético-GO"],
            "Vila Nova": ["Goiás", "Atlético-GO"],
            "Atlético-GO": ["Goiás", "Vila Nova"],
            "Fortaleza": ["Ceará"],
            "Ceará": ["Fortaleza"],
            "Remo": ["Paysandu"],
            "Paysandu": ["Remo"],
            "Guarani": ["Ponte Preta"],
            "Ponte Preta": ["Guarani"],
            "Avaí": ["Figueirense"],
            "Figueirense": ["Avaí"],
            "ABC": ["América-RN"],
            "América-RN": ["ABC"],
            # Europeus
            "Real Madrid": ["Barcelona", "Atlético de Madrid"],
            "Barcelona": ["Real Madrid", "Espanyol"],
            "Atlético de Madrid": ["Real Madrid"],
            "Manchester United": ["Manchester City", "Liverpool"],
            "Manchester City": ["Manchester United"],
            "Liverpool": ["Everton", "Manchester United"],
            "Arsenal": ["Tottenham"],
            "Tottenham": ["Arsenal"],
            "Chelsea": ["Fulham"],
            "Milan": ["Inter de Milão", "Juventus"],
            "Inter de Milão": ["Milan", "Juventus"],
            "Juventus": ["Milan", "Inter de Milão", "Torino"],
            "Roma": ["Lazio"],
            "Lazio": ["Roma"],
            "Borussia Dortmund": ["Bayern de Munique", "Schalke 04"],
            "Bayern de Munique": ["Borussia Dortmund"],
            "PSG": ["Olympique de Marseille"],
            "Olympique de Marseille": ["PSG"],
            "Benfica": ["Porto", "Sporting CP"],
            "Porto": ["Benfica", "Sporting CP"],
            "Sporting CP": ["Benfica", "Porto"],
            "Ajax": ["Feyenoord", "PSV"],
            "Feyenoord": ["Ajax"],
            "PSV": ["Ajax"],
            "River Plate": ["Boca Juniors"],
            "Boca Juniors": ["River Plate"],
            "Galatasaray": ["Fenerbahçe", "Beşiktaş"],
            "Fenerbahçe": ["Galatasaray", "Beşiktaş"],
            "Beşiktaş": ["Galatasaray", "Fenerbahçe"],
            "Celtic": ["Rangers"],
            "Rangers": ["Celtic"],
        }

    # ═══════════════════════════════════════════════════════════
    #  NOVO JOGO
    # ═══════════════════════════════════════════════════════════

    def novo_jogo(self, time_escolhido: str) -> None:
        from data.seeds.seed_loader import (
            criar_times_serie_a, criar_times_serie_b,
            criar_times_serie_c, criar_times_serie_d,
            criar_times_sem_divisao, criar_todos_times_europeus,
        )
        self.times_serie_a = criar_times_serie_a()
        self.times_serie_b = criar_times_serie_b()
        self.times_serie_c = criar_times_serie_c()
        self.times_serie_d = criar_times_serie_d()
        self.times_sem_divisao = criar_times_sem_divisao()
        self.times_europeus = criar_todos_times_europeus()
        self._serie_d_target = max(64, len(self.times_serie_d))

        self.time_jogador = None
        for t in self.todos_times():
            if t.nome == time_escolhido:
                t.eh_jogador = True
                self.time_jogador = t
                break

        if not self.time_jogador:
            raise ValueError(f"Time não encontrado: {time_escolhido}")

        self._registrar_pool_selecoes_base()

        # Mercado de jogadores livres
        max_id = max((j.id for t in self.todos_times()
                       for j in t.jogadores), default=0) + 1
        self.mercado.gerar_jogadores_livres(50, max_id)

        self.temporada = TEMPORADA_INICIAL
        self.semana = 0
        self._comp_selecoes = False
        self._iniciar_temporada()

        # Inicializar sistemas avançados
        if self.time_jogador:
            self.identidade_engine.atribuir_identidade(self.time_jogador)
            self.objetivos_engine.gerar_objetivos_temporada(self.time_jogador)
            all_ids = [j.id for j in self.time_jogador.jogadores]
            self.agentes_engine.gerar_agentes(all_ids)
            # Registrar jogadores estrangeiros para adaptação
            for j in self.time_jogador.jogadores:
                if j.nacionalidade and j.nacionalidade != "Brasil":
                    self.adaptacao_engine.registrar_transferencia(j, "Brasil")

        log.info("Novo jogo criado com %s", time_escolhido)

        # Inicializar ranking mundial
        self.rankings_engine.inicializar(self.todos_times())
        self._inicializar_fantasy()

    def novo_jogo_config(self, time_escolhido: str, ligas_selecionadas: List[str],
                         *, tecnico_nome: str = "Treinador", tecnico_nac: str = "Brasil",
                         sistema_salarios: str = "mensal", sistema_forca: str = "classico",
                         temporada_inicio: int = TEMPORADA_INICIAL,
                         tacas_internacionais: bool = False,
                         comp_selecoes: bool = False) -> None:
        """Novo jogo com carregamento seletivo de ligas (performance)."""
        from data.seeds.seed_loader import (
            criar_times_serie_a, criar_times_serie_b,
            criar_times_serie_c, criar_times_serie_d,
            criar_times_sem_divisao, criar_times_europeus,
        )
        # Carrega apenas ligas selecionadas
        if "BRA" in ligas_selecionadas:
            self.times_serie_a = criar_times_serie_a()
            self.times_serie_b = criar_times_serie_b()
            self.times_serie_c = criar_times_serie_c()
            self.times_serie_d = criar_times_serie_d()
            self.times_sem_divisao = criar_times_sem_divisao()
            self._serie_d_target = max(64, len(self.times_serie_d))

        for codigo in ligas_selecionadas:
            if codigo != "BRA":
                try:
                    dados = criar_times_europeus(codigo)
                    if dados:
                        self.times_europeus[codigo] = dados
                except Exception as e:
                    log.warning("Erro ao carregar liga %s: %s", codigo, e)

        # Localizar time do jogador
        self.time_jogador = None
        for t in self.todos_times():
            if t.nome == time_escolhido:
                t.eh_jogador = True
                self.time_jogador = t
                break
        if not self.time_jogador:
            raise ValueError(f"Time não encontrado: {time_escolhido}")

        self._registrar_pool_selecoes_base()

        # Config do técnico
        self.time_jogador.tecnico = tecnico_nome
        self._tecnico_nome = tecnico_nome
        self._tecnico_nac = tecnico_nac
        self._sistema_salarios = sistema_salarios
        self._sistema_forca = sistema_forca
        self._tacas_internacionais = tacas_internacionais
        self._comp_selecoes = comp_selecoes

        # Mercado
        max_id = max((j.id for t in self.todos_times()
                       for j in t.jogadores), default=0) + 1
        self.mercado.gerar_jogadores_livres(50, max_id)

        self.temporada = temporada_inicio
        self.semana = 0
        self._iniciar_temporada()

        # Sistemas avançados
        if self.time_jogador:
            self.identidade_engine.atribuir_identidade(self.time_jogador)
            self.objetivos_engine.gerar_objetivos_temporada(self.time_jogador)
            all_ids = [j.id for j in self.time_jogador.jogadores]
            self.agentes_engine.gerar_agentes(all_ids)
            for j in self.time_jogador.jogadores:
                if j.nacionalidade and j.nacionalidade != "Brasil":
                    self.adaptacao_engine.registrar_transferencia(j, "Brasil")

        log.info("Novo jogo (config) criado com %s – ligas: %s", time_escolhido, ligas_selecionadas)
        self.rankings_engine.inicializar(self.todos_times())
        self._inicializar_fantasy()

    def _normalizar_pais_codigo(self, valor: str, fallback: str = "") -> str:
        texto = str(valor or "").strip()
        if not texto:
            texto = str(fallback or "").strip()
        if not texto:
            return "BRA"
        codigo = texto.upper()
        if codigo in _COUNTRY_NAME_BY_CODE:
            return codigo
        if len(codigo) == 2 and codigo.isalpha():
            return "BRA"
        chave = "".join(
            c for c in unicodedata.normalize("NFKD", texto.lower())
            if ord(c) < 128
        )
        return _COUNTRY_CODE_BY_NAME.get(chave, fallback.upper() if len(fallback) == 3 else "BRA")

    def _nome_pais(self, codigo: str) -> str:
        return _COUNTRY_NAME_BY_CODE.get(codigo, codigo)

    def _registrar_pool_selecoes_base(self) -> None:
        pool: Dict[str, List] = {}
        for time in self.todos_times():
            pais_clube = self._normalizar_pais_codigo(getattr(time, "estado", ""), "BRA")
            for jogador in time.jogadores:
                pais = self._normalizar_pais_codigo(getattr(jogador, "nacionalidade", ""), pais_clube)
                pool.setdefault(pais, []).append(copy.deepcopy(jogador))
        self._selecoes_pool_base = pool

    def _clubes_sul_americanos(self) -> List[Time]:
        clubes = list(self.times_serie_a + self.times_serie_b + self.times_serie_c + self.times_serie_d + self.times_sem_divisao)
        for pais, divs in self.times_europeus.items():
            if pais not in _SOUTH_AMERICA_CODES:
                continue
            for times in divs.values():
                clubes.extend(times)
        return clubes

    @staticmethod
    def _dedupe_times(times: List[Time], usados: Optional[set[int]] = None) -> List[Time]:
        vistos = set(usados or set())
        unicos: List[Time] = []
        for time in times:
            if not time or time.id in vistos:
                continue
            unicos.append(time)
            vistos.add(time.id)
        return unicos

    def _normalizar_divisoes_brasileiras(self) -> None:
        alvo_d = max(64, getattr(self, "_serie_d_target", len(self.times_serie_d) or 64))
        pool = self._dedupe_times(
            self.times_serie_a + self.times_serie_b + self.times_serie_c + self.times_serie_d + self.times_sem_divisao
        )
        usados: set[int] = set()

        def limpar_base(lista: List[Time], alvo: int, divisao: int) -> List[Time]:
            base = self._dedupe_times(lista, usados)
            selecionados = base[:alvo]
            for time in selecionados:
                usados.add(time.id)
                time.divisao = divisao
            return selecionados

        def preencher(lista: List[Time], alvo: int, divisao: int) -> List[Time]:
            if len(lista) >= alvo:
                return lista[:alvo]
            candidatos = sorted(
                (time for time in pool if time.id not in usados),
                key=lambda time: (
                    abs((getattr(time, "divisao", divisao) or divisao) - divisao),
                    -getattr(time, "prestigio", 0),
                    time.nome,
                ),
            )
            for time in candidatos:
                if len(lista) >= alvo:
                    break
                usados.add(time.id)
                time.divisao = divisao
                lista.append(time)
            return lista

        serie_a = preencher(limpar_base(self.times_serie_a, 20, 1), 20, 1)
        serie_b = preencher(limpar_base(self.times_serie_b, 20, 2), 20, 2)
        serie_c = preencher(limpar_base(self.times_serie_c, 20, 3), 20, 3)
        serie_d = preencher(limpar_base(self.times_serie_d, alvo_d, 4), alvo_d, 4)

        self.times_serie_a = serie_a
        self.times_serie_b = serie_b
        self.times_serie_c = serie_c
        self.times_serie_d = serie_d
        self.times_sem_divisao = self._dedupe_times(self.times_sem_divisao + pool, usados)

    def _gerar_qualificados_libertadores(self) -> List[Time]:
        qualificados: List[Time] = []
        vistos: set[int] = set()
        cotas = {
            "BRA": 6, "ARG": 4, "COL": 3, "CHI": 3,
            "EQU": 2, "PAR": 2, "PER": 2, "URU": 2,
            "BOL": 1, "VEN": 1,
        }

        def adicionar(lista: List[Time], limite: int) -> None:
            for time in lista[:limite]:
                if time.id in vistos:
                    continue
                qualificados.append(time)
                vistos.add(time.id)

        if self.competicoes.brasileirao_a:
            adicionar(self.competicoes.brasileirao_a.classificacao(), cotas["BRA"])
        elif self.times_serie_a:
            adicionar(sorted(self.times_serie_a, key=lambda t: t.prestigio, reverse=True), cotas["BRA"])

        for pais, quota in cotas.items():
            if pais == "BRA":
                continue
            liga = self.competicoes.ligas_europeias.get(pais, {}).get(1)
            if liga:
                adicionar(liga.classificacao(), quota)
            elif pais in self.times_europeus and 1 in self.times_europeus[pais]:
                adicionar(sorted(self.times_europeus[pais][1], key=lambda t: t.prestigio, reverse=True), quota)

        if self.competicoes.copa_brasil and self.competicoes.copa_brasil.campeao:
            campeao = self.competicoes.copa_brasil.campeao
            if campeao.id not in vistos:
                qualificados.append(campeao)
                vistos.add(campeao.id)

        pool = sorted(self._clubes_sul_americanos(), key=lambda t: t.prestigio, reverse=True)
        for time in pool:
            if len(qualificados) >= 32:
                break
            if time.id in vistos:
                continue
            qualificados.append(time)
            vistos.add(time.id)
        return qualificados[:32]

    def _criar_selecoes_competicoes(self) -> Dict[str, List[Time]]:
        jogadores_por_pais: Dict[str, List] = {}
        for time in self.todos_times():
            pais_clube = self._normalizar_pais_codigo(getattr(time, "estado", ""), "BRA")
            for jogador in time.jogadores:
                pais = self._normalizar_pais_codigo(getattr(jogador, "nacionalidade", ""), pais_clube)
                jogadores_por_pais.setdefault(pais, []).append(jogador)

        selecoes: List[Time] = []
        time_id = 900_000
        jogador_id = 9_000_000
        todos_paises = sorted(set(jogadores_por_pais) | set(self._selecoes_pool_base))
        for pais in todos_paises:
            jogadores = list(jogadores_por_pais.get(pais, []))
            nomes_atuais = {j.nome for j in jogadores}
            for reserva in self._selecoes_pool_base.get(pais, []):
                if len(jogadores) >= 23:
                    break
                if reserva.nome in nomes_atuais:
                    continue
                jogadores.append(copy.deepcopy(reserva))
                nomes_atuais.add(reserva.nome)
            if len(jogadores) < 11:
                continue
            elenco = [copy.deepcopy(j) for j in sorted(jogadores, key=lambda item: item.overall, reverse=True)[:23]]
            if len(elenco) < 11:
                continue
            for idx, jogador in enumerate(elenco):
                jogador.id = jogador_id + idx
            jogador_id += len(elenco) + 10

            selecao = Time(
                id=time_id,
                nome=self._nome_pais(pais),
                nome_curto=pais,
                cidade=self._nome_pais(pais),
                estado=pais,
                cor_principal="#0f172a",
                cor_secundaria="#ffffff",
                divisao=99,
                prestigio=max(55, int(sum(j.overall for j in elenco[:11]) / max(1, min(11, len(elenco))))),
                torcida_tamanho=15_000_000,
                jogadores=elenco,
            )
            time_id += 1
            selecao.estadio.nome = f"Estadio Nacional de {selecao.nome}"
            selecao.titulares = [j.id for j in sorted(elenco, key=lambda item: item.overall, reverse=True)[:11]]
            selecao.reservas = [j.id for j in sorted(elenco, key=lambda item: item.overall, reverse=True)[11:23]]
            selecoes.append(selecao)

        selecoes.sort(key=lambda t: t.prestigio, reverse=True)
        return {
            "mundo": selecoes,
            "europa": [t for t in selecoes if t.estado in _EUROPE_CODES],
            "america_sul": [t for t in selecoes if t.estado in _SOUTH_AMERICA_CODES],
        }

    def _iniciar_temporada(self, resetar: bool = True) -> None:
        if hasattr(self, '_lib_qualificados') and self._lib_qualificados:
            times_lib = list(self._lib_qualificados)
        else:
            times_lib = self._gerar_qualificados_libertadores()

        selecoes = self._criar_selecoes_competicoes() if self._comp_selecoes else {}
        self.competicoes.temporada = self.temporada
        self.competicoes.iniciar_temporada(
            self.times_serie_a, self.times_serie_b,
            self.times_serie_c, self.times_serie_d,
            self.times_sem_divisao,
            times_lib, self.time_jogador.estado if self.time_jogador else "SP",
            resetar=resetar,
            times_europeus=self.times_europeus,
            times_sul_america=self._clubes_sul_americanos(),
            selecoes=selecoes,
            supercopa_times=self._supercopa_times,
        )
        # Set board objectives for the player's team
        self._definir_metas_diretoria()
        # Set TV revenue by division
        self._ajustar_financas_temporada()
        # Reiniciar objetivos de jogadores para nova temporada
        if self.time_jogador:
            self.objetivos_engine.gerar_objetivos_temporada(self.time_jogador)
        self.motor_temporada.iniciar_pre_temporada(self.todos_times(), semanas=4)

    def mercado_aberto(self, semana: Optional[int] = None) -> bool:
        semana_ref = self.semana if semana is None else semana
        return any(inicio <= semana_ref <= fim for inicio, fim in self._janelas_transferencia)

    @staticmethod
    def _formatar_deadline_event(ev: Dict) -> str:
        tipo = ev.get("tipo", "")
        if tipo == "deadline_oferta":
            status = "ACEITA ✓" if ev.get("aceito") else "RECUSADA ✗"
            return (f"{ev['comprador']} fez oferta de R$ {ev['valor']:,.0f} "
                    f"por {ev['jogador']} ({ev['vendedor']}). {status}")
        elif tipo == "deadline_fechado":
            return (f"CONFIRMADO: {ev['jogador']} é o novo reforço do "
                    f"{ev['comprador']} por R$ {ev['valor']:,.0f}!")
        elif tipo == "deadline_oferta_recebida":
            return (f"{ev['de']} quer {ev['jogador']} e oferece "
                    f"R$ {ev['valor']:,.0f}! Você tem até o fim do dia.")
        return str(ev)

    def configurar_performance(self, ativo: bool) -> None:
        self.modo_performance = bool(ativo)
        if self.modo_performance:
            self.auto_save_intervalo_semanas = 24
            self._mercado_ia_intervalo_semanas = 8
            self._ranking_intervalo_semanas = 2
            self._inbox_intervalo_semanas = 2
        else:
            self.auto_save_intervalo_semanas = 12
            self._mercado_ia_intervalo_semanas = 4
            self._ranking_intervalo_semanas = 1
            self._inbox_intervalo_semanas = 1

    def get_resumo_semana(self) -> Dict:
        return self._resumo_semana

    def _montar_resumo_semana(self, resultados: Dict[str, List[ResultadoPartida]]) -> Dict:
        resumo_resultados: List[Dict] = []
        meu_time = self.time_jogador.nome if self.time_jogador else ""
        for comp, lista in resultados.items():
            for r in lista:
                resumo_resultados.append({
                    "comp": comp,
                    "casa": r.time_casa,
                    "fora": r.time_fora,
                    "placar": f"{r.gols_casa} x {r.gols_fora}",
                    "meu_jogo": meu_time in (r.time_casa, r.time_fora),
                })
        transferencias = [
            {
                "jogador": n.titulo.replace("TRANSFERÊNCIA: ", ""),
                "texto": n.texto,
            }
            for n in self.noticias
            if n.categoria == CategoriaNoticia.TRANSFERENCIA
        ]
        tabela = []
        if self.competicoes.brasileirao_a:
            camp = self.competicoes.brasileirao_a
            classif = camp.classificacao()
            for pos, time in enumerate(classif[:10], start=1):
                stats = camp.get_stats(time.id)
                tabela.append({
                    "pos": pos,
                    "time": time.nome,
                    "pontos": stats.get("pontos", 0),
                    "ultimos5": (
                        f"{stats.get('v', 0)}V-{stats.get('e', 0)}E-{stats.get('d', 0)}D"
                    ),
                    "meu_time": time.eh_jogador,
                })
        return {
            "semana": self.semana,
            "mercado_aberto": self.mercado_aberto(),
            "resultados": resumo_resultados,
            "transferencias": transferencias[-10:],
            "tabela_serie_a": tabela,
            "noticias": [
                {"titulo": n.titulo, "texto": n.texto}
                for n in self.noticias[-10:]
            ],
        }

    # ═══════════════════════════════════════════════════════════
    #  AVANÇAR SEMANA
    # ═══════════════════════════════════════════════════════════

    def avancar_semana(self) -> Dict[str, List[ResultadoPartida]]:
        self.semana += 1
        self.noticias = []

        # 1. Progressão semanal
        todos = self.todos_times()
        if self.motor_temporada.pre_temporada_ativa:
            noticias_sem = self.motor_temporada.processar_pre_temporada(todos)
        else:
            noticias_sem = self.motor_temporada.processar_semana(todos)
        self.noticias.extend(noticias_sem)

        # Hook: snapshot callback (after training, before matches)
        if hasattr(self, '_pre_match_callback') and self._pre_match_callback:
            self._pre_match_callback()

        # 2. Competições
        resultados = self.competicoes.avancar_semana()
        self.ultimo_resultado = resultados

        # 2.amistoso — Jogar amistoso se agendado e sem jogo oficial
        if self.amistoso_agendado and self.time_jogador:
            tem_jogo_oficial = False
            for comp_key, lista_res in resultados.items():
                for r in lista_res:
                    if r.time_casa == self.time_jogador.nome or r.time_fora == self.time_jogador.nome:
                        tem_jogo_oficial = True
                        break
                if tem_jogo_oficial:
                    break
            if not tem_jogo_oficial:
                from engine.match_engine import MotorPartida
                motor = MotorPartida()
                res_amistoso = motor.simular(
                    self.time_jogador, self.amistoso_agendado,
                    aplicar_pos_jogo=False,
                )
                resultados["amistoso"] = [res_amistoso]
                self.ultimo_resultado = resultados
                # Receita de bilheteria reduzida (30% da capacidade x preço ingresso médio)
                if hasattr(self.time_jogador, 'estadio') and self.time_jogador.estadio:
                    publico = int(self.time_jogador.estadio.capacidade * 0.3)
                    receita = publico * 35
                    self.time_jogador.financas.saldo += receita
                    self.noticias.append(Noticia(
                        titulo="Amistoso Realizado",
                        texto=f"{self.time_jogador.nome} {res_amistoso.gols_casa} x {res_amistoso.gols_fora} {self.amistoso_agendado.nome} (Amistoso). Público: {publico:,}. Receita: R$ {receita:,.0f}",
                        categoria=CategoriaNoticia.GERAL,
                    ))
            self.amistoso_agendado = None

        self._processar_fantasy(resultados)

        # 2a. Supercopa Rei — premiação
        if "supercopa_rei" in resultados and self.competicoes.supercopa_rei:
            sc = self.competicoes.supercopa_rei
            if sc.get("campeao"):
                campeao_sc = sc["campeao"]
                premio_sc = 10_000_000
                campeao_sc.financas.saldo += premio_sc
                self.noticias.append(Noticia(
                    titulo=f"SUPERCOPA REI — {campeao_sc.nome}",
                    texto=f"{campeao_sc.nome} venceu a Supercopa Rei! Prêmio: R$ {premio_sc:,.0f}",
                    categoria=CategoriaNoticia.GERAL,
                ))
                # Vice recebe R$5M
                vice_sc = sc["time1"] if sc["campeao"] == sc["time2"] else sc["time2"]
                vice_sc.financas.saldo += 5_000_000

        # 2b. Persistir estatísticas no banco
        self._persistir_resultados(resultados)
        self._processar_fantasy(resultados)

        # 2b2. Análise pós-jogo inteligente
        self._gerar_analise_pos_jogo(resultados)

        # 2c. Artilharia em memória (funciona mesmo sem save_id)
        self._atualizar_artilharia_memoria(resultados)

        # 2c2. Ranking mundial (ELO update)
        if self._ranking_intervalo_semanas <= 1 or self.semana % self._ranking_intervalo_semanas == 0:
            try:
                self.rankings_engine.processar_resultados(resultados, todos)
            except Exception as e:
                log.warning("Erro ao atualizar ranking: %s", e)

        # 2d. Diretoria — avaliar resultados do jogador
        self._avaliar_diretoria(resultados)

        # 2f. Sócios — flutuação baseada em resultados
        self._atualizar_socios(resultados)

        # 2g. IA demite técnicos com desempenho ruim (a cada 8 semanas)
        if self.semana % 8 == 0 and self.semana > 8:
            self._ia_demitir_tecnicos()

        # 2h. Sistemas avançados (promessas, vestiário, química, carreira, adaptação, objetivos)
        try:
            self._processar_sistemas_avancados(resultados)
        except Exception as e:
            log.warning("Erro ao processar sistemas avançados: %s", e)

        # 3. IA transferências (1 a cada 4 semanas)
        if self.mercado_aberto() and self.semana % self._mercado_ia_intervalo_semanas == 0:
            self.mercado.ia_fazer_transferencias(todos)
            self.noticias.extend(self.mercado.noticias)
            self.mercado.noticias.clear()

        # 3b. Deadline Day — última semana da janela
        for inicio, fim in self._janelas_transferencia:
            if self.semana == fim:
                try:
                    deadline_events = self.deadline_engine.processar_deadline(
                        todos, self.time_jogador, self.mercado)
                    for ev in deadline_events:
                        self.noticias.append(Noticia(
                            titulo="DEADLINE DAY: " + ev.get("tipo", "").replace("_", " ").title(),
                            texto=self._formatar_deadline_event(ev),
                            categoria=CategoriaNoticia.TRANSFERENCIA,
                        ))
                except Exception as e:
                    log.warning("Erro no Deadline Day: %s", e)

        # 3c. Reunião de Staff
        if self.time_jogador:
            try:
                reuniao = self.staff_meeting_engine.gerar_reuniao(
                    self.time_jogador, self.semana)
                if reuniao:
                    self._ultima_reuniao_staff = reuniao
            except Exception as e:
                log.warning("Erro na reunião de staff: %s", e)

        # 4. Finanças mensais (1 a cada 4 semanas)
        if self.semana % 4 == 0:
            for t in todos:
                t.financas.processar_mes(t.folha_salarial)
            # FFP check para o time do jogador
            if self.time_jogador:
                try:
                    violacoes = self.ffp_engine.verificar_violacao(self.time_jogador, self.temporada)
                    for v in violacoes:
                        self.noticias.append(Noticia(
                            titulo="⚠️ Alerta FFP",
                            texto=v,
                            categoria=CategoriaNoticia.FINANCAS,
                        ))
                except Exception as e:
                    log.warning("Erro ao verificar FFP: %s", e)

        # 5. Verificar obras no estádio
        self._processar_obras_estadio()

        # 6. Verificar fim de temporada
        if self.competicoes.temporada_encerrada() or self.semana >= SEMANAS_POR_TEMPORADA:
            self._processar_fim_temporada()

        # 6. Central de notificações — gerar mensagens automáticas
        if self._inbox_intervalo_semanas <= 1 or self.semana % self._inbox_intervalo_semanas == 0:
            try:
                self.inbox.processar_semana(
                    semana=self.semana,
                    temporada=self.temporada,
                    time_jogador=self.time_jogador,
                    todos_times=todos,
                    resultados=resultados,
                    noticias=self.noticias,
                    desempregado=getattr(self, '_desempregado', False),
                )
            except Exception as e:
                log.warning("Erro ao processar inbox: %s", e)

        # 7. Recordes e conquistas
        try:
            self._processar_recordes(resultados)
            self._processar_conquistas()
        except Exception as e:
            log.warning("Erro ao processar recordes/conquistas: %s", e)

        # 8. Auto-save (a cada 4 semanas)
        if (
            self.auto_save_ativo
            and self.auto_save_intervalo_semanas > 0
            and self.semana % self.auto_save_intervalo_semanas == 0
            and self.time_jogador
        ):
            try:
                self.salvar("autosave")
            except Exception:
                pass

        self._resumo_semana = self._montar_resumo_semana(resultados)
        return resultados

    def _atualizar_artilharia_memoria(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Rastreia artilharia em memória (independente de save_id)."""
        todos = {t.nome: t for t in (self.times_serie_a + self.times_serie_b +
                                      self.times_serie_c + self.times_serie_d +
                                      self.times_sem_divisao)}
        for pais_divs in self.times_europeus.values():
            for times_div in pais_divs.values():
                for t in times_div:
                    todos[t.nome] = t
        for comp, lista in resultados.items():
            for r in lista:
                for ev in r.eventos:
                    if ev.tipo in ("gol", "gol_falta"):
                        entry = self.artilharia_memoria.setdefault(ev.jogador_id, {
                            "gols": 0, "assistencias": 0,
                            "nome": ev.jogador_nome, "time": ev.time,
                        })
                        entry["gols"] += 1
                        if ev.detalhe.startswith("Assistência de "):
                            nome_assist = ev.detalhe[15:]
                            time_obj = todos.get(ev.time)
                            if time_obj:
                                for j in time_obj.jogadores:
                                    if j.nome == nome_assist:
                                        a_entry = self.artilharia_memoria.setdefault(j.id, {
                                            "gols": 0, "assistencias": 0,
                                            "nome": j.nome, "time": ev.time,
                                        })
                                        a_entry["assistencias"] += 1
                                        break

    def _processar_obras_estadio(self) -> None:
        """Process stadium construction progress each week."""
        if not self.time_jogador:
            return
        est = self.time_jogador.estadio
        if not hasattr(est, 'obras_em_andamento'):
            est.obras_em_andamento = []
        concluidas = []
        for obra in est.obras_em_andamento:
            obra["semanas_restantes"] = obra.get("semanas_restantes", 0) - 1
            if obra["semanas_restantes"] <= 0:
                concluidas.append(obra)
        for obra in concluidas:
            est.obras_em_andamento.remove(obra)
            tipo = obra.get("tipo", "")
            if tipo == "capacidade":
                est.capacidade += 5000
                est.cap_geral = getattr(est, 'cap_geral', 0) + 2500
                est.cap_arquibancada = getattr(est, 'cap_arquibancada', 0) + 1350
                est.cap_cadeira = getattr(est, 'cap_cadeira', 0) + 800
                est.cap_camarote = getattr(est, 'cap_camarote', 0) + 350
            elif tipo == "gramado":
                est.nivel_gramado = min(100, est.nivel_gramado + 10)
            elif tipo == "estrutura":
                est.nivel_estrutura = min(100, est.nivel_estrutura + 10)
            elif tipo == "iluminacao":
                est.nivel_estrutura = min(100, est.nivel_estrutura + 5)
            elif tipo == "camarotes":
                est.preco_ingresso = int(est.preco_ingresso * 1.3)
                est.nivel_estrutura = min(100, est.nivel_estrutura + 8)
            self.noticias.append(Noticia(
                titulo="🏗️ Obra concluída!",
                texto=f"A obra \"{obra.get('descricao', tipo)}\" no {est.nome} foi concluída com sucesso!",
                categoria=CategoriaNoticia.FINANCAS,
            ))

    def _processar_fim_temporada(self) -> None:
        todos = self.todos_times()
        noticias_fim = self.motor_temporada.processar_fim_temporada(todos)
        self.noticias.extend(noticias_fim)
        self.mercado.fim_temporada_contratos(todos)

        self._lib_qualificados = self._gerar_qualificados_libertadores()

        # Guardar campeões para Supercopa Rei da próxima temporada
        campeao_br = None
        campeao_copa = None
        if self.competicoes.brasileirao_a:
            classif = self.competicoes.brasileirao_a.classificacao()
            if classif:
                campeao_br = classif[0]
        if self.competicoes.copa_brasil and self.competicoes.copa_brasil.campeao:
            campeao_copa = self.competicoes.copa_brasil.campeao
        if campeao_br and campeao_copa and campeao_br != campeao_copa:
            self._supercopa_times = (campeao_br, campeao_copa)
        else:
            self._supercopa_times = None
        if self.competicoes.brasileirao_a and self.competicoes.brasileirao_b:
            classif_a = self.competicoes.brasileirao_a.classificacao()
            classif_b = self.competicoes.brasileirao_b.classificacao()
            rebaixados_a = classif_a[-4:]
            promovidos_b = classif_b[:4]

            for t in rebaixados_a:
                t.divisao = 2
                self.noticias.append(Noticia(
                    titulo=f"REBAIXAMENTO — {t.nome}",
                    texto=f"{t.nome} foi rebaixado para a Série B!",
                    categoria=CategoriaNoticia.GERAL,
                ))
            for t in promovidos_b:
                t.divisao = 1
                self.noticias.append(Noticia(
                    titulo=f"ACESSO — {t.nome}",
                    texto=f"{t.nome} conquistou o acesso à Série A!",
                    categoria=CategoriaNoticia.GERAL,
                ))

            novos_a = [t for t in classif_a if t not in rebaixados_a] + list(promovidos_b)
            novos_b = [t for t in classif_b if t not in promovidos_b] + list(rebaixados_a)
            self.times_serie_a = novos_a
            self.times_serie_b = novos_b

            # Premiação: campeão Série A
            campeao_a = classif_a[0] if classif_a else None
            if campeao_a:
                premio_campeao = 45_000_000
                campeao_a.financas.saldo += premio_campeao
                self.noticias.append(Noticia(
                    titulo=f"CAMPEÃO BRASILEIRO — {campeao_a.nome}",
                    texto=f"{campeao_a.nome} é o campeão do Brasileirão {self.temporada}! Prêmio: R$ {premio_campeao:,.0f}",
                    categoria=CategoriaNoticia.GERAL,
                ))

        # Promoção / Rebaixamento Série B ↔ C (4 times)
        if self.competicoes.brasileirao_b and self.competicoes.brasileirao_c:
            classif_b = self.competicoes.brasileirao_b.classificacao()
            classif_c = self.competicoes.brasileirao_c.classificacao()
            rebaixados_b = classif_b[-4:]

            # Promovidos da C: via mata-mata (semifinalistas) se disponível
            promovidos_c = []
            mata_mata_c = getattr(self.competicoes.brasileirao_c, "mata_mata", None)
            if mata_mata_c and getattr(mata_mata_c, "classificados", None):
                for fase in mata_mata_c.classificados:
                    if len(fase) == 4:
                        promovidos_c = list(fase)
                        break
            if not promovidos_c:
                promovidos_c = classif_c[:4]

            for t in rebaixados_b:
                t.divisao = 3
                self.noticias.append(Noticia(
                    titulo=f"REBAIXAMENTO — {t.nome}",
                    texto=f"{t.nome} foi rebaixado para a Série C!",
                    categoria=CategoriaNoticia.GERAL,
                ))
            for t in promovidos_c:
                t.divisao = 2
                self.noticias.append(Noticia(
                    titulo=f"ACESSO — {t.nome}",
                    texto=f"{t.nome} conquistou o acesso à Série B!",
                    categoria=CategoriaNoticia.GERAL,
                ))

            novos_b = [t for t in classif_b if t not in rebaixados_b] + list(promovidos_c)
            novos_c = [t for t in classif_c if t not in promovidos_c] + list(rebaixados_b)
            self.times_serie_b = novos_b
            self.times_serie_c = novos_c

        # Promoção / Rebaixamento Série C ↔ D (4 rebaixados da C, 4 promovidos da D)
        if self.competicoes.brasileirao_c and self.competicoes.brasileirao_d:
            classif_c = self.competicoes.brasileirao_c.classificacao()
            classif_d = self.competicoes.brasileirao_d.classificacao()
            rebaixados_c = classif_c[-4:]
            promovidos_d = []
            mata_mata_d = getattr(self.competicoes.brasileirao_d, "mata_mata", None)
            if mata_mata_d and getattr(mata_mata_d, "classificados", None):
                for fase in mata_mata_d.classificados:
                    if len(fase) == 4:
                        promovidos_d = list(fase)
                        break
            if not promovidos_d:
                promovidos_d = classif_d[:4]

            for t in rebaixados_c:
                t.divisao = 4
                self.noticias.append(Noticia(
                    titulo=f"REBAIXAMENTO — {t.nome}",
                    texto=f"{t.nome} foi rebaixado para a Série D!",
                    categoria=CategoriaNoticia.GERAL,
                ))
            for t in promovidos_d:
                t.divisao = 3
                self.noticias.append(Noticia(
                    titulo=f"ACESSO — {t.nome}",
                    texto=f"{t.nome} conquistou o acesso à Série C!",
                    categoria=CategoriaNoticia.GERAL,
                ))

            novos_c = [t for t in classif_c if t not in rebaixados_c] + list(promovidos_d)
            novos_d = [t for t in classif_d if t not in promovidos_d] + list(rebaixados_c)
            self.times_serie_c = novos_c
            self.times_serie_d = novos_d

        # Estaduais — premiação e rebaixamento
        for uf, est in self.competicoes.estaduais.items():
            if est.campeao:
                premio_est = 5_000_000
                est.campeao.financas.saldo += premio_est
                self.noticias.append(Noticia(
                    titulo=f"CAMPEÃO {est.nome.upper()}",
                    texto=f"{est.campeao.nome} é o campeão do {est.nome}! Prêmio: R$ {premio_est:,.0f}",
                    categoria=CategoriaNoticia.GERAL,
                ))
            if est.rebaixados:
                for t in est.rebaixados:
                    self.noticias.append(Noticia(
                        titulo=f"REBAIXAMENTO ESTADUAL — {t.nome}",
                        texto=f"{t.nome} foi rebaixado no {est.nome}!",
                        categoria=CategoriaNoticia.GERAL,
                    ))

        # Copa do Brasil — premiação
        if self.competicoes.copa_brasil and self.competicoes.copa_brasil.campeao:
            copa_campeao = self.competicoes.copa_brasil.campeao
            premio_copa = 70_000_000
            copa_campeao.financas.saldo += premio_copa
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA COPA — {copa_campeao.nome}",
                texto=f"{copa_campeao.nome} venceu a Copa do Brasil! Prêmio: R$ {premio_copa:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))
            # Copa champion qualifies for Libertadores
            if copa_campeao not in self._lib_qualificados:
                self._lib_qualificados.append(copa_campeao)

        # Libertadores — premiação
        if self.competicoes.libertadores and self.competicoes.libertadores.campeao:
            lib_campeao = self.competicoes.libertadores.campeao
            premio_lib = 120_000_000  # ~US$ 23M
            lib_campeao.financas.saldo += premio_lib
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA LIBERTADORES — {lib_campeao.nome}",
                texto=f"{lib_campeao.nome} venceu a CONMEBOL Libertadores! Prêmio: R$ {premio_lib:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # Sul-Americana — premiação
        if self.competicoes.sul_americana and self.competicoes.sul_americana.campeao:
            sula_campeao = self.competicoes.sul_americana.campeao
            premio_sula = 26_000_000  # ~US$ 5M
            sula_campeao.financas.saldo += premio_sula
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA SUL-AMERICANA — {sula_campeao.nome}",
                texto=f"{sula_campeao.nome} venceu a CONMEBOL Sul-Americana! Prêmio: R$ {premio_sula:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # Champions League — premiação
        if self.competicoes.champions_league and self.competicoes.champions_league.campeao:
            cl_campeao = self.competicoes.champions_league.campeao
            premio_cl = 430_000_000  # ~€80M
            cl_campeao.financas.saldo += premio_cl
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA UEFA CHAMPIONS LEAGUE — {cl_campeao.nome}",
                texto=f"{cl_campeao.nome} conquistou a Champions League! Prêmio: R$ {premio_cl:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # Europa League — premiação
        if self.competicoes.europa_league and self.competicoes.europa_league.campeao:
            el_campeao = self.competicoes.europa_league.campeao
            premio_el = 47_000_000  # ~€8.6M
            el_campeao.financas.saldo += premio_el
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA UEFA EUROPA LEAGUE — {el_campeao.nome}",
                texto=f"{el_campeao.nome} conquistou a Europa League! Prêmio: R$ {premio_el:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # Conference League — premiação
        if self.competicoes.conference_league and self.competicoes.conference_league.campeao:
            ecl_campeao = self.competicoes.conference_league.campeao
            premio_ecl = 27_000_000  # ~€5M
            ecl_campeao.financas.saldo += premio_ecl
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA UEFA CONFERENCE LEAGUE — {ecl_campeao.nome}",
                texto=f"{ecl_campeao.nome} conquistou a Conference League! Prêmio: R$ {premio_ecl:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # AFC Champions League — premiação
        if self.competicoes.afc_champions and self.competicoes.afc_champions.campeao:
            afc_campeao = self.competicoes.afc_champions.campeao
            premio_afc = 62_000_000  # ~US$ 12M
            afc_campeao.financas.saldo += premio_afc
            self.noticias.append(Noticia(
                titulo=f"CAMPEÃO DA AFC CHAMPIONS LEAGUE — {afc_campeao.nome}",
                texto=f"{afc_campeao.nome} conquistou a AFC Champions League! Prêmio: R$ {premio_afc:,.0f}",
                categoria=CategoriaNoticia.GERAL,
            ))

        # Promoção / Rebaixamento EUROPEU (conforme regulamento por liga)
        # Número de rebaixados/promovidos por liga principal
        _league_relegation = {
            "ING": 3, "ESP": 3, "ITA": 3, "ALE": 3, "FRA": 3,
            "POR": 3, "TUR": 3, "GRE": 3,
            "HOL": 2, "RUS": 2, "SUI": 2, "AUT": 2,
            "BEL": 1, "ESC": 1,
            "ARG": 4, "CHI": 2, "COL": 2, "MEX": 2,
            "JAP": 2, "CHN": 2, "ARS": 2,
        }
        _default_relegation = 2
        for pais, divs in self.times_europeus.items():
            div_nums = sorted(divs.keys())
            for i in range(len(div_nums) - 1):
                sup = div_nums[i]
                inf = div_nums[i + 1]
                liga_sup = self.competicoes.ligas_europeias.get(pais, {}).get(sup)
                liga_inf = self.competicoes.ligas_europeias.get(pais, {}).get(inf)
                if not liga_sup or not liga_inf:
                    continue
                classif_sup = liga_sup.classificacao()
                classif_inf = liga_inf.classificacao()
                n_troca = _league_relegation.get(pais, _default_relegation)
                # Não pode trocar mais times do que cada divisão comporta
                n_troca = min(n_troca, len(classif_sup) // 4, len(classif_inf) // 4)
                if n_troca < 1:
                    continue
                reb = classif_sup[-n_troca:]
                prom = classif_inf[:n_troca]
                for t in reb:
                    self.noticias.append(Noticia(
                        titulo=f"REBAIXAMENTO — {t.nome}",
                        texto=f"{t.nome} foi rebaixado na liga europeia!",
                        categoria=CategoriaNoticia.GERAL,
                    ))
                for t in prom:
                    self.noticias.append(Noticia(
                        titulo=f"ACESSO — {t.nome}",
                        texto=f"{t.nome} subiu de divisão na liga europeia!",
                        categoria=CategoriaNoticia.GERAL,
                    ))
                novos_sup = [t for t in classif_sup if t not in reb] + list(prom)
                novos_inf = [t for t in classif_inf if t not in prom] + list(reb)
                self.times_europeus[pais][sup] = novos_sup
                self.times_europeus[pais][inf] = novos_inf

        # Premiações de fim de temporada (Bola de Ouro, Artilheiro, etc.)
        try:
            todos = self.todos_times()
            artilharia = {
                entry.get("nome", ""): entry.get("gols", 0)
                for entry in self.artilharia_memoria.values()
                if entry.get("nome") and entry.get("gols", 0) > 0
            }
            notas_medias = {
                j.id: getattr(getattr(j, "historico_temporada", None), "nota_media", 6.0)
                for t in todos
                for j in t.jogadores
            }
            awards = self.premiacoes.calcular_premiacoes(
                self.temporada,
                todos,
                artilharia,
                notas_medias,
                competicao_principal="serie_a",
            )
            for a in awards:
                self.noticias.append(Noticia(
                    titulo=f"PRÊMIO: {a.tipo.value}",
                    texto=f"{a.jogador_nome} ({a.time_nome}) recebeu o prêmio de {a.tipo.value}!",
                    categoria=CategoriaNoticia.GERAL,
                ))
                # Registrar no Hall of Fame
                self.hall_of_fame.registrar(
                    jogador_nome=a.jogador_nome,
                    time_nome=a.time_nome,
                    temporada=self.temporada,
                    categoria=a.tipo.name.lower(),
                    descricao=f"{a.tipo.value} — {a.competicao or 'Temporada'}",
                    valor=a.valor,
                )
            # FFP penalidades de fim de temporada
            if self.time_jogador:
                penalidades = self.ffp_engine.aplicar_penalidades(self.time_jogador, self.temporada)
                for p in penalidades:
                    self.noticias.append(Noticia(
                        titulo="PENALIDADE FFP",
                        texto=p,
                        categoria=CategoriaNoticia.FINANCAS,
                    ))
            # Conquista: título
            if self.time_jogador and self.competicoes.brasileirao_a:
                campeao = self.competicoes.brasileirao_a.classificacao()
                if campeao and campeao[0].nome == self.time_jogador.nome:
                    titulos = getattr(self, '_total_titulos', 0) + 1
                    self._total_titulos = titulos
                    self.conquistas.set_progresso("primeiro_titulo", 1)
                    self.conquistas.set_progresso("penta", titulos)
                    self.conquistas.set_progresso("deca", titulos)
                    self.recordes.registrar_titulo("Brasileirão", self.temporada)
        except Exception as e:
            log.warning("Erro ao calcular premiações: %s", e)

        self._normalizar_divisoes_brasileiras()
        self.temporada += 1
        self.semana = 0
        self.artilharia_memoria = {}
        self._iniciar_temporada()
        self.noticias.append(Noticia(
            titulo=f"NOVA TEMPORADA {self.temporada}",
            texto="A nova temporada começou!",
            categoria=CategoriaNoticia.GERAL,
        ))

    # ═══════════════════════════════════════════════════════════
    #  SAVE / LOAD
    # ═══════════════════════════════════════════════════════════

    def salvar(self, nome: str) -> str:
        from save_system.save_manager import serializar_jogo
        dados = serializar_jogo(self)
        meta = {
            "nome": nome,
            "temporada": self.temporada,
            "semana": self.semana,
            "time_jogador": self.time_jogador.nome if self.time_jogador else "",
        }
        relatorio = self.save_integrity.save(nome, dados, meta)
        self.save_nome = nome
        self._ultimo_relatorio_save = relatorio
        log.info("Jogo salvo com integridade: %s", nome)
        return nome

    def carregar(self, nome: str) -> bool:
        from save_system.save_manager import desserializar_jogo
        try:
            dados_bytes, relatorio = self.save_integrity.load(
                nome,
                attempt_recovery=True,
            )
        except (FileNotFoundError, ValueError) as e:
            log.warning("Falha ao carregar save '%s': %s", nome, e)
            return False
        desserializar_jogo(self, dados_bytes)
        self.save_nome = nome
        self._ultimo_relatorio_save = relatorio
        log.info("Jogo carregado: %s", nome)
        return True

    def listar_saves(self) -> List[dict]:
        import os, json as _json
        os.makedirs(SAVES_DIR, exist_ok=True)
        saves = []
        for fn in sorted(os.listdir(SAVES_DIR)):
            if not fn.endswith(".sav"):
                continue
            nome = fn[:-4]
            sav_path = os.path.join(SAVES_DIR, fn)
            meta_path = os.path.join(SAVES_DIR, nome + ".meta")
            mtime = os.path.getmtime(sav_path)
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        hdr = _json.load(f)
                    integridade = self.save_integrity.validate(nome)
                    saves.append({
                        "nome": nome,
                        "temporada": hdr.get("temporada", 0),
                        "semana": hdr.get("semana", 0),
                        "time_jogador": hdr.get("time_jogador", ""),
                        "data_modificacao": mtime,
                        "integridade_ok": integridade.get("ok", False),
                        "integridade_erro": integridade.get("error", ""),
                        "backups": integridade.get("backups", 0),
                        "game_version": hdr.get("game_version", ""),
                    })
                    continue
                except Exception:
                    pass
            # Fallback: decompress .sav header (for legacy saves without .meta)
            try:
                dados_bytes, integridade = self.save_integrity.load(
                    nome,
                    attempt_recovery=False,
                )
                raw = dados_bytes.decode("utf-8")
                hdr = _json.loads(raw)
                saves.append({
                    "nome": nome,
                    "temporada": hdr.get("temporada", 0),
                    "semana": hdr.get("semana", 0),
                    "time_jogador": hdr.get("time_jogador_nome", ""),
                    "data_modificacao": mtime,
                    "integridade_ok": integridade.get("ok", False),
                    "integridade_erro": integridade.get("error", ""),
                    "backups": integridade.get("backups", 0),
                    "game_version": integridade.get("game_version", ""),
                })
            except Exception:
                integridade = self.save_integrity.validate(nome)
                saves.append({
                    "nome": nome,
                    "temporada": 0,
                    "semana": 0,
                    "time_jogador": "",
                    "data_modificacao": 0,
                    "integridade_ok": integridade.get("ok", False),
                    "integridade_erro": integridade.get("error", "save_unreadable"),
                    "backups": integridade.get("backups", 0),
                    "game_version": integridade.get("game_version", ""),
                })
        saves.sort(key=lambda s: s["data_modificacao"], reverse=True)
        return saves

    def deletar_save(self, nome: str) -> bool:
        deleted = self.save_integrity.delete(nome, include_backups=True)
        if self.save_nome == nome:
            self.save_nome = None
            self._ultimo_relatorio_save = None
        return bool(deleted.get("ok"))

    def validar_save(self, nome: str) -> Dict:
        return self.save_integrity.validate(nome)

    def restaurar_ultimo_backup(self, nome: str) -> Dict:
        resultado = self.save_integrity.restore_latest_backup(nome)
        if resultado.get("ok"):
            self._ultimo_relatorio_save = self.save_integrity.validate(nome)
            if self.save_nome == nome:
                self.carregar(nome)
        return resultado

    def get_asset_registry(self) -> Dict:
        return self.asset_registry.to_api_dict(self.licensing)

    def get_license_status(self) -> Dict:
        return self.license_service.status()

    def ativar_licenca(self, serial: str) -> Dict:
        return self.license_service.activate(serial)

    # ═══════════════════════════════════════════════════════════
    #  DIRETORIA — METAS E SATISFAÇÃO
    # ═══════════════════════════════════════════════════════════

    def _definir_metas_diretoria(self) -> None:
        """Set board objectives based on division and prestige."""
        t = self.time_jogador
        if not t:
            return
        d = t.diretoria
        d.satisfacao = 50
        d.paciencia = 60
        d.pressao_torcida = 30
        d.demitido = False
        d.mensagens = []

        if t.divisao == 1:
            if t.prestigio >= 85:
                d.meta_principal = "Título do Brasileirão"
                d.meta_minima = "Top 6 (Libertadores)"
                d.paciencia = 40
            elif t.prestigio >= 70:
                d.meta_principal = "Classificação para Libertadores (Top 6)"
                d.meta_minima = "Top 12"
                d.paciencia = 55
            else:
                d.meta_principal = "Permanecer na Série A"
                d.meta_minima = "Não rebaixar (Top 16)"
                d.paciencia = 65
        elif t.divisao == 2:
            if t.prestigio >= 65:
                d.meta_principal = "Acesso à Série A"
                d.meta_minima = "Top 8"
                d.paciencia = 50
            else:
                d.meta_principal = "Campanha no G8"
                d.meta_minima = "Não rebaixar"
                d.paciencia = 60
        elif t.divisao == 3:
            d.meta_principal = "Acesso à Série B"
            d.meta_minima = "Campanha no G8"
            d.paciencia = 65
        else:
            d.meta_principal = "Acesso à divisão superior"
            d.meta_minima = "Boa campanha"
            d.paciencia = 70

    def _avaliar_diretoria(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Evaluate board satisfaction after weekly results."""
        t = self.time_jogador
        if not t or t.diretoria.demitido:
            return
        d = t.diretoria
        nome = t.nome

        # Find the player's match result
        jogou = False
        for comp, lista in resultados.items():
            for r in lista:
                if r.time_casa != nome and r.time_fora != nome:
                    continue
                jogou = True
                eh_casa = r.time_casa == nome
                gols_pro = r.gols_casa if eh_casa else r.gols_fora
                gols_contra = r.gols_fora if eh_casa else r.gols_casa

                if gols_pro > gols_contra:  # Vitória
                    d.satisfacao = min(100, d.satisfacao + 4)
                    d.paciencia = min(100, d.paciencia + 2)
                    d.pressao_torcida = max(0, d.pressao_torcida - 3)
                elif gols_pro == gols_contra:  # Empate
                    d.satisfacao = max(0, d.satisfacao - 1)
                    d.pressao_torcida = min(100, d.pressao_torcida + 1)
                else:  # Derrota
                    d.satisfacao = max(0, d.satisfacao - 5)
                    d.paciencia = max(0, d.paciencia - 3)
                    d.pressao_torcida = min(100, d.pressao_torcida + 5)
                    # Big defeats (3+ goal difference)
                    if gols_contra - gols_pro >= 3:
                        d.satisfacao = max(0, d.satisfacao - 5)
                        d.paciencia = max(0, d.paciencia - 5)

        if not jogou:
            return

        # Generate messages based on satisfaction level
        d.mensagens = []
        if d.satisfacao >= 80:
            d.mensagens.append("A diretoria está muito satisfeita com seu trabalho!")
        elif d.satisfacao >= 60:
            d.mensagens.append("A diretoria aprova a campanha até o momento.")
        elif d.satisfacao >= 40:
            d.mensagens.append("A diretoria espera uma melhora nos resultados.")
        elif d.satisfacao >= 20:
            d.mensagens.append("A diretoria está insatisfeita. Resultados precisam melhorar urgentemente!")
        else:
            d.mensagens.append("ATENÇÃO: A diretoria considera seriamente sua demissão!")

        if d.pressao_torcida >= 70:
            d.mensagens.append("A torcida está pressionando por resultados melhores.")

        # Check sacking condition
        if d.satisfacao <= 10 and d.paciencia <= 10 and self.semana >= 10:
            d.demitido = True
            d.mensagens = ["Você foi demitido pela diretoria devido aos resultados insatisfatórios."]
            self.noticias.append(Noticia(
                titulo="Técnico demitido!",
                texto=f"A diretoria do {t.nome} demitiu o técnico após resultados ruins.",
                categoria=CategoriaNoticia.GERAL,
            ))
            # Iniciar fluxo de desemprego
            try:
                self.iniciar_desemprego()
            except Exception as e:
                log.warning("Erro ao iniciar desemprego após demissão: %s", e)

    def _ajustar_financas_temporada(self) -> None:
        """Set TV revenue and sponsorship based on division for all teams."""
        tv_por_divisao = {1: 3_000_000, 2: 800_000, 3: 300_000, 4: 100_000}
        patrocinio_base = {1: 2_000_000, 2: 600_000, 3: 200_000, 4: 80_000}
        patrocinadores_genericos = {
            1: [
                "Ultra Sports", "Master Eleven", "Prime Arena", "Altiva Bank",
                "Nexus Capital", "Pulse Energy", "Atlas Mobility", "North Grid",
                "Crown Pay", "Vertex Group",
            ],
            2: [
                "Regional Max", "Arena Partner", "Futura Telecom", "Liga Invest",
                "Sprint Hub", "Metro Cargo", "UniCred Brasil", "Impacto Saúde",
                "Delta Seguro", "Vale Digital",
            ],
            3: [
                "Parceiro Local", "Sponsor Regional", "Rede Municipal",
                "Comercial Prime", "Grupo Horizonte", "Plataforma BR",
                "Conecta+", "Mercado Centro", "Nova Via", "Eixo Sports",
            ],
            4: [
                "Parceiro Local", "Sponsor Regional", "Rede Municipal",
                "Comercial Prime", "Grupo Horizonte", "Plataforma BR",
                "Conecta+", "Mercado Centro", "Nova Via", "Eixo Sports",
            ],
        }
        materiais_genericos = [
            "Ultrafoot Pro", "Vertex Wear", "Arena Lab", "North Kit",
            "Pulse Gear", "Tatica One", "Aster Sports", "Forza Lab",
        ]
        patrocinadores_costas = [
            "Backline+", "Arena Cargo", "Nexa Trade", "Mobi Fleet",
            "Cobrex", "LogiMax", "Seguro BR", "Sprint Net",
        ]
        patrocinadores_manga = [
            "Capital One BR", "Axis Bank", "Union Credito", "Conta Azul",
            "Flow Pay", "Lume Invest", "Grid Bank", "Aurora Finance",
        ]
        PATROCINADORES_A = [
            "Crefisa", "Esportes da Sorte", "Betano", "Pixbet", "Superbet",
            "MRV", "Blaze", "Vai de Bet", "Parimatch", "Estrela Bet",
            "BetNacional", "Casa de Apostas", "RecargaPay", "Adidas",
            "Nike", "Puma", "Banco do Brasil", "Itaú", "Brahma", "Ambev",
        ]
        PATROCINADORES_B = [
            "EstrelaBet", "BetNacional", "Novibet", "KTO", "Penalty",
            "Topper", "Umbro", "Lupo", "Joma", "Águia Sports",
            "Volt", "Super Bolla", "Duelo", "Kappa", "Rinat",
        ]
        PATROCINADORES_CD = [
            "Topper", "Penalty", "Super Bolla", "Duelo", "Icone Sports",
            "Volt", "Kanxa", "BSide", "N2 Sports", "Lupo",
        ]

        for t in self.todos_times():
            div = t.divisao if t.divisao in tv_por_divisao else 4
            fator_prestigio = t.prestigio / 80  # scales around 1.0
            t.financas.receita_tv_mensal = int(tv_por_divisao[div] * fator_prestigio)
            # Only reset sponsor if it's the default low value
            if t.financas.receita_patrocinio_mensal <= 500_000:
                t.financas.receita_patrocinio_mensal = int(patrocinio_base[div] * fator_prestigio)
            # Preserve imported sponsor data and only fall back to generic placeholders.
            if t.financas.patrocinador_principal in ("Sem patrocinador", ""):
                t.financas.patrocinador_principal = random.choice(patrocinadores_genericos[div])
            # Material esportivo
            if not t.financas.material_esportivo:
                t.financas.material_esportivo = random.choice(
                    materiais_genericos[:5] if div <= 2 else materiais_genericos
                )
            # Patrocinador costas
            if not t.financas.patrocinador_costas:
                t.financas.patrocinador_costas = random.choice(patrocinadores_costas)
            # Patrocinador manga
            if not t.financas.patrocinador_manga:
                MANGA = ["Banco do Brasil", "Itaú", "Caixa", "Bradesco", "BTG Pactual",
                         "XP", "C6 Bank", "Inter", "Nubank", "PagBank", "Serasa"]
                t.financas.patrocinador_manga = random.choice(patrocinadores_manga)

    def _atualizar_socios(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Adjust membership count based on match results for all teams that played."""
        todos_dict = {t.nome: t for t in self.todos_times()}
        for comp, lista in resultados.items():
            for r in lista:
                for nome_time, gp, gc in [
                    (r.time_casa, r.gols_casa, r.gols_fora),
                    (r.time_fora, r.gols_fora, r.gols_casa),
                ]:
                    t = todos_dict.get(nome_time)
                    if not t:
                        continue
                    f = t.financas
                    if gp > gc:
                        f.num_socios = min(f.num_socios + random.randint(50, 200), 200_000)
                    elif gp < gc:
                        f.num_socios = max(f.num_socios - random.randint(30, 100), 500)

    def _ia_demitir_tecnicos(self) -> None:
        """IA fires coaches of underperforming AI teams."""
        from core.enums import TipoStaff
        import random as _rnd
        for t in self.todos_times():
            if t.eh_jogador:
                continue
            jogos = t.vitorias + t.empates + t.derrotas
            if jogos < 5:
                continue
            aprov = t.pontos / (jogos * 3) if jogos else 0
            # Fire if approval below 30% (very bad)
            if aprov < 0.30 and _rnd.random() < 0.4:
                treinador = t.staff_por_tipo(TipoStaff.TREINADOR)
                nome_tecnico = treinador.nome if treinador else "Desconhecido"
                self.tecnicos_demitidos.append({
                    "nome": nome_tecnico, "time": t.nome,
                    "semana": self.semana, "temporada": self.temporada,
                    "aproveitamento": round(aprov * 100, 1),
                })
                # Replace with new coach
                if treinador:
                    treinador.nome = _rnd.choice([
                        "Carlos Silva", "Roberto Mendes", "Luiz Almeida",
                        "Fernando Costa", "Marcos Pereira", "André Santos",
                        "Paulo Oliveira", "Ricardo Lima", "Eduardo Souza",
                        "Gustavo Ferreira", "Jorge Martins", "Renato Gaúcho Jr",
                    ])
                    treinador.habilidade = _rnd.randint(35, 65)
                self.noticias.append(Noticia(
                    titulo=f"Técnico demitido: {nome_tecnico}",
                    texto=f"{nome_tecnico} foi demitido do {t.nome} por mau desempenho ({round(aprov*100,1)}% aproveitamento).",
                ))

    # ═══════════════════════════════════════════════════════════
    #  SISTEMAS AVANÇADOS
    # ═══════════════════════════════════════════════════════════

    def _processar_sistemas_avancados(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        t = self.time_jogador
        if not t:
            return

        # Promessas
        evts = self.promessas_engine.processar_semana(t)
        for e in evts:
            if e.get("tipo") == "promessa_quebrada":
                self.noticias.append(Noticia(
                    titulo="Promessa não cumprida!",
                    texto=e.get("descricao", "Uma promessa não foi cumprida."),
                    categoria=CategoriaNoticia.GERAL,
                ))

        # Resultado da semana para vestiário
        res_semana = None
        nome = t.nome
        for comp, lista in resultados.items():
            for r in lista:
                if r.time_casa == nome or r.time_fora == nome:
                    eh_casa = r.time_casa == nome
                    gp = r.gols_casa if eh_casa else r.gols_fora
                    gc = r.gols_fora if eh_casa else r.gols_casa
                    res_semana = {"resultado": "vitoria" if gp > gc else "empate" if gp == gc else "derrota"}
                    break
            if res_semana:
                break

        # Vestiário (dinâmica de grupo)
        evts_vest = self.vestiario_engine.processar_semana(t, res_semana)
        for e in evts_vest:
            if e.get("tipo") == "conflito":
                self.noticias.append(Noticia(
                    titulo="Problema no vestiário!",
                    texto=e.get("descricao", "Tensão no vestiário."),
                    categoria=CategoriaNoticia.GERAL,
                ))

        # Química tática
        self.quimica_engine.processar_semana(t)

        # Carreira do treinador
        self.carreira_engine.registrar_semana(t, resultados)
        self.carreira_engine.atualizar_reputacao_semanal(t)

        # Adaptação cultural
        evts_adapt = self.adaptacao_engine.processar_semana()
        for e in evts_adapt:
            if e.get("progresso", 0) >= 100:
                self.noticias.append(Noticia(
                    titulo="Jogador adaptado!",
                    texto=e.get("descricao", "Um jogador se adaptou totalmente."),
                    categoria=CategoriaNoticia.GERAL,
                ))

        # Objetivos pessoais
        evts_obj = self.objetivos_engine.atualizar_progresso(t, resultados)
        for e in evts_obj:
            self.noticias.append(Noticia(
                titulo="Objetivo atingido!",
                texto=e.get("descricao", "Um jogador atingiu seu objetivo pessoal."),
                categoria=CategoriaNoticia.GERAL,
            ))

    def _gerar_analise_pos_jogo(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        t = self.time_jogador
        if not t:
            return
        nome = t.nome
        todos_dict = {tm.nome: tm for tm in self.todos_times()}
        for comp, lista in resultados.items():
            for r in lista:
                if r.time_casa == nome or r.time_fora == nome:
                    casa_t = todos_dict.get(r.time_casa)
                    fora_t = todos_dict.get(r.time_fora)
                    self.ultima_analise = self.analise_engine.analisar(
                        r, nome, casa_time=casa_t, fora_time=fora_t,
                    )
                    return

    def _inicializar_fantasy(self) -> None:
        """Inicializa a liga fantasy com a base brasileira ja carregada."""
        try:
            pool = self.times_serie_a + self.times_serie_b
            if not pool:
                return
            nome_base = getattr(self, "_tecnico_nome", "") or (
                self.time_jogador.nome if self.time_jogador else "Meu Time"
            )
            self.fantasy.criar_liga(pool, nome_jogador=f"{nome_base} Fantasy")
        except Exception as e:
            log.warning("Erro ao inicializar fantasy: %s", e)

    def _processar_fantasy(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Atualiza a liga fantasy com os resultados reais da semana."""
        if not hasattr(self, "fantasy"):
            return
        liga = getattr(self.fantasy, "liga", None)
        if liga is None:
            return
        if not getattr(liga, "times", None):
            self._inicializar_fantasy()
            if not getattr(self.fantasy.liga, "times", None):
                return

        mapa_times = {t.nome: t for t in self.todos_times()}
        jogos: List[ResultadoPartida] = []
        times_casa: List[Time] = []
        times_fora: List[Time] = []

        for lista in resultados.values():
            for resultado in lista:
                casa = mapa_times.get(resultado.time_casa)
                fora = mapa_times.get(resultado.time_fora)
                if not casa or not fora:
                    continue
                jogos.append(resultado)
                times_casa.append(casa)
                times_fora.append(fora)

        if not jogos:
            return

        try:
            self.fantasy.processar_rodada(jogos, times_casa, times_fora)
        except Exception as e:
            log.warning("Erro ao processar fantasy: %s", e)

    def iniciar_desemprego(self) -> None:
        """Marca jogador como desempregado e gera ofertas iniciais."""
        if self.time_jogador:
            old = self.time_jogador
            self.carreira_engine.registrar_demissao(old.nome, self.semana)
            old.eh_jogador = False
            old.diretoria.demitido = False
        self.time_jogador = None
        self._desempregado = True
        self._semanas_desempregado = 0
        self._ofertas_emprego = []
        self._gerar_ofertas_emprego()

    def _gerar_ofertas_emprego(self) -> None:
        """Gera ofertas de emprego baseadas na reputação."""
        import random as _rnd
        rep = self.carreira_engine.carreira.reputacao
        todos = self.todos_times()
        _rnd.shuffle(todos)

        # Decay: fewer offers over time, lower quality
        max_ofertas = max(1, 5 - self._semanas_desempregado // 4)
        # Filter by reputation bracket
        candidatos = []
        for t in todos:
            if t == self.time_jogador:
                continue
            # Higher rep = access to better teams
            if rep >= 70 and t.prestigio >= 60:
                candidatos.append(t)
            elif rep >= 40 and t.prestigio >= 30:
                candidatos.append(t)
            elif rep < 40 and t.prestigio <= 60:
                candidatos.append(t)
            if len(candidatos) >= max_ofertas * 3:
                break

        _rnd.shuffle(candidatos)
        self._ofertas_emprego = [{
            "nome": t.nome, "divisao": t.divisao,
            "overall": t.overall_medio,
            "prestigio": t.prestigio,
            "pais": getattr(t, 'estado', 'BR'),
        } for t in candidatos[:max_ofertas]]

    def avancar_semana_desempregado(self) -> Dict:
        """Avança o jogo enquanto desempregado. Retorna info do estado."""
        self.semana += 1
        self._semanas_desempregado += 1
        self.noticias = []

        # Reputação decai com desemprego
        if self._semanas_desempregado % 4 == 0:
            self.carreira_engine.carreira.reputacao = max(
                0, self.carreira_engine.carreira.reputacao - 2
            )

        # O jogo continua rodando (IA joga)
        todos = self.todos_times()
        if self.motor_temporada.pre_temporada_ativa:
            noticias_sem = self.motor_temporada.processar_pre_temporada(todos)
        else:
            noticias_sem = self.motor_temporada.processar_semana(todos)
        self.noticias.extend(noticias_sem)

        resultados = self.competicoes.avancar_semana()
        self.ultimo_resultado = resultados

        # IA transferências e finanças
        if self.mercado_aberto() and self.semana % self._mercado_ia_intervalo_semanas == 0:
            self.mercado.ia_fazer_transferencias(todos)
        if self.semana % 4 == 0:
            for t in todos:
                t.financas.processar_mes(t.folha_salarial)

        # IA demite técnicos
        if self.semana % 8 == 0 and self.semana > 8:
            self._ia_demitir_tecnicos()

        # Fim de temporada
        if self.competicoes.temporada_encerrada() or self.semana >= SEMANAS_POR_TEMPORADA:
            self._processar_fim_temporada()

        # Novas ofertas a cada 2 semanas
        if self._semanas_desempregado % 2 == 0:
            self._gerar_ofertas_emprego()

        # A inbox segue gerando mensagens enquanto o técnico está sem clube.
        if self._inbox_intervalo_semanas <= 1 or self.semana % self._inbox_intervalo_semanas == 0:
            try:
                self.inbox.processar_semana(
                    semana=self.semana,
                    temporada=self.temporada,
                    time_jogador=None,
                    todos_times=todos,
                    resultados=resultados,
                    noticias=self.noticias,
                    desempregado=True,
                )
            except Exception as e:
                log.warning("Erro ao processar inbox no desemprego: %s", e)

        return {
            "semana": self.semana,
            "temporada": self.temporada,
            "semanas_desempregado": self._semanas_desempregado,
            "reputacao": self.carreira_engine.carreira.reputacao,
            "ofertas": self._ofertas_emprego,
            "noticias": [{"titulo": n.titulo, "texto": n.texto} for n in self.noticias[:5]],
        }

    def aceitar_oferta_emprego(self, nome_time: str) -> bool:
        """Aceita uma oferta de emprego durante o desemprego."""
        novo = None
        for t in self.todos_times():
            if t.nome == nome_time:
                novo = t
                break
        if not novo:
            return False
        novo.eh_jogador = True
        self.time_jogador = novo
        self._desempregado = False
        self._semanas_desempregado = 0
        self._ofertas_emprego = []
        self._definir_metas_diretoria()
        self.carreira_engine.registrar_novo_time(novo.nome, "", 0)
        # Gerar novos objetivos para o novo time
        self.objetivos_engine.gerar_objetivos_temporada(novo)
        all_ids = [j.id for j in novo.jogadores]
        self.agentes_engine.gerar_agentes(all_ids)
        self.identidade_engine.atribuir_identidade(novo)
        return True

    # ═══════════════════════════════════════════════════════════
    #  HELPERS DE INTERFACE
    # ═══════════════════════════════════════════════════════════

    def todos_times(self) -> List[Time]:
        base = (self.times_serie_a + self.times_serie_b +
                self.times_serie_c + self.times_serie_d +
                self.times_sem_divisao)
        for pais_divs in self.times_europeus.values():
            for times_div in pais_divs.values():
                base += times_div
        return base

    def nomes_times_disponiveis(self) -> List[str]:
        return [t.nome for t in self.todos_times()]

    def eh_derby(self, time_a: str, time_b: str) -> bool:
        """Verifica se dois times formam um clássico/derby."""
        rivais = self._rivalidades.get(time_a, [])
        return time_b in rivais

    # ═══════════════════════════════════════════════════════════
    #  RECORDES E CONQUISTAS
    # ═══════════════════════════════════════════════════════════

    def _processar_recordes(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Registra recordes baseados nos resultados da semana."""
        t = self.time_jogador
        if not t:
            return
        nome = t.nome
        for comp, lista in resultados.items():
            for r in lista:
                if r.time_casa == nome or r.time_fora == nome:
                    eh_casa = r.time_casa == nome
                    gols_favor = r.gols_casa if eh_casa else r.gols_fora
                    gols_contra = r.gols_fora if eh_casa else r.gols_casa
                    self.recordes.registrar_resultado(
                        gols_favor,
                        gols_contra,
                        comp,
                        self.temporada,
                    )

    def _processar_conquistas(self) -> None:
        """Verifica conquistas após cada semana."""
        t = self.time_jogador
        if not t:
            return
        jogos = t.vitorias + t.empates + t.derrotas
        self.conquistas.set_progresso("primeiro_jogo", min(1, jogos))
        self.conquistas.set_progresso("100_jogos", jogos)
        self.conquistas.set_progresso("500_jogos", jogos)
        if t.vitorias >= 10:
            seq = self._calcular_sequencia_invicta()
            self.conquistas.set_progresso("invicto_10", seq)
            self.conquistas.set_progresso("invicto_20", seq)

    def _calcular_sequencia_invicta(self) -> int:
        """Conta a sequência invicta atual analisando último resultado."""
        if not self.ultimo_resultado:
            return 0
        t = self.time_jogador
        if not t:
            return 0
        seq = getattr(self, '_seq_invicta', 0)
        for comp, lista in self.ultimo_resultado.items():
            for r in lista:
                if r.time_casa == t.nome:
                    if r.gols_casa >= r.gols_fora:
                        seq += 1
                    else:
                        seq = 0
                elif r.time_fora == t.nome:
                    if r.gols_fora >= r.gols_casa:
                        seq += 1
                    else:
                        seq = 0
        self._seq_invicta = seq
        return seq

    # ═══════════════════════════════════════════════════════════
    #  PERSISTÊNCIA DE ESTATÍSTICAS
    # ═══════════════════════════════════════════════════════════

    def _persistir_resultados(self, resultados: Dict[str, List[ResultadoPartida]]) -> None:
        """Atualiza artilharia em memória (será salva no JSON do save)."""
        if not resultados:
            return
        todos = {t.nome: t for t in self.todos_times()}
        for comp, lista in resultados.items():
            for r in lista:
                for ev in r.eventos:
                    if ev.tipo in ("gol", "gol_falta"):
                        jid = ev.jogador_id
                        entry = self.artilharia_memoria.setdefault(jid, {
                            "nome": ev.jogador_nome, "time": ev.time, "gols": 0, "assists": 0,
                        })
                        entry["gols"] += 1
                        # Assistência
                        if ev.detalhe and ev.detalhe.startswith("Assistência de "):
                            nome_assist = ev.detalhe[15:]
                            time_obj = todos.get(ev.time)
                            if time_obj:
                                for j in time_obj.jogadores:
                                    if j.nome == nome_assist:
                                        ae = self.artilharia_memoria.setdefault(j.id, {
                                            "nome": j.nome, "time": ev.time, "gols": 0, "assists": 0,
                                        })
                                        ae["assists"] += 1
                                        break
