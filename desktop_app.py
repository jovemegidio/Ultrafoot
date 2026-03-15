# -*- coding: utf-8 -*-
"""
Ultrafoot — Desktop App Launcher
=========================================
Embarca o frontend HTML/CSS/JS em janela desktop nativa via pywebview.
A classe UltrafootAPI é exposta ao JavaScript como window.pywebview.api.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import orjson as _orjson
    def _json_load_file(path):
        with open(path, "rb") as f:
            return _orjson.loads(f.read())
    def _json_dumps(obj):
        return _orjson.dumps(obj, option=_orjson.OPT_NON_STR_KEYS).decode()
except ImportError:
    _orjson = None
    def _json_load_file(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    def _json_dumps(obj):
        return json.dumps(obj, ensure_ascii=False)

import webview

from config import GAME_TITLE, GAME_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT
from core.enums import FormacaoTatica, EstiloJogo, VelocidadeJogo, MarcacaoPressao
from managers.game_manager import GameManager
from services.scout_service import ScoutService
from services.ai_service import AIService
from services.user_settings import UserSettingsService
from utils.logger import get_logger
from utils.helpers import format_reais
from data.seeds.seed_loader import limpar_cache_seeds as _limpar_cache_seeds_orig
from services import discord_rpc as _discord

log = get_logger(__name__)


def _limpar_cache_seeds():
    """Limpa cache de seeds tanto no seed_loader quanto no API bridge."""
    _limpar_cache_seeds_orig()
    UltrafootAPI._seeds_cache.clear()

# Diretórios de assets
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
_ESCUDOS_DIR = os.path.join(_BASE, "teams", "escudos")
_CAMISAS_DIR = os.path.join(_BASE, "teams", "camisas")
_SONS_DIR = os.path.join(_BASE, "sons")
_PLAYER_ASSETS_DIR = os.path.join(_BASE, "data", "assets", "players")
_TROFEUS_DIR = os.path.join(_BASE, "trofeus")

# URL base para assets — vazio porque pywebview serve via HTTP local (bottle)
# O HTML é navegado como http://127.0.0.1:PORT/index.html; file:// é cross-origin
_ASSET_BASE_URL = ""

# ══════════════════════════════════════════════════════════════
#  API BRIDGE — Exposta ao JavaScript via window.pywebview.api
# ══════════════════════════════════════════════════════════════

class UltrafootAPI:
    """Todos os métodos aqui são chamáveis pelo frontend JS."""

    def __init__(self):
        self._gm: GameManager | None = None
        self._scout = ScoutService()
        self._ai = AIService()
        self._window = None
        self._user_settings = UserSettingsService()
        self._window_fullscreen = bool(self._user_settings.load().get("window_fullscreen", False))
        # Match substitution state
        self._match_snapshot: dict | None = None
        self._match_seed: int | None = None
        self._match_casa: object | None = None
        self._match_fora: object | None = None
        self._match_comp_key: str = ""
        self._match_subs: list = []
        self._match_subs_count: int = 0

    def set_window(self, window):
        self._window = window

    def _apply_window_preferences(self, settings: dict) -> None:
        if not self._window:
            return
        fullscreen = bool(settings.get("window_fullscreen", False))
        width = int(settings.get("window_width", WINDOW_WIDTH))
        height = int(settings.get("window_height", WINDOW_HEIGHT))
        maximized = bool(settings.get("window_maximized", False))

        if fullscreen != self._window_fullscreen:
            self._window.toggle_fullscreen()
            self._window_fullscreen = fullscreen

        if not fullscreen:
            try:
                self._window.restore()
            except Exception:
                pass
            try:
                self._window.resize(width, height)
            except Exception:
                pass
            if maximized:
                try:
                    self._window.maximize()
                except Exception:
                    pass

    def _apply_user_settings_to_game(self, settings: dict | None = None) -> None:
        if not self._gm:
            return
        data = settings or self._user_settings.load()
        self._gm.configurar_performance(bool(data.get("perf_mode", False)))
        self._gm.auto_save_ativo = bool(data.get("auto_save", True))
        self._gm.music.set_volume("musica", float(data.get("music_volume", 0.5)))
        self._gm.music.set_volume("efeitos", float(data.get("effects_volume", 0.8)))
        self._gm.music.set_volume("narracao", float(data.get("narration_volume", 0.7)))
        self._gm.music.set_streamer_safe(bool(data.get("streamer_safe", False)))
        self._gm.music.set_contexto_ativo("menu", bool(data.get("menu_music", True)))
        self._gm.music.set_contexto_ativo("pre_match", bool(data.get("pre_match_music", True)))
        self._gm.music.set_narrador(str(data.get("narrator", "") or ""))

    # Mapa de comp_key → nome amigável
    _COMP_DISPLAY = {
        "brasileirao_a": "Brasileirão Betano Série A",
        "brasileirao_b": "Brasileirão Betano Série B",
        "brasileirao_c": "Brasileirão Betano Série C",
        "brasileirao_d": "Brasileirão Betano Série D",
        "serie_a": "Brasileirão Betano Série A",
        "serie_b": "Brasileirão Betano Série B",
        "serie_c": "Brasileirão Betano Série C",
        "serie_d": "Brasileirão Betano Série D",
        "copa_brasil": "Copa Betano do Brasil",
        "libertadores": "Conmebol Libertadores",
        "sul_americana": "Conmebol Sul-Americana",
        "champions_league": "UEFA Champions League",
        "europa_league": "UEFA Europa League",
        "conference_league": "UEFA Conference League",
        "afc_champions": "AFC Champions League",
        "copa_mundo": "Copa do Mundo",
        "eurocopa": "Eurocopa",
        "copa_america": "Copa America",
    }

    @staticmethod
    def _comp_display_name(comp_key: str) -> str:
        """Converte comp_key interno para nome amigável."""
        if comp_key in UltrafootAPI._COMP_DISPLAY:
            return UltrafootAPI._COMP_DISPLAY[comp_key]
        if comp_key.startswith("estadual_"):
            from managers.competition_manager import ESTADUAL_NOME_COMERCIAL
            uf = comp_key[9:]
            return ESTADUAL_NOME_COMERCIAL.get(uf, f"Estadual {uf}")
        if comp_key.startswith("liga_"):
            parts = comp_key.split("_")
            if len(parts) >= 3:
                from managers.competition_manager import _INT_LEAGUE_NAMES
                pais = parts[1].upper()
                try:
                    div = int(parts[2])
                except ValueError:
                    div = 1
                return _INT_LEAGUE_NAMES.get(pais, {}).get(div, f"Liga {pais} Div {div}")
        return comp_key

    @staticmethod
    def _serializar_resultado_partida(resultado, competicao: str = "") -> dict:
        return {
            "placar": resultado.placar,
            "time_casa": resultado.time_casa,
            "time_fora": resultado.time_fora,
            "gols_casa": resultado.gols_casa,
            "gols_fora": resultado.gols_fora,
            "posse_casa": round(resultado.posse_casa, 1),
            "finalizacoes_casa": resultado.finalizacoes_casa,
            "finalizacoes_fora": resultado.finalizacoes_fora,
            "finalizacoes_gol_casa": resultado.finalizacoes_gol_casa,
            "finalizacoes_gol_fora": resultado.finalizacoes_gol_fora,
            "escanteios_casa": resultado.escanteios_casa,
            "escanteios_fora": resultado.escanteios_fora,
            "faltas_casa": resultado.faltas_casa,
            "faltas_fora": resultado.faltas_fora,
            "publico": resultado.publico,
            "renda": resultado.renda,
            "competicao": UltrafootAPI._comp_display_name(competicao),
            "xg_casa": getattr(resultado, "xg_casa", 0),
            "xg_fora": getattr(resultado, "xg_fora", 0),
            "xa_casa": getattr(resultado, "xa_casa", 0),
            "xa_fora": getattr(resultado, "xa_fora", 0),
            "momentum": getattr(resultado, "momentum", []),
            "clima": getattr(resultado, "clima", ""),
            "nivel_gramado": getattr(resultado, "nivel_gramado", 0),
            "escalacao_casa": getattr(resultado, "escalacao_casa", []),
            "escalacao_fora": getattr(resultado, "escalacao_fora", []),
            "eventos": [
                {
                    "minuto": evento.minuto,
                    "tipo": evento.tipo,
                    "jogador": evento.jogador_nome,
                    "time": evento.time,
                    "detalhe": evento.detalhe,
                }
                for evento in resultado.eventos
            ],
        }

    # ── Jogo ──────────────────────────────────────────────────

    # Cache de JSON seeds (evita reler 2.7MB a cada chamada)
    _seeds_cache: dict = {}
    _player_photo_cache: dict[str, str] = {}
    _br_teams_cache: dict | None = None

    @classmethod
    def _load_seed(cls, name: str) -> dict:
        if name not in cls._seeds_cache:
            cls._seeds_cache[name] = _json_load_file(
                os.path.join(_BASE, "data", "seeds", name))
        return cls._seeds_cache[name]

    @classmethod
    def _load_br_teams(cls) -> dict:
        """Carrega times BR com division_overrides_2026 aplicados (cached)."""
        if cls._br_teams_cache is None:
            from data.seeds.seed_loader import carregar_times_br_raw
            cls._br_teams_cache = carregar_times_br_raw()
        return cls._br_teams_cache

    def get_ligas_disponiveis(self) -> str:
        """Retorna lista de países/ligas disponíveis para o wizard de novo jogo."""
        result = []
        # Brasil
        br_path = os.path.join(_BASE, "data", "seeds", "teams_br.json")
        if os.path.exists(br_path):
            br = self._load_br_teams()
            total_br = sum(len(br.get(k, [])) for k in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"])
            result.append({"codigo": "BRA", "nome": "Brasil", "bandeira": "", "total_times": total_br,
                           "ligas": [{"nome": "Brasileirão", "divisoes": [
                               {"nome": "Série A", "n_times": len(br.get("serie_a", []))},
                               {"nome": "Série B", "n_times": len(br.get("serie_b", []))},
                               {"nome": "Série C", "n_times": len(br.get("serie_c", []))},
                               {"nome": "Série D", "n_times": len(br.get("serie_d", []))},
                           ]}]})
        # EU
        eu_path = os.path.join(_BASE, "data", "seeds", "teams_eu.json")
        if os.path.exists(eu_path):
            eu = self._load_seed("teams_eu.json")
            for cc, country in sorted(eu.items(), key=lambda x: x[1].get("pais_nome", x[0])):
                pais = country.get("pais_nome", cc)
                ligas_data = country.get("ligas", [])
                divisoes_data = country.get("divisoes", {})
                total = sum(len(v) for v in divisoes_data.values())
                divs = []
                for div_key in sorted(divisoes_data.keys()):
                    div_num = int(div_key.replace("div_", ""))
                    liga_nome = ligas_data[div_num - 1]["nome"] if div_num <= len(ligas_data) else f"Divisão {div_num}"
                    divs.append({"nome": liga_nome, "n_times": len(divisoes_data[div_key])})
                liga_principal = ligas_data[0]["nome"] if ligas_data else "Liga"
                result.append({"codigo": cc, "nome": pais, "bandeira": "", "total_times": total,
                               "ligas": [{"nome": liga_principal, "divisoes": divs}]})
        return _json_dumps(result)

    def get_times_por_liga(self, codigo_pais: str) -> str:
        """Retorna times agrupados por divisão para um país."""
        result = {}
        if codigo_pais == "BRA":
            br = self._load_br_teams()
            div_map = {"serie_a": "Série A", "serie_b": "Série B", "serie_c": "Série C", "serie_d": "Série D", "sem_divisao": "Sem Divisão"}
            for key, label in div_map.items():
                result[label] = [{"nome": t["nome"], "file_key": t.get("file_key", ""), "prestigio": t.get("prestigio", 50), "estado": t.get("estado", "")} for t in br.get(key, [])]
        else:
            eu_path = os.path.join(_BASE, "data", "seeds", "teams_eu.json")
            if os.path.exists(eu_path):
                eu = self._load_seed("teams_eu.json")
                country = eu.get(codigo_pais, {})
                ligas = country.get("ligas", [])
                for div_key, teams in country.get("divisoes", {}).items():
                    div_num = int(div_key.replace("div_", ""))
                    nome = ligas[div_num - 1]["nome"] if div_num <= len(ligas) else f"Divisão {div_num}"
                    result[nome] = [{"nome": t["nome"], "file_key": t.get("file_key", ""), "prestigio": t.get("prestigio", 50), "estado": t.get("estado", "")} for t in teams]
        return _json_dumps(result)

    def novo_jogo_config(self, config_json: str) -> str:
        """Inicia novo jogo com configuração estilo Ultrafoot."""
        cfg = json.loads(config_json) if isinstance(config_json, str) else config_json
        time_nome = cfg.get("time", "")
        ligas_selecionadas = cfg.get("ligas", ["BRA"])
        tecnico_nome = cfg.get("tecnico_nome", "Treinador")
        tecnico_nac = cfg.get("tecnico_nacionalidade", "Brasil")
        sistema_salarios = cfg.get("sistema_salarios", "mensal")
        sistema_forca = cfg.get("sistema_forca", "classico")
        temporada = cfg.get("temporada_inicio", 2026)
        tacas_internacionais = cfg.get("tacas_internacionais", False)
        comp_selecoes = cfg.get("competicoes_selecoes", False)

        self._gm = GameManager()
        self._gm.novo_jogo_config(
            time_nome, ligas_selecionadas,
            tecnico_nome=tecnico_nome, tecnico_nac=tecnico_nac,
            sistema_salarios=sistema_salarios, sistema_forca=sistema_forca,
            temporada_inicio=temporada,
            tacas_internacionais=tacas_internacionais,
            comp_selecoes=comp_selecoes,
        )
        self._apply_user_settings_to_game()
        log.info("Novo jogo config: %s (ligas: %s)", time_nome, ligas_selecionadas)
        _discord.atualizar_jogo(time=time_nome, temporada=temporada, semana=1)
        return json.dumps({"ok": True, "time": time_nome})

    def editor_get_teams_list(self) -> str:
        """Return list of all teams with metadata for the editor panel."""
        _discord.atualizar_editor()
        result = []
        # BR teams
        br = self._load_br_teams()
        labels = {"serie_a": "Série A", "serie_b": "Série B", "serie_c": "Série C", "serie_d": "Série D", "sem_divisao": "Sem Divisão"}
        for cat, lbl in labels.items():
            for t in br.get(cat, []):
                result.append({"nome": t["nome"], "pais": "Brasil", "divisao": lbl, "file_key": t.get("file_key", ""), "prestigio": t.get("prestigio", 50)})
        # EU teams
        eu_path = os.path.join(_BASE, "data", "seeds", "teams_eu.json")
        if os.path.exists(eu_path):
            eu = self._load_seed("teams_eu.json")
            for cc, country in eu.items():
                pais = country.get("pais_nome", cc)
                ligas = country.get("ligas", [])
                for div_key, teams in country.get("divisoes", {}).items():
                    div_num = int(div_key.replace("div_", ""))
                    liga = ligas[div_num - 1]["nome"] if div_num <= len(ligas) else f"Div {div_num}"
                    for t in teams:
                        result.append({"nome": t["nome"], "pais": pais, "divisao": liga, "file_key": t.get("file_key", ""), "prestigio": t.get("prestigio", 50)})
        return _json_dumps(result)

    def nomes_times(self) -> str:
        br = self._load_br_teams()
        result = {}
        labels = {"serie_a": "Série A", "serie_b": "Série B", "serie_c": "Série C", "serie_d": "Série D", "sem_divisao": "Sem Divisão"}
        for cat in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
            result[labels[cat]] = [t["nome"] for t in br.get(cat, [])]
        # European teams
        eu_path = os.path.join(_BASE, "data", "seeds", "teams_eu.json")
        if os.path.exists(eu_path):
            eu = self._load_seed("teams_eu.json")
            for cc, country in eu.items():
                pais_nome = country.get("pais_nome", cc)
                ligas = country.get("ligas", [])
                divisoes = country.get("divisoes", {})
                for div_key, teams in divisoes.items():
                    div_num = int(div_key.replace("div_", ""))
                    liga_nome = ligas[div_num - 1]["nome"] if div_num <= len(ligas) else f"Div {div_num}"
                    label = f"{pais_nome} - {liga_nome}"
                    result[label] = [t["nome"] for t in teams]
        return _json_dumps(result)

    def novo_jogo(self, nome_time: str) -> str:
        self._gm = GameManager()
        self._gm.novo_jogo(nome_time)
        self._apply_user_settings_to_game()
        log.info("Novo jogo: %s", nome_time)
        _discord.atualizar_jogo(time=nome_time, temporada=self._gm.temporada, semana=1)
        return json.dumps({"ok": True, "time": nome_time})

    def carregar_jogo(self, nome_save: str) -> str:
        try:
            self._gm = GameManager()
            ok = self._gm.carregar(nome_save)
            if ok:
                self._apply_user_settings_to_game()
            if ok and self._gm.time_jogador:
                _discord.atualizar_jogo(
                    time=self._gm.time_jogador.nome,
                    temporada=self._gm.temporada,
                    semana=self._gm.semana,
                )
            return json.dumps({"ok": ok})
        except Exception as e:
            log.exception("Erro ao carregar save '%s'", nome_save)
            return json.dumps({"ok": False, "error": str(e)})

    def salvar_jogo(self, nome_save: str) -> str:
        if not self._gm:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        try:
            self._gm.salvar(nome_save)
            return json.dumps({"ok": True, "save_nome": nome_save})
        except Exception as e:
            log.exception("Erro ao salvar jogo '%s'", nome_save)
            return json.dumps({"ok": False, "error": str(e)})

    def listar_saves(self) -> str:
        if not self._gm:
            self._gm = GameManager()
        saves = self._gm.listar_saves()
        return json.dumps(saves, ensure_ascii=False, default=str)

    def deletar_save(self, nome: str) -> str:
        if not self._gm:
            self._gm = GameManager()
        ok = self._gm.deletar_save(nome)
        return json.dumps({"ok": ok})

    def get_user_settings(self) -> str:
        return json.dumps(self._user_settings.load(), ensure_ascii=False)

    def update_user_settings(self, settings_json: str) -> str:
        payload = json.loads(settings_json) if isinstance(settings_json, str) else settings_json
        settings = self._user_settings.update(payload or {})
        self._apply_window_preferences(settings)
        self._apply_user_settings_to_game(settings)
        return json.dumps({"ok": True, "settings": settings}, ensure_ascii=False)

    def get_save_integrity(self, nome: str = "") -> str:
        if not self._gm:
            self._gm = GameManager()
        alvo = nome or self._gm.save_nome or ""
        if not alvo:
            return json.dumps({"ok": False, "error": "save_nao_informado"})
        return json.dumps(self._gm.validar_save(alvo), ensure_ascii=False)

    def restore_latest_backup(self, nome: str) -> str:
        if not self._gm:
            self._gm = GameManager()
        resultado = self._gm.restaurar_ultimo_backup(nome)
        if resultado.get("ok") and self._gm.save_nome == nome and self._gm.time_jogador:
            _discord.atualizar_jogo(
                time=self._gm.time_jogador.nome,
                temporada=self._gm.temporada,
                semana=self._gm.semana,
            )
        return json.dumps(resultado, ensure_ascii=False)

    def get_license_status(self) -> str:
        if not self._gm:
            self._gm = GameManager()
        return json.dumps(self._gm.get_license_status(), ensure_ascii=False)

    def activate_license(self, serial: str) -> str:
        if not self._gm:
            self._gm = GameManager()
        return json.dumps(self._gm.ativar_licenca(serial), ensure_ascii=False)

    def get_asset_registry(self) -> str:
        if not self._gm:
            self._gm = GameManager()
        return json.dumps(self._gm.get_asset_registry(), ensure_ascii=False)

    # ── Game State ────────────────────────────────────────────

    def get_dashboard(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        # Se desempregado, retornar estado especial
        if getattr(gm, '_desempregado', False):
            return json.dumps({
                "desempregado": True,
                "temporada": gm.temporada,
                "semana": gm.semana,
                "max_semanas": 48,
                "semanas_desempregado": gm._semanas_desempregado,
                "reputacao": gm.carreira_engine.carreira.reputacao if hasattr(gm, 'carreira_engine') else 50,
                "ofertas": gm._ofertas_emprego,
                "noticias": [
                    {"titulo": n.titulo, "texto": n.texto,
                     "categoria": n.categoria.value if hasattr(n.categoria, 'value') else str(n.categoria),
                     "rodada": getattr(n, 'rodada', gm.semana)}
                    for n in gm.noticias[-15:]
                ],
            }, ensure_ascii=False, default=str)
        if not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador
        # Use per-competition stats from the player's main league
        player_camp = None
        for camp_check in [gm.competicoes.brasileirao_a, gm.competicoes.brasileirao_b,
                           gm.competicoes.brasileirao_c]:
            if camp_check and t in camp_check.times:
                player_camp = camp_check
                break
        # Also check European leagues
        if not player_camp and gm.competicoes.ligas_europeias:
            for pais, divs in gm.competicoes.ligas_europeias.items():
                for dv, camp_check in divs.items():
                    if t in camp_check.times:
                        player_camp = camp_check
                        break
                if player_camp:
                    break
        ps = player_camp.get_stats(t.id) if player_camp and hasattr(player_camp, 'get_stats') else None
        jogos = (ps["v"] + ps["e"] + ps["d"]) if ps else (t.vitorias + t.empates + t.derrotas)
        return json.dumps({
            "time": t.nome,
            "time_curto": t.nome_curto,
            "divisao": t.divisao,
            "estado": getattr(t, 'estado', ''),
            "temporada": gm.temporada,
            "semana": gm.semana,
            "max_semanas": 48,
            "saldo": t.financas.saldo,
            "saldo_fmt": format_reais(t.financas.saldo),
            "elenco_qtd": len(t.jogadores),
            "overall": t.overall_medio,
            "vitorias": ps["v"] if ps else t.vitorias,
            "empates": ps["e"] if ps else t.empates,
            "derrotas": ps["d"] if ps else t.derrotas,
            "jogos": jogos,
            "gols_marcados": ps["gm"] if ps else t.gols_marcados,
            "gols_sofridos": ps["gs"] if ps else t.gols_sofridos,
            "pontos": ps["pontos"] if ps else t.pontos,
            "prestigio": t.prestigio,
            "diretoria": {
                "meta_principal": t.diretoria.meta_principal,
                "meta_minima": t.diretoria.meta_minima,
                "satisfacao": t.diretoria.satisfacao,
                "paciencia": t.diretoria.paciencia,
                "pressao_torcida": t.diretoria.pressao_torcida,
                "status": t.diretoria.status,
                "demitido": t.diretoria.demitido,
                "mensagens": t.diretoria.mensagens,
            },
            "noticias": [
                {"titulo": n.titulo, "texto": n.texto,
                 "categoria": n.categoria.value if hasattr(n.categoria, 'value') else str(n.categoria),
                 "rodada": getattr(n, 'rodada', gm.semana)}
                for n in gm.noticias[-15:]
            ],
        }, ensure_ascii=False, default=str)

    def avancar_semana(self) -> str:
        if not self._gm:
            return json.dumps({"error": "Nenhum jogo ativo"})

        gm = self._gm
        # Reset substitution state
        self._match_snapshot = None
        self._match_seed = None
        self._match_casa = None
        self._match_fora = None
        self._match_comp_key = ""
        self._match_subs = []
        self._match_subs_count = 0

        # Set pre-match callback to snapshot teams
        def _snapshot_callback():
            casa, fora, comp_key = self._find_player_match_teams()
            if casa and fora:
                self._match_snapshot = self._take_team_snapshot(casa, fora)
                self._match_casa = casa
                self._match_fora = fora
                self._match_comp_key = comp_key
                import random
                self._match_seed = random.randint(0, 2**31)

        gm._pre_match_callback = _snapshot_callback
        resultados = gm.avancar_semana()
        gm._pre_match_callback = None

        # Serializar resultados
        res_dict = {}
        for comp, lista in resultados.items():
            res_dict[comp] = [self._serializar_resultado_partida(r, comp) for r in lista]

        # Discord RPC update
        if gm.time_jogador:
            _discord.atualizar_jogo(
                time=gm.time_jogador.nome,
                temporada=gm.temporada,
                semana=gm.semana,
            )

        return json.dumps(res_dict, ensure_ascii=False, default=str)

    # ── Substituições durante partida ─────────────────────────

    def _find_player_match_teams(self):
        """Find home/away teams and comp key for the player's upcoming match."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return None, None, ""
        t = gm.time_jogador
        comps = gm.competicoes
        proxima_semana = comps.semana_atual + 1
        comps_semana = comps.calendario.get(proxima_semana, [])
        if not comps_semana:
            return None, None, ""
        uf = t.estado

        if "estadual" in comps_semana and uf and uf in comps.estaduais:
            est = comps.estaduais[uf]
            if not est.encerrado:
                if est._em_mata_mata and est.semifinal and not est.semifinal.encerrado:
                    jogo = est.semifinal.jogo_do_jogador(t)
                    if jogo:
                        return jogo[0], jogo[1], f"estadual_{uf}"
                elif hasattr(est, 'fase_grupos') and est.fase_grupos and not est.fase_grupos.encerrado:
                    jogo = est.fase_grupos.jogo_do_jogador(t)
                    if jogo:
                        return jogo[0], jogo[1], f"estadual_{uf}"

        if "brasileirao" in comps_semana:
            for attr in ['brasileirao_a', 'brasileirao_b', 'brasileirao_c', 'brasileirao_d']:
                comp = getattr(comps, attr, None)
                if comp and not comp.encerrado:
                    jogo = comp.jogo_do_jogador(t)
                    if jogo:
                        return jogo[0], jogo[1], attr

        if "brasileirao_c" in comps_semana:
            comp = comps.brasileirao_c
            if comp and not comp.encerrado:
                jogo = comp.jogo_do_jogador(t)
                if jogo:
                    return jogo[0], jogo[1], "brasileirao_c"

        if "brasileirao_d" in comps_semana:
            comp = comps.brasileirao_d
            if comp and not comp.encerrado:
                jogo = comp.jogo_do_jogador(t)
                if jogo:
                    return jogo[0], jogo[1], "brasileirao_d"

        if "copa_brasil" in comps_semana and comps.copa_brasil and not comps.copa_brasil.encerrado:
            jogo = comps.copa_brasil.jogo_do_jogador(t)
            if jogo:
                return jogo[0], jogo[1], "copa_brasil"

        if "libertadores" in comps_semana and comps.libertadores and not comps.libertadores.encerrado:
            jogo = comps.libertadores.jogo_do_jogador(t)
            if jogo:
                return jogo[0], jogo[1], "libertadores"

        if "sul_americana" in comps_semana and comps.sul_americana and not comps.sul_americana.encerrado:
            jogo = comps.sul_americana.jogo_do_jogador(t)
            if jogo:
                return jogo[0], jogo[1], "sul_americana"

        if "europeias" in comps_semana and comps.ligas_europeias:
            for pais, divs in comps.ligas_europeias.items():
                for div_num, liga in divs.items():
                    if not liga.encerrado:
                        jogo = liga.jogo_do_jogador(t)
                        if jogo:
                            return jogo[0], jogo[1], f"liga_{pais}_{div_num}"

        if "champions_league" in comps_semana and comps.champions_league and not comps.champions_league.encerrado:
            jogo = comps.champions_league.jogo_do_jogador(t)
            if jogo:
                return jogo[0], jogo[1], "champions_league"

        # Amistoso agendado (fallback se nenhum jogo oficial)
        if gm.amistoso_agendado:
            return t, gm.amistoso_agendado, "amistoso"

        return None, None, ""

    def _take_team_snapshot(self, casa, fora) -> dict:
        """Snapshot team + player stats before match for rollback."""
        from core.enums import StatusLesao
        snap = {}
        for team in (casa, fora):
            ts = {
                'gm': team.gols_marcados, 'gs': team.gols_sofridos,
                'v': team.vitorias, 'e': team.empates, 'd': team.derrotas,
                'p': team.pontos, 'saldo': team.financas.saldo,
            }
            ps = {}
            for j in team.jogadores:
                ps[j.id] = {
                    'gols': j.historico_temporada.gols,
                    'assist': j.historico_temporada.assistencias,
                    'jogos': j.historico_temporada.jogos,
                    'ca': j.historico_temporada.cartoes_amarelos,
                    'cv': j.historico_temporada.cartoes_vermelhos,
                    'ca_acum': j.cartao_amarelo_acumulado,
                    'susp': j.suspensao_jogos,
                    'moral': j.moral,
                    'cond': j.condicao_fisica,
                    'lesao': j.status_lesao,
                    'dias_lesao': j.dias_lesao,
                }
            snap[team.nome] = {'team': ts, 'players': ps}
        return snap

    def _restore_team_snapshot(self, casa, fora, snap: dict) -> None:
        """Restore teams from snapshot."""
        for team in (casa, fora):
            if team.nome not in snap:
                continue
            ts = snap[team.nome]['team']
            team.gols_marcados = ts['gm']
            team.gols_sofridos = ts['gs']
            team.vitorias = ts['v']
            team.empates = ts['e']
            team.derrotas = ts['d']
            team.pontos = ts['p']
            team.financas.saldo = ts['saldo']
            ps = snap[team.nome]['players']
            for j in team.jogadores:
                if j.id in ps:
                    s = ps[j.id]
                    j.historico_temporada.gols = s['gols']
                    j.historico_temporada.assistencias = s['assist']
                    j.historico_temporada.jogos = s['jogos']
                    j.historico_temporada.cartoes_amarelos = s['ca']
                    j.historico_temporada.cartoes_vermelhos = s['cv']
                    j.cartao_amarelo_acumulado = s['ca_acum']
                    j.suspensao_jogos = s['susp']
                    j.moral = s['moral']
                    j.condicao_fisica = s['cond']
                    j.status_lesao = s['lesao']
                    j.dias_lesao = s['dias_lesao']

    def get_banco_partida(self) -> str:
        """Return bench players of the player's team for substitution."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps([])
        t = gm.time_jogador
        titulares_ids = set(t.titulares)
        # Exclude already-subbed-out players
        saiu_ids = {s['sai_id'] for s in self._match_subs}
        banco = []
        for j in t.jogadores:
            if j.id not in titulares_ids and j.id not in saiu_ids and j.pode_jogar:
                banco.append(self._jogador_sub_info(j))
        return json.dumps(banco, ensure_ascii=False)

    def get_titulares_partida(self) -> str:
        """Return current starters for substitution selection."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps([])
        t = gm.time_jogador
        titulares_ids = set(t.titulares)
        # Include players that came in as subs
        entrou_ids = {s['entra_id'] for s in self._match_subs}
        em_campo = titulares_ids | entrou_ids
        # Remove players that left
        saiu_ids = {s['sai_id'] for s in self._match_subs}
        em_campo -= saiu_ids
        tits = []
        for j in t.jogadores:
            if j.id in em_campo:
                tits.append(self._jogador_sub_info(j))
        return json.dumps(tits, ensure_ascii=False)

    @staticmethod
    def _jogador_sub_info(j) -> dict:
        """Build player info dict with radar attributes for substitution UI."""
        tec = j.tecnicos
        fis = j.fisicos
        men = j.mentais
        return {
            "id": j.id,
            "nome": j.nome,
            "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
            "overall": j.overall,
            "condicao": j.condicao_fisica,
            "idade": j.idade,
            "radar": {
                "VEL": int((fis.velocidade + fis.aceleracao) / 2),
                "FIN": int((tec.finalizacao + tec.chute_longa_dist + tec.cabeceio) / 3),
                "PAS": int((tec.passe_curto + tec.passe_longo + tec.lancamento) / 3),
                "DRI": int((tec.drible + tec.controle_bola) / 2),
                "DEF": int((tec.desarme + tec.marcacao) / 2),
                "FIS": int((fis.forca + fis.resistencia + fis.agilidade) / 3),
            },
        }

    @staticmethod
    def _fallback_player_photo(nome: str, cor_primaria: str = "#d4ff00", cor_secundaria: str = "#0f1118") -> str:
        partes = [p for p in (nome or "").split() if p]
        iniciais = "".join(p[0].upper() for p in partes[:2]) or "UF"
        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="{cor_primaria}"/>
      <stop offset="100%" stop-color="{cor_secundaria}"/>
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="128" fill="url(#g)"/>
  <circle cx="128" cy="96" r="44" fill="rgba(255,255,255,0.18)"/>
  <path d="M56 214c10-42 40-66 72-66s62 24 72 66" fill="rgba(255,255,255,0.14)"/>
  <text x="128" y="235" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="54" font-weight="900" fill="#ffffff">{iniciais}</text>
</svg>
""".strip()
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"

    @staticmethod
    def _slug_player_name(nome: str) -> str:
        texto = (nome or "").lower()
        normalizado = "".join(
            c for c in unicodedata.normalize("NFKD", texto)
            if not unicodedata.combining(c)
        )
        normalizado = re.sub(r"[^a-z0-9]+", "-", normalizado).strip("-")
        return normalizado or "jogador"

    @classmethod
    def _file_key_for_nome(cls, nome: str) -> str:
        nome = str(nome or "").strip()
        if not nome:
            return ""

        br = cls._load_br_teams()
        for chave in ("serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"):
            for item in br.get(chave, []):
                if item.get("nome") == nome:
                    return item.get("file_key", "")

        eu = cls._load_seed("teams_eu.json")
        for country in eu.values():
            for teams in country.get("divisoes", {}).values():
                for item in teams:
                    if item.get("nome") == nome:
                        return item.get("file_key", "")
        return ""

    @classmethod
    def _image_to_data_uri(cls, path: str) -> str | None:
        if not path or not os.path.isfile(path):
            return None
        if path in cls._player_photo_cache:
            return cls._player_photo_cache[path]
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext)
        if not mime:
            return None
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        uri = f"data:{mime};base64,{data}"
        cls._player_photo_cache[path] = uri
        return uri

    def _resolver_local_player_photo(self, jogador, time=None) -> str | None:
        slug = self._slug_player_name(getattr(jogador, "nome", ""))
        candidatos = []
        if time is not None:
            file_key = self._file_key_for_nome(getattr(time, "nome", ""))
            if file_key:
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    candidatos.append(os.path.join(_PLAYER_ASSETS_DIR, file_key, slug + ext))
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidatos.append(os.path.join(_PLAYER_ASSETS_DIR, slug + ext))
        for path in candidatos:
            uri = self._image_to_data_uri(path)
            if uri:
                return uri
        return None

    def _player_photo_src(self, jogador, time=None) -> str:
        foto = getattr(jogador, "foto", "") or ""
        if foto:
            if foto.startswith(("data:", "http://", "https://", "file:///")):
                return foto
            local = foto if os.path.isabs(foto) else os.path.join(_BASE, foto)
            uri = self._image_to_data_uri(local)
            if uri:
                return uri
        local_photo = self._resolver_local_player_photo(jogador, time)
        if local_photo:
            return local_photo
        cor_primaria = "#d4ff00"
        cor_secundaria = "#0f1118"
        if time is not None:
            cor_primaria = getattr(time, "cor_principal", cor_primaria) or cor_primaria
            cor_secundaria = getattr(time, "cor_secundaria", cor_secundaria) or cor_secundaria
        return self._fallback_player_photo(jogador.nome, cor_primaria, cor_secundaria)

    def fazer_substituicao(self, minuto: int, sai_id: int, entra_id: int) -> str:
        """Make a substitution at the given minute, re-simulate the match."""
        gm = self._gm
        if not gm or not self._match_snapshot or not self._match_casa:
            return json.dumps({"error": "Nenhuma partida em andamento"})
        if self._match_subs_count >= 5:
            return json.dumps({"error": "Limite de 5 substituições atingido"})

        nome_time = gm.time_jogador.nome
        self._match_subs.append({
            "minuto": minuto,
            "sai_id": sai_id,
            "entra_id": entra_id,
            "time_nome": nome_time,
        })
        self._match_subs_count += 1

        # Restore teams from snapshot
        casa = self._match_casa
        fora = self._match_fora
        self._restore_team_snapshot(casa, fora, self._match_snapshot)

        # Re-simulate with subs using same seed
        from engine.match_engine import MotorPartida
        motor = MotorPartida()
        resultado = motor.simular(
            casa, fora,
            seed=self._match_seed,
            substituicoes=self._match_subs,
            aplicar_pos_jogo=True,
        )

        # Update ultimo_resultado
        for comp_key, comp_resultados in gm.ultimo_resultado.items():
            for i, r in enumerate(comp_resultados):
                if r.time_casa == casa.nome and r.time_fora == fora.nome:
                    gm.ultimo_resultado[comp_key][i] = resultado
                    break

        # Also update internal competition results (critical for Copa ida/volta aggregation)
        comp_key = self._match_comp_key
        comps = gm.competicoes
        if comp_key.startswith("brasileirao_"):
            camp = getattr(comps, comp_key, None)
            if camp and camp.resultados:
                last_rodada = camp.resultados[-1]
                for i, r in enumerate(last_rodada):
                    if r.time_casa == casa.nome and r.time_fora == fora.nome:
                        last_rodada[i] = resultado
                        break
        elif comp_key in ("copa_brasil", "libertadores", "sul_americana"):
            copa = getattr(comps, comp_key, None)
            if copa:
                fa = copa.fase_atual - (0 if copa.jogo_ida else 1)
                if fa < 0:
                    fa = copa.fase_atual
                if copa.jogo_ida and fa < len(copa.resultados_volta):
                    # Just played volta, update volta results
                    for i, r in enumerate(copa.resultados_volta[fa]):
                        if r.time_casa == casa.nome and r.time_fora == fora.nome:
                            copa.resultados_volta[fa][i] = resultado
                            break
                elif not copa.jogo_ida and copa.fase_atual < len(copa.resultados_ida):
                    # Just played ida, update ida results
                    for i, r in enumerate(copa.resultados_ida[copa.fase_atual]):
                        if r.time_casa == casa.nome and r.time_fora == fora.nome:
                            copa.resultados_ida[copa.fase_atual][i] = resultado
                            break

        # Return updated match data
        return json.dumps({
            "ok": True,
            "subs_restantes": 5 - self._match_subs_count,
            "partida": self._serializar_resultado_partida(resultado, self._match_comp_key),
        }, ensure_ascii=False, default=str)

    # ── Elenco ────────────────────────────────────────────────

    def get_elenco(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps([])
        jogadores = []
        for j in gm.time_jogador.jogadores:
            jogadores.append({
                "id": j.id,
                "nome": j.nome,
                "idade": j.idade,
                "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
                "overall": j.overall,
                "potencial": j.potencial,
                "moral": j.moral,
                "condicao": j.condicao_fisica,
                "status_lesao": j.status_lesao.value if hasattr(j.status_lesao, 'value') else "Saudável",
                "dias_lesao": j.dias_lesao,
                "salario": j.contrato.salario,
                "salario_fmt": format_reais(j.contrato.salario),
                "valor_mercado": j.valor_mercado,
                "valor_fmt": format_reais(j.valor_mercado),
                "contrato_meses": j.contrato.meses_restantes,
                "titular": j.id in gm.time_jogador.titulares,
                "pode_jogar": j.pode_jogar,
                "foto": self._player_photo_src(j, gm.time_jogador),
                "nacionalidade": j.nacionalidade,
                "pe": j.pe_preferido.value if hasattr(j.pe_preferido, 'value') else str(j.pe_preferido),
                "altura": j.altura,
                "peso": j.peso,
                "traits": [tr.value if hasattr(tr, 'value') else str(tr) for tr in j.traits],
                "stats_temp": {
                    "jogos": j.historico_temporada.jogos if j.historico_temporada else 0,
                    "gols": j.historico_temporada.gols if j.historico_temporada else 0,
                    "assistencias": j.historico_temporada.assistencias if j.historico_temporada else 0,
                    "amarelos": j.historico_temporada.cartoes_amarelos if j.historico_temporada else 0,
                    "vermelhos": j.historico_temporada.cartoes_vermelhos if j.historico_temporada else 0,
                    "nota_media": round(j.historico_temporada.nota_media, 1) if j.historico_temporada else 6.0,
                },
                "tecnicos": {
                    "passe_curto": j.tecnicos.passe_curto,
                    "passe_longo": j.tecnicos.passe_longo,
                    "cruzamento": j.tecnicos.cruzamento,
                    "finalizacao": j.tecnicos.finalizacao,
                    "chute_longa": j.tecnicos.chute_longa_dist,
                    "cabeceio": j.tecnicos.cabeceio,
                    "drible": j.tecnicos.drible,
                    "controle": j.tecnicos.controle_bola,
                    "desarme": j.tecnicos.desarme,
                    "marcacao": j.tecnicos.marcacao,
                },
                "fisicos": {
                    "velocidade": j.fisicos.velocidade,
                    "aceleracao": j.fisicos.aceleracao,
                    "resistencia": j.fisicos.resistencia,
                    "forca": j.fisicos.forca,
                    "agilidade": j.fisicos.agilidade,
                },
                "mentais": {
                    "visao": j.mentais.visao_jogo,
                    "decisao": j.mentais.decisao,
                    "concentracao": j.mentais.concentracao,
                    "lideranca": j.mentais.lideranca,
                    "compostura": j.mentais.compostura,
                },
            })
        return json.dumps(jogadores, ensure_ascii=False, default=str)

    def get_jogador_detalhe(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        for t in gm.todos_times():
            j = t.jogador_por_id(jogador_id)
            if j:
                return json.dumps({
                    "id": j.id, "nome": j.nome, "idade": j.idade,
                    "foto": self._player_photo_src(j, t),
                    "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
                    "overall": j.overall, "potencial": j.potencial,
                    "moral": j.moral, "condicao": j.condicao_fisica,
                    "valor_mercado": j.valor_mercado,
                    "valor_fmt": format_reais(j.valor_mercado),
                    "time": t.nome,
                    "tecnicos": vars(j.tecnicos) if hasattr(j.tecnicos, '__dict__') else {},
                    "fisicos": vars(j.fisicos) if hasattr(j.fisicos, '__dict__') else {},
                    "mentais": vars(j.mentais) if hasattr(j.mentais, '__dict__') else {},
                    "goleiro": vars(j.goleiro) if hasattr(j.goleiro, '__dict__') else {},
                    "traits": [tr.value if hasattr(tr, 'value') else str(tr) for tr in j.traits],
                    "salario": j.contrato.salario,
                    "salario_fmt": format_reais(j.contrato.salario),
                    "contrato_meses": j.contrato.meses_restantes,
                    "contrato_duracao": j.contrato.duracao_meses,
                    "multa_rescisoria": j.contrato.multa_rescisoria,
                    "multa_fmt": format_reais(j.contrato.multa_rescisoria) if j.contrato.multa_rescisoria else "N/A",
                }, ensure_ascii=False, default=str)
        return json.dumps({"error": "not_found"})

    # ── Classificação ─────────────────────────────────────────

    def _classif_item(self, camp, t, pos):
        """Build a classification dict entry using per-competition stats."""
        s = camp.get_stats(t.id) if hasattr(camp, 'get_stats') else None
        if s:
            return {
                "pos": pos, "nome": t.nome, "nome_curto": t.nome_curto,
                "pontos": s["pontos"],
                "jogos": s["v"] + s["e"] + s["d"],
                "v": s["v"], "e": s["e"], "d": s["d"],
                "gm": s["gm"], "gs": s["gs"],
                "sg": s["gm"] - s["gs"],
                "eh_jogador": t.eh_jogador,
            }
        return {
            "pos": pos, "nome": t.nome, "nome_curto": t.nome_curto,
            "pontos": t.pontos,
            "jogos": t.vitorias + t.empates + t.derrotas,
            "v": t.vitorias, "e": t.empates, "d": t.derrotas,
            "gm": t.gols_marcados, "gs": t.gols_sofridos,
            "sg": t.saldo_gols,
            "eh_jogador": t.eh_jogador,
        }

    def get_classificacao(self, competicao: str = "serie_a") -> str:
        gm = self._gm
        if not gm:
            return json.dumps([])
        comp = gm.competicoes
        camp = None

        # Helper: retornar dados de grupos para CampeonatoComGrupos
        def _grupos_json(ccg):
            from managers.competition_manager import CampeonatoComGrupos
            if isinstance(ccg, CampeonatoComGrupos) and ccg.grupos:
                grupos_data = []
                for gi, grupo in enumerate(ccg.grupos):
                    classif = grupo.classificacao()
                    grupo_items = [self._classif_item(grupo, t, i + 1)
                                   for i, t in enumerate(classif)]
                    grupos_data.append({
                        "grupo": chr(65 + gi),
                        "nome": grupo.nome,
                        "classificacao": grupo_items,
                    })
                return json.dumps({"grupos": grupos_data,
                                   "em_mata_mata": ccg._em_mata_mata},
                                  ensure_ascii=False)
            return None

        # Serie D com grupos
        if competicao == "serie_d" and comp.brasileirao_d:
            r = _grupos_json(comp.brasileirao_d)
            if r:
                return r

        # Serie C com grupos (formato 2026: 2 grupos)
        if competicao == "serie_c" and comp.brasileirao_c:
            r = _grupos_json(comp.brasileirao_c)
            if r:
                return r

        if competicao == "serie_a":
            camp = comp.brasileirao_a
        elif competicao == "serie_b":
            camp = comp.brasileirao_b
        elif competicao == "serie_c":
            camp = comp.brasileirao_c
        elif competicao == "serie_d":
            camp = comp.brasileirao_d
        elif competicao.startswith("estadual_"):
            uf = competicao[9:]
            est = comp.estaduais.get(uf)
            if est and est.fase_grupos:
                camp = est.fase_grupos
                # Estadual com fase de grupos (ex: Paulistão) ou intergrupos (ex: Mineiro)
                from managers.competition_manager import GruposEstadual, GruposIntergrupais
                if isinstance(camp, GruposIntergrupais):
                    grupos_data = []
                    for gi in range(camp.n_grupos):
                        classif = camp.classificacao_grupo(gi)
                        grupo_items = []
                        for i, t in enumerate(classif):
                            s = camp.get_stats(t.id)
                            grupo_items.append({
                                "pos": i + 1,
                                "nome": t.nome,
                                "pontos": s.get("pontos", 0),
                                "v": s.get("v", 0),
                                "e": s.get("e", 0),
                                "d": s.get("d", 0),
                                "gm": s.get("gm", 0),
                                "gs": s.get("gs", 0),
                                "sg": s.get("gm", 0) - s.get("gs", 0),
                                "j": s.get("v", 0) + s.get("e", 0) + s.get("d", 0),
                            })
                        grupos_data.append({
                            "grupo": chr(65 + gi),
                            "nome": f"{camp.nome} - Grupo {chr(65 + gi)}",
                            "classificacao": grupo_items,
                        })
                    semi = None
                    if est._em_mata_mata and est.semifinal:
                        confrontos = []
                        if est.semifinal.fase_atual < len(est.semifinal.confrontos):
                            for t1, t2 in est.semifinal.confrontos[est.semifinal.fase_atual]:
                                confrontos.append({
                                    "time1": t1.nome if t1 else "BYE",
                                    "time2": t2.nome if t2 else "BYE",
                                })
                        semi = {
                            "fase": est.semifinal.fase_nome,
                            "confrontos": confrontos,
                            "campeao": est.campeao.nome if est.campeao else None,
                        }
                    return json.dumps({"grupos": grupos_data,
                                       "em_mata_mata": est._em_mata_mata,
                                       "semifinal": semi,
                                       "campeao": est.campeao.nome if est.campeao else None},
                                      ensure_ascii=False)
                elif isinstance(camp, GruposEstadual) and camp.grupos:
                    grupos_data = []
                    for gi, grupo in enumerate(camp.grupos):
                        classif = grupo.classificacao()
                        grupo_items = [self._classif_item(grupo, t, i + 1)
                                       for i, t in enumerate(classif)]
                        grupos_data.append({
                            "grupo": chr(65 + gi),
                            "nome": grupo.nome,
                            "classificacao": grupo_items,
                        })
                    semi = None
                    if est._em_mata_mata and est.semifinal:
                        confrontos = []
                        if est.semifinal.fase_atual < len(est.semifinal.confrontos):
                            for t1, t2 in est.semifinal.confrontos[est.semifinal.fase_atual]:
                                confrontos.append({
                                    "time1": t1.nome if t1 else "BYE",
                                    "time2": t2.nome if t2 else "BYE",
                                })
                        semi = {
                            "fase": est.semifinal.fase_nome,
                            "confrontos": confrontos,
                            "campeao": est.campeao.nome if est.campeao else None,
                        }
                    return json.dumps({"grupos": grupos_data,
                                       "em_mata_mata": est._em_mata_mata,
                                       "semifinal": semi,
                                       "campeao": est.campeao.nome if est.campeao else None},
                                      ensure_ascii=False)

                # Estadual pontos corridos (padrão)
                classificacao = camp.classificacao()
                base = [self._classif_item(camp, t, i + 1)
                        for i, t in enumerate(classificacao)]
                semi = None
                if est._em_mata_mata and est.semifinal:
                    confrontos = []
                    if est.semifinal.fase_atual < len(est.semifinal.confrontos):
                        for t1, t2 in est.semifinal.confrontos[est.semifinal.fase_atual]:
                            confrontos.append({
                                "time1": t1.nome if t1 else "BYE",
                                "time2": t2.nome if t2 else "BYE",
                            })
                    semi = {
                        "fase": est.semifinal.fase_nome,
                        "confrontos": confrontos,
                        "campeao": est.campeao.nome if est.campeao else None,
                    }
                return json.dumps({"classificacao": base, "semifinal": semi,
                                   "campeao": est.campeao.nome if est.campeao else None},
                                  ensure_ascii=False)
        elif competicao.startswith("liga_"):
            # European league: liga_ING_1, liga_ESP_1, etc.
            parts = competicao.split("_")
            if len(parts) >= 3:
                pais = parts[1]
                div = int(parts[2])
                eu_ligas = comp.ligas_europeias.get(pais, {})
                camp = eu_ligas.get(div)
        elif competicao in {"champions_league", "europa_league", "copa_mundo", "eurocopa", "copa_america"}:
            ccg = getattr(comp, competicao, None)
            if ccg:
                r = _grupos_json(ccg)
                if r:
                    return r
        if camp is None:
            return json.dumps([])
        classificacao = camp.classificacao()
        return json.dumps([self._classif_item(camp, t, i + 1)
                           for i, t in enumerate(classificacao)], ensure_ascii=False)

    def get_estaduais_info(self) -> str:
        """Retorna info sobre todos os estaduais disponíveis."""
        gm = self._gm
        if not gm:
            return json.dumps([])
        estado_jogador = gm.time_jogador.estado if gm.time_jogador else ""
        info = []
        for uf, est in gm.competicoes.estaduais.items():
            info.append({
                "uf": uf,
                "nome": est.nome,
                "encerrado": est.encerrado,
                "campeao": est.campeao.nome if est.campeao else None,
                "n_times": len(est.times),
                "eh_do_jogador": uf == estado_jogador,
            })
        info.sort(key=lambda x: (not x["eh_do_jogador"], x["uf"]))
        return json.dumps(info, ensure_ascii=False)

    def get_european_leagues_info(self) -> str:
        """Retorna info sobre ligas internacionais e torneios continentais/seleções."""
        gm = self._gm
        if not gm:
            return json.dumps([])
        eu_ligas = gm.competicoes.ligas_europeias
        pais_jogador = getattr(gm.time_jogador, 'estado', '') if gm.time_jogador else ''
        result = []
        for pais, divs in eu_ligas.items():
            for div_num, liga in sorted(divs.items()):
                nome_limpo = liga.nome.split(f" {gm.temporada}")[0] if gm else liga.nome
                result.append({
                    "key": f"liga_{pais}_{div_num}",
                    "nome": nome_limpo,
                    "pais": pais,
                    "div": div_num,
                    "eh_do_jogador": pais == pais_jogador and div_num == getattr(gm.time_jogador, 'divisao', 0),
                    "encerrado": liga.encerrado,
                })
        result.sort(key=lambda item: (not item["eh_do_jogador"], item["pais"], item["div"]))
        return json.dumps({
            "ligas": result,
            "champions_league": gm.competicoes.champions_league is not None,
            "europa_league": gm.competicoes.europa_league is not None,
            "copa_mundo": gm.competicoes.copa_mundo is not None,
            "eurocopa": gm.competicoes.eurocopa is not None,
            "copa_america": gm.competicoes.copa_america is not None,
            "pais_jogador": pais_jogador,
        }, ensure_ascii=False)

    def get_copa(self, tipo: str = "copa_brasil") -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        copa = getattr(gm.competicoes, tipo, None)
        if not copa:
            return json.dumps(None)
        confrontos = []
        if copa.fase_atual < len(copa.confrontos):
            for t1, t2 in copa.confrontos[copa.fase_atual]:
                confrontos.append({
                    "time1": t1.nome if t1 else "BYE",
                    "time2": t2.nome if t2 else "BYE",
                })
        return json.dumps({
            "fase": copa.fase_nome,
            "encerrado": copa.encerrado,
            "campeao": copa.campeao.nome if copa.encerrado and copa.campeao else None,
            "confrontos": confrontos,
        }, ensure_ascii=False)

    # ── Mercado ───────────────────────────────────────────────

    def get_mercado(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({"ofertas": [], "livres": []})
        ofertas = [{
            "id": o.id, "jogador": o.jogador_nome,
            "origem": o.time_origem, "destino": o.time_destino,
            "valor": o.valor, "valor_fmt": format_reais(o.valor),
            "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
        } for o in gm.mercado.ofertas_pendentes]
        livres = [{
            "id": j.id, "nome": j.nome, "idade": j.idade,
            "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
            "overall": j.overall,
            "valor_mercado": j.valor_mercado,
            "valor_fmt": format_reais(j.valor_mercado),
            "salario_fmt": format_reais(j.contrato.salario),
            "foto": self._player_photo_src(j),
        } for j in gm.mercado.jogadores_livres[:30]]
        return json.dumps({
            "ofertas": ofertas,
            "livres": livres,
            "mercado_aberto": gm.mercado_aberto(),
            "janelas": list(gm._janelas_transferencia),
        }, ensure_ascii=False, default=str)

    def contratar_livre(self, jogador_id: int, salario: int = 0) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        if not gm.mercado_aberto():
            return json.dumps({"ok": False, "error": "A janela de transferências está fechada no momento"})
        # Find player in free agents to get default salary
        jogador = None
        for j in gm.mercado.jogadores_livres:
            if j.id == jogador_id:
                jogador = j
                if salario <= 0:
                    salario = j.contrato.salario
                break
        if not jogador:
            return json.dumps({"ok": False, "error": "Jogador não encontrado nos agentes livres"})
        # Verificar se tem saldo para o salário
        if salario <= 0:
            salario = max(jogador.valor_mercado // 120, 5000)
        folha_atual = gm.time_jogador.folha_salarial
        if folha_atual + salario > gm.time_jogador.financas.saldo:
            return json.dumps({"ok": False, "error": "Saldo insuficiente para a folha salarial"})
        try:
            ok = gm.mercado.contratar_livre(gm.time_jogador, jogador, salario)
            if ok:
                return json.dumps({"ok": True, "msg": f"{jogador.nome} contratado com sucesso!"})
            return json.dumps({"ok": False, "error": "Não foi possível contratar o jogador"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def fazer_oferta(self, jogador_id: int, valor: int, salario: int = 0) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        if not gm.mercado_aberto():
            return json.dumps({"ok": False, "error": "A janela de transferências está fechada no momento"})
        # Encontrar time vendedor e jogador
        for t in gm.todos_times():
            j = t.jogador_por_id(jogador_id)
            if j and t.nome != gm.time_jogador.nome:
                # IA de negociação: avalia se aceita a oferta
                valor_mercado = j.valor_mercado
                salario_atual = j.contrato.salario if j.contrato else 0
                if salario <= 0:
                    salario = salario_atual
                # Fator de aceitação baseado em valor oferecido vs valor de mercado
                import random
                ratio = valor / max(valor_mercado, 1)
                # Times com mais prestígio exigem mais
                prestigio_vendedor = getattr(t, 'prestigio', 70)
                exigencia = 0.8 + (prestigio_vendedor / 500)  # 0.8 ~ 1.0
                if ratio >= exigencia * 1.2:
                    aceita = True
                elif ratio >= exigencia:
                    aceita = random.random() < (ratio - exigencia * 0.7) / (exigencia * 0.5)
                else:
                    aceita = False
                if not aceita:
                    sugestao = int(valor_mercado * exigencia * 1.1)
                    return json.dumps({"ok": False,
                        "error": f"{t.nome} recusou a proposta de R$ {valor:,.0f}. "
                                 f"Valor estimado: R$ {sugestao:,.0f}"
                        .replace(",", ".")})
                # Verifica se o comprador tem saldo
                if gm.time_jogador.financas.saldo < valor:
                    return json.dumps({"ok": False, "error": "Saldo insuficiente para essa transferência"})
                from core.enums import TipoOferta, StatusOferta
                oferta = gm.mercado.fazer_oferta(
                    gm.time_jogador, t, j, valor, salario, TipoOferta.COMPRA
                )
                oferta.status = StatusOferta.ACEITA
                gm.mercado._executar_transferencia(oferta, gm.todos_times())
                return json.dumps({"ok": True, "oferta_id": oferta.id,
                    "msg": f"Proposta aceita! {j.nome} foi contratado."})
        return json.dumps({"ok": False, "error": "Jogador não encontrado"})

    def fazer_oferta_emprestimo(self, jogador_id: int, salario: int = 0) -> str:
        """Oferta de empréstimo de jogador de outro time."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        if not gm.mercado_aberto():
            return json.dumps({"ok": False, "error": "A janela de transferências está fechada no momento"})
        for t in gm.todos_times():
            j = t.jogador_por_id(jogador_id)
            if j and t.nome != gm.time_jogador.nome:
                import random
                valor_mercado = j.valor_mercado
                if salario <= 0:
                    salario = j.contrato.salario if j.contrato else 50000
                prestigio_vendedor = getattr(t, 'prestigio', 70)
                # Empréstimo aceito mais facilmente se time tem elenco grande ou jogador é reserva
                is_reserva = j.id not in t.titulares
                chance = 0.4 + (0.3 if is_reserva else 0.0) - (prestigio_vendedor / 500)
                if random.random() > chance:
                    return json.dumps({"ok": False,
                        "error": f"{t.nome} recusou o empréstimo de {j.nome}."})
                # Verificar folha salarial
                folha = gm.time_jogador.folha_salarial
                if folha + salario > gm.time_jogador.financas.saldo * 0.5:
                    return json.dumps({"ok": False, "error": "Folha salarial ficaria muito alta"})
                from core.enums import TipoOferta, StatusOferta
                clausula = int(valor_mercado * 0.7)
                oferta = gm.mercado.fazer_oferta(
                    gm.time_jogador, t, j, clausula, salario, TipoOferta.EMPRESTIMO
                )
                oferta.status = StatusOferta.ACEITA
                gm.mercado._executar_transferencia(oferta, gm.todos_times())
                return json.dumps({"ok": True, "oferta_id": oferta.id,
                    "msg": f"Empréstimo aceito! {j.nome} emprestado por 12 meses."})
        return json.dumps({"ok": False, "error": "Jogador não encontrado"})

    def emprestar_jogador(self, jogador_id: int) -> str:
        """Emprestar um jogador do próprio elenco para outro time (IA decide)."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        j = gm.time_jogador.jogador_por_id(jogador_id)
        if not j:
            return json.dumps({"ok": False, "error": "Jogador não encontrado"})
        import random
        # Procurar time interessado
        candidatos = [t for t in gm.todos_times()
                      if t.nome != gm.time_jogador.nome and len(t.jogadores) < 30]
        if not candidatos:
            return json.dumps({"ok": False, "error": "Nenhum time interessado"})
        destino = random.choice(candidatos[:10])
        from core.enums import TipoOferta, StatusOferta
        clausula = int(j.valor_mercado * 0.7)
        oferta = gm.mercado.fazer_oferta(
            destino, gm.time_jogador, j, clausula, j.contrato.salario, TipoOferta.EMPRESTIMO
        )
        oferta.status = StatusOferta.ACEITA
        gm.mercado._executar_transferencia(oferta, gm.todos_times())
        return json.dumps({"ok": True, "oferta_id": oferta.id,
            "msg": f"{j.nome} emprestado para {destino.nome} por 12 meses."})

    # ── Finanças ──────────────────────────────────────────────

    def get_financas(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        f = gm.time_jogador.financas
        return json.dumps({
            "saldo": f.saldo,
            "saldo_fmt": format_reais(f.saldo),
            "folha": gm.time_jogador.folha_salarial,
            "folha_fmt": format_reais(gm.time_jogador.folha_salarial),
            "receitas_mes": f.receitas_mes,
            "despesas_mes": f.despesas_mes,
            "patrocinio": f.receita_patrocinio_mensal,
            "tv": f.receita_tv_mensal,
            "patrocinador_nome": f.patrocinador_principal,
            "material_esportivo": f.material_esportivo,
            "patrocinador_costas": f.patrocinador_costas,
            "patrocinador_manga": f.patrocinador_manga,
            "socios": f.num_socios,
            "mensalidade": f.mensalidade_socio,
            "estadio": gm.time_jogador.estadio.nome if gm.time_jogador.estadio else "",
            "capacidade": gm.time_jogador.estadio.capacidade if gm.time_jogador.estadio else 0,
            "historico": f.historico_mensal[-12:],
        }, ensure_ascii=False, default=str)

    # ── Tática ────────────────────────────────────────────────

    def get_tatica(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador.tatica
        return json.dumps({
            "formacao": t.formacao.value if hasattr(t.formacao, 'value') else str(t.formacao),
            "estilo": t.estilo.value if hasattr(t.estilo, 'value') else str(t.estilo),
            "velocidade": t.velocidade.value if hasattr(t.velocidade, 'value') else str(t.velocidade),
            "marcacao": t.marcacao.value if hasattr(t.marcacao, 'value') else str(t.marcacao),
            "titulares": gm.time_jogador.titulares,
            "instrucoes": {
                "linha_alta": t.linha_alta,
                "contra_ataque": t.contra_ataque,
                "jogo_pelas_laterais": t.jogo_pelas_laterais,
                "jogo_pelo_centro": t.jogo_pelo_centro,
                "bola_longa": t.bola_longa,
                "toque_curto": t.toque_curto,
                "pressao_saida_bola": t.pressao_saida_bola,
                "zaga_adiantada": t.zaga_adiantada,
            },
            "cobradores": {
                "falta": t.cobrador_falta,
                "penalti": t.cobrador_penalti,
                "escanteio": t.cobrador_escanteio,
                "capitao": t.capitao,
            },
            "opcoes_formacao": [f.value for f in FormacaoTatica],
            "opcoes_estilo": [e.value for e in EstiloJogo],
            "opcoes_velocidade": [v.value for v in VelocidadeJogo],
            "opcoes_marcacao": [m.value for m in MarcacaoPressao],
            "escanteio_estilo": getattr(t, 'escanteio_estilo', 'areaCentral'),
            "falta_estilo": getattr(t, 'falta_estilo', 'direto'),
            "lateral_longo": getattr(t, 'lateral_longo', False),
            "defesa_escanteio": getattr(t, 'defesa_escanteio', 'zona'),
            "num_barreira_falta": getattr(t, 'num_barreira_falta', 3),
            "roles_jogadores": getattr(t, 'roles_jogadores', {}),
        }, ensure_ascii=False, default=str)

    def set_formacao(self, formacao_str: str) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        for f in FormacaoTatica:
            if f.value == formacao_str:
                gm.time_jogador.tatica.formacao = f
                return json.dumps({"ok": True})
        return json.dumps({"ok": False, "error": "Formação inválida"})

    def set_estilo(self, estilo_str: str) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        for e in EstiloJogo:
            if e.value == estilo_str:
                gm.time_jogador.tatica.estilo = e
                return json.dumps({"ok": True})
        return json.dumps({"ok": False, "error": "Estilo inválido"})

    def set_velocidade(self, vel_str: str) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        for v in VelocidadeJogo:
            if v.value == vel_str:
                gm.time_jogador.tatica.velocidade = v
                return json.dumps({"ok": True})
        return json.dumps({"ok": False, "error": "Velocidade inválida"})

    def set_marcacao(self, marc_str: str) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        for m in MarcacaoPressao:
            if m.value == marc_str:
                gm.time_jogador.tatica.marcacao = m
                return json.dumps({"ok": True})
        return json.dumps({"ok": False, "error": "Marcação inválida"})

    def set_titulares(self, ids: list) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        valid_ids = {j.id for j in gm.time_jogador.jogadores}
        clean = [i for i in ids if i in valid_ids]
        if len(clean) != 11:
            return json.dumps({"ok": False, "error": f"Selecione exatamente 11 jogadores (recebido {len(clean)})"})
        gm.time_jogador.titulares = clean
        return json.dumps({"ok": True})

    def set_instrucao(self, chave: str, valor: bool) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador.tatica
        allowed = {"linha_alta", "contra_ataque", "jogo_pelas_laterais",
                    "jogo_pelo_centro", "bola_longa", "toque_curto",
                    "pressao_saida_bola", "zaga_adiantada"}
        if chave not in allowed:
            return json.dumps({"ok": False, "error": "Instrução inválida"})
        setattr(t, chave, bool(valor))
        return json.dumps({"ok": True})

    def set_cobrador(self, tipo: str, jogador_id: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador.tatica
        mapping = {"falta": "cobrador_falta", "penalti": "cobrador_penalti",
                    "escanteio": "cobrador_escanteio", "capitao": "capitao"}
        attr = mapping.get(tipo)
        if not attr:
            return json.dumps({"ok": False, "error": "Tipo inválido"})
        setattr(t, attr, jogador_id if jogador_id else None)
        return json.dumps({"ok": True})

    # ── Artilharia ────────────────────────────────────────────

    def get_artilharia(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps([])
        art = getattr(gm, 'artilharia_memoria', {})
        if not art:
            return json.dumps([])
        ranking = sorted(art.values(), key=lambda x: (-x.get('gols', 0), -x.get('assists', 0)))[:30]
        return json.dumps([{
            "jogador_nome": r.get("nome", "?"),
            "time_nome": r.get("time", "?"),
            "gols": r.get("gols", 0),
            "assistencias": r.get("assists", 0),
        } for r in ranking], ensure_ascii=False, default=str)

    # ── Partida (última) ──────────────────────────────────────

    def get_ultima_partida(self) -> str:
        gm = self._gm
        if not gm or not gm.ultimo_resultado:
            return json.dumps(None)
        nome = gm.time_jogador.nome if gm.time_jogador else ""
        for comp_nome, comp_resultados in gm.ultimo_resultado.items():
            for r in comp_resultados:
                if r.time_casa == nome or r.time_fora == nome:
                    return json.dumps(
                        self._serializar_resultado_partida(r, comp_nome),
                        ensure_ascii=False,
                        default=str,
                    )
        return json.dumps(None)

    def get_proxima_partida(self) -> str:
        """Retorna informações da próxima partida agendada (apenas para a próxima semana)."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador
        nome = t.nome
        info = {"time_casa": nome, "time_fora": "A definir", "competicao": "Campeonato"}
        try:
            comps = gm.competicoes
            # Get which competitions are scheduled for the NEXT week
            proxima_semana = comps.semana_atual + 1
            comps_semana = comps.calendario.get(proxima_semana, [])
            if not comps_semana:
                return json.dumps(info, ensure_ascii=False, default=str)

            uf = t.estado

            # Check Supercopa Rei first (if scheduled)
            if "supercopa_rei" in comps_semana and comps.supercopa_rei and not comps.supercopa_rei.get("encerrado"):
                sc = comps.supercopa_rei
                if sc["time1"].nome == nome or sc["time2"].nome == nome:
                    info = {"time_casa": sc["time1"].nome, "time_fora": sc["time2"].nome, "competicao": "Supercopa Rei"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Check estaduais first (if scheduled)
            if "estadual" in comps_semana and uf and uf in comps.estaduais:
                est = comps.estaduais[uf]
                if not est.encerrado:
                    jogo = None
                    if est._em_mata_mata and est.semifinal and not est.semifinal.encerrado:
                        jogo = est.semifinal.jogo_do_jogador(t)
                    elif hasattr(est, 'fase_grupos') and est.fase_grupos and not est.fase_grupos.encerrado:
                        jogo = est.fase_grupos.jogo_do_jogador(t)
                    if jogo:
                        c, f = jogo
                        info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": est.nome}
                        return json.dumps(info, ensure_ascii=False, default=str)

            # Check brasileirão (if scheduled)
            if "brasileirao" in comps_semana:
                for attr in ['brasileirao_a', 'brasileirao_b', 'brasileirao_c', 'brasileirao_d']:
                    comp = getattr(comps, attr, None)
                    if comp and not comp.encerrado:
                        jogo = comp.jogo_do_jogador(t)
                        if jogo:
                            c, f = jogo
                            info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": attr}
                            return json.dumps(info, ensure_ascii=False, default=str)
            if "brasileirao_c" in comps_semana:
                comp = comps.brasileirao_c
                if comp and not comp.encerrado:
                    jogo = comp.jogo_do_jogador(t)
                    if jogo:
                        c, f = jogo
                        info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "brasileirao_c"}
                        return json.dumps(info, ensure_ascii=False, default=str)
            if "brasileirao_d" in comps_semana:
                comp = comps.brasileirao_d
                if comp and not comp.encerrado:
                    jogo = comp.jogo_do_jogador(t)
                    if jogo:
                        c, f = jogo
                        info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "brasileirao_d"}
                        return json.dumps(info, ensure_ascii=False, default=str)

            # Copa do Brasil (if scheduled)
            if "copa_brasil" in comps_semana and comps.copa_brasil and not comps.copa_brasil.encerrado:
                jogo = comps.copa_brasil.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "Copa Betano do Brasil"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Libertadores (if scheduled)
            if "libertadores" in comps_semana and comps.libertadores and not comps.libertadores.encerrado:
                jogo = comps.libertadores.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "CONMEBOL Libertadores"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Sul-Americana (if scheduled)
            if "sul_americana" in comps_semana and comps.sul_americana and not comps.sul_americana.encerrado:
                jogo = comps.sul_americana.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "CONMEBOL Sul-Americana"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # European leagues (if scheduled)
            if "europeias" in comps_semana and comps.ligas_europeias:
                for pais, divs in comps.ligas_europeias.items():
                    for div_num, liga in divs.items():
                        if not liga.encerrado:
                            jogo = liga.jogo_do_jogador(t)
                            if jogo:
                                c, f = jogo
                                info = {"time_casa": c.nome, "time_fora": f.nome,
                                        "competicao": f"liga_{pais}_{div_num}"}
                                return json.dumps(info, ensure_ascii=False, default=str)

            # Champions League (if scheduled)
            if "champions_league" in comps_semana and comps.champions_league and not comps.champions_league.encerrado:
                jogo = comps.champions_league.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "UEFA Champions League"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Europa League (if scheduled)
            if "europa_league" in comps_semana and comps.europa_league and not comps.europa_league.encerrado:
                jogo = comps.europa_league.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "UEFA Europa League"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Conference League (if scheduled)
            if "conference_league" in comps_semana and comps.conference_league and not comps.conference_league.encerrado:
                jogo = comps.conference_league.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "UEFA Conference League"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # AFC Champions League (if scheduled)
            if "afc_champions" in comps_semana and comps.afc_champions and not comps.afc_champions.encerrado:
                jogo = comps.afc_champions.jogo_do_jogador(t)
                if jogo:
                    c, f = jogo
                    info = {"time_casa": c.nome, "time_fora": f.nome, "competicao": "AFC Champions League"}
                    return json.dumps(info, ensure_ascii=False, default=str)

            # Amistoso agendado
            if gm.amistoso_agendado:
                info = {"time_casa": t.nome, "time_fora": gm.amistoso_agendado.nome,
                        "competicao": "Amistoso", "eh_amistoso": True}
                return json.dumps(info, ensure_ascii=False, default=str)

            # Sem jogo — informar que pode agendar amistoso
            info["sem_jogo"] = True
        except Exception:
            pass
        return json.dumps(info, ensure_ascii=False, default=str)

    # ── Scout ─────────────────────────────────────────────────

    def scout_avaliar(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        for t in gm.todos_times():
            j = t.jogador_por_id(jogador_id)
            if j:
                scout_staff = gm.time_jogador.staff_por_tipo(
                    __import__('core.enums', fromlist=['TipoStaff']).TipoStaff.SCOUT
                ) if gm.time_jogador else None
                qualidade = scout_staff.habilidade if scout_staff else 50
                avaliacao = self._scout.avaliar(j, qualidade)
                return json.dumps(avaliacao, ensure_ascii=False, default=str)
        return json.dumps(None)

    # ── Dispensar Jogador ─────────────────────────────────────

    def dispensar_jogador(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador
        j = t.jogador_por_id(jogador_id)
        if not j:
            return json.dumps({"ok": False, "error": "Jogador não encontrado"})
        if len(t.jogadores) <= 16:
            return json.dumps({"ok": False, "error": "Elenco mínimo de 16 jogadores"})
        # Remove from squad and titulares
        t.jogadores = [p for p in t.jogadores if p.id != jogador_id]
        if jogador_id in t.titulares:
            t.titulares = [tid for tid in t.titulares if tid != jogador_id]
        # Add to free agents
        gm.mercado.jogadores_livres.append(j)
        return json.dumps({"ok": True, "nome": j.nome})

    def renovar_contrato(self, jogador_id: int, novo_salario: int, duracao_meses: int) -> str:
        """Renew a player's contract."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador
        j = t.jogador_por_id(jogador_id)
        if not j:
            return json.dumps({"ok": False, "error": "Jogador não encontrado"})
        if novo_salario <= 0 or duracao_meses <= 0:
            return json.dumps({"ok": False, "error": "Valores inválidos"})
        multa = int(j.valor_mercado * 0.5)
        from engine.transfer_engine import MotorTransferencias
        ok = MotorTransferencias.renovar_contrato(j, novo_salario, duracao_meses, multa)
        if ok:
            return json.dumps({"ok": True, "nome": j.nome, "novo_salario": novo_salario,
                              "novo_salario_fmt": format_reais(novo_salario),
                              "duracao": duracao_meses})
        return json.dumps({"ok": False, "error": "Jogador recusou a proposta de renovação"})

    def get_negociacao_renovacao(self, jogador_id: int) -> str:
        """Get AI-calculated player demands for renewal negotiation."""
        import random as _rnd
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador
        j = t.jogador_por_id(jogador_id)
        if not j:
            return json.dumps(None)
        sal_atual = j.contrato.salario
        ovr = j.overall
        idade = j.idade
        moral = j.moral
        # Base salary expectation: higher OVR + younger = higher demand
        fator_ovr = 1.0 + max(0, (ovr - 65)) * 0.015
        fator_idade = 1.15 if idade <= 24 else 1.05 if idade <= 28 else 0.95 if idade <= 32 else 0.85
        fator_moral = 1.0 + (moral - 50) * 0.003
        salario_pedido = int(sal_atual * fator_ovr * fator_idade * fator_moral)
        salario_pedido = max(salario_pedido, int(sal_atual * 1.05))
        salario_minimo = int(salario_pedido * 0.85)
        duracao_desejada = 36 if idade <= 26 else 24 if idade <= 30 else 12
        humor = "exigente" if moral < 40 or j.quer_sair else "receptivo" if moral > 70 else "neutro"
        return json.dumps({
            "nome": j.nome, "overall": ovr, "idade": idade, "moral": moral,
            "salario_atual": sal_atual, "salario_atual_fmt": format_reais(sal_atual),
            "salario_pedido": salario_pedido, "salario_pedido_fmt": format_reais(salario_pedido),
            "salario_minimo": salario_minimo, "salario_minimo_fmt": format_reais(salario_minimo),
            "duracao_desejada": duracao_desejada,
            "humor": humor, "quer_sair": j.quer_sair,
            "meses_restantes": j.contrato.meses_restantes,
        }, ensure_ascii=False)

    def negociar_renovacao(self, jogador_id: int, salario_oferta: int, duracao: int) -> str:
        """AI negotiation round: player evaluates and may counter-offer."""
        import random as _rnd
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador
        j = t.jogador_por_id(jogador_id)
        if not j:
            return json.dumps({"ok": False, "error": "Jogador não encontrado"})
        sal_atual = j.contrato.salario
        ovr = j.overall
        idade = j.idade
        moral = j.moral
        fator_ovr = 1.0 + max(0, (ovr - 65)) * 0.015
        fator_idade = 1.15 if idade <= 24 else 1.05 if idade <= 28 else 0.95 if idade <= 32 else 0.85
        fator_moral = 1.0 + (moral - 50) * 0.003
        salario_pedido = int(sal_atual * fator_ovr * fator_idade * fator_moral)
        salario_pedido = max(salario_pedido, int(sal_atual * 1.05))
        salario_minimo = int(salario_pedido * 0.85)
        # Evaluate offer
        if salario_oferta >= salario_pedido:
            # Accept immediately
            multa = int(j.valor_mercado * 0.5)
            from engine.transfer_engine import MotorTransferencias
            ok = MotorTransferencias.renovar_contrato(j, salario_oferta, duracao, multa)
            if ok:
                return json.dumps({"resultado": "aceito", "nome": j.nome,
                                   "salario_final": salario_oferta,
                                   "salario_final_fmt": format_reais(salario_oferta),
                                   "duracao": duracao})
            return json.dumps({"resultado": "recusado", "motivo": "O jogador não quer renovar no momento."})
        elif salario_oferta >= salario_minimo:
            # Counter-offer: meet in the middle
            contra = int((salario_oferta + salario_pedido) / 2)
            chance = 0.3 + 0.7 * ((salario_oferta - salario_minimo) / max(1, salario_pedido - salario_minimo))
            if _rnd.random() < chance:
                multa = int(j.valor_mercado * 0.5)
                from engine.transfer_engine import MotorTransferencias
                ok = MotorTransferencias.renovar_contrato(j, salario_oferta, duracao, multa)
                if ok:
                    return json.dumps({"resultado": "aceito", "nome": j.nome,
                                       "salario_final": salario_oferta,
                                       "salario_final_fmt": format_reais(salario_oferta),
                                       "duracao": duracao})
            return json.dumps({"resultado": "contra_proposta",
                               "contra_salario": contra,
                               "contra_salario_fmt": format_reais(contra),
                               "mensagem": "O jogador pede R$ " + format_reais(contra) + "/mês para renovar."})
        else:
            # Too low
            if j.quer_sair or moral < 30:
                return json.dumps({"resultado": "recusado", "motivo": "O jogador recusou. Ele não está satisfeito no clube."})
            contra = salario_pedido
            return json.dumps({"resultado": "contra_proposta",
                               "contra_salario": contra,
                               "contra_salario_fmt": format_reais(contra),
                               "mensagem": "Oferta muito baixa. O jogador insiste em R$ " + format_reais(contra) + "/mês."})

    # ── Treinamento ───────────────────────────────────────────

    def get_treinamento(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        tr = gm.time_jogador.treinamento
        return json.dumps({
            "foco_tecnico": tr.foco_tecnico,
            "foco_fisico": tr.foco_fisico,
            "foco_tatico": tr.foco_tatico,
            "intensidade": tr.intensidade.value if hasattr(tr.intensidade, 'value') else str(tr.intensidade),
            "foco_principal": getattr(tr, 'foco_principal', 'finalizacao'),
            "foco_secundario": getattr(tr, 'foco_secundario', 'velocidade'),
            "auto_decidir": getattr(tr, 'auto_decidir', True),
        }, ensure_ascii=False)

    def set_treinamento(self, foco_tec: int, foco_fis: int,
                        foco_tat: int, intensidade: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        tr = gm.time_jogador.treinamento
        tr.foco_tecnico = max(0, min(100, foco_tec))
        tr.foco_fisico = max(0, min(100, foco_fis))
        tr.foco_tatico = max(0, min(100, foco_tat))
        tr.intensidade = max(1, min(100, intensidade))
        return json.dumps({"ok": True})

    def set_treinamento_ultrafoot(self, foco_principal: str, foco_secundario: str,
                                  auto_decidir: bool) -> str:
        """Ultrafoot-style training: choose primary & secondary skill focus."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        tr = gm.time_jogador.treinamento
        valid_principal = {"gol", "desarme", "armacao", "finalizacao"}
        valid_secundario = {"velocidade", "tecnica", "passe"}
        if foco_principal in valid_principal:
            tr.foco_principal = foco_principal
        if foco_secundario in valid_secundario:
            tr.foco_secundario = foco_secundario
        tr.auto_decidir = bool(auto_decidir)
        return json.dumps({"ok": True})

    # ── Amistosos ─────────────────────────────────────────────

    def listar_adversarios_amistoso(self) -> str:
        """Lista times disponíveis para amistoso."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps([])
        t = gm.time_jogador
        # Verificar se tem jogo oficial na próxima semana
        comps = gm.competicoes
        proxima = comps.semana_atual + 1
        comps_semana = comps.calendario.get(proxima, [])
        # Verificar se o time já tem jogo oficial
        tem_oficial = False
        for comp_name in comps_semana:
            casa, fora, _ = self._find_player_match_teams()
            if casa and fora:
                tem_oficial = True
                break
        if tem_oficial:
            return json.dumps({"error": "Você já tem jogo oficial esta semana"})
        # Selecionar adversários de divisões diferentes ou times que não enfrentará esta semana
        adversarios = []
        todos = gm.todos_times()
        for adv in todos:
            if adv.nome == t.nome:
                continue
            adversarios.append({
                "nome": adv.nome,
                "nome_curto": adv.nome_curto,
                "overall": adv.overall_medio,
                "divisao": adv.divisao,
                "estado": getattr(adv, 'estado', ''),
            })
        adversarios.sort(key=lambda x: x["overall"], reverse=True)
        return json.dumps(adversarios[:50], ensure_ascii=False, default=str)

    def agendar_amistoso(self, adversario_nome: str) -> str:
        """Agenda um amistoso para a próxima semana."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        if gm.amistoso_agendado:
            return json.dumps({"ok": False, "error": "Já existe um amistoso agendado"})
        # Verificar se não tem jogo oficial
        casa, fora, _ = self._find_player_match_teams()
        if casa and fora:
            return json.dumps({"ok": False, "error": "Você já tem jogo oficial esta semana"})
        # Encontrar adversário
        adversario = None
        for t in gm.todos_times():
            if t.nome == adversario_nome:
                adversario = t
                break
        if not adversario:
            return json.dumps({"ok": False, "error": "Adversário não encontrado"})
        gm.amistoso_agendado = adversario
        return json.dumps({"ok": True, "adversario": adversario.nome})

    def cancelar_amistoso(self) -> str:
        """Cancela amistoso agendado."""
        gm = self._gm
        if not gm:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        gm.amistoso_agendado = None
        return json.dumps({"ok": True})

    # ══════════════════════════════════════════════════════════
    #  NOVOS SISTEMAS FM-STYLE
    # ══════════════════════════════════════════════════════════

    # ── Data Hub / Analytics ──────────────────────────────────

    def get_data_hub(self) -> str:
        """Retorna analytics profundo do time do jogador."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador

        # Stats do elenco
        jogadores_stats = []
        for j in sorted(t.jogadores, key=lambda x: x.overall, reverse=True):
            h = j.historico_temporada
            jogadores_stats.append({
                "id": j.id, "nome": j.nome, "posicao": j.posicao.value,
                "overall": j.overall, "idade": j.idade,
                "jogos": h.jogos, "gols": h.gols, "assists": h.assistencias,
                "amarelos": h.cartoes_amarelos, "vermelhos": h.cartoes_vermelhos,
                "nota_media": round(h.nota_media, 1),
                "condicao": j.condicao_fisica, "moral": j.moral,
                "valor": j.valor_mercado,
                "traits": [tr.value for tr in j.traits],
            })

        # Médias do elenco
        total = len(t.jogadores) or 1
        media_ovr = sum(j.overall for j in t.jogadores) / total
        media_idade = sum(j.idade for j in t.jogadores) / total
        media_moral = sum(j.moral for j in t.jogadores) / total

        # Distribuição por posição
        pos_dist = {}
        for j in t.jogadores:
            pos = j.posicao.value
            pos_dist[pos] = pos_dist.get(pos, 0) + 1

        # Financeiro resumido
        fin = t.financas
        financeiro = {
            "saldo": fin.saldo,
            "receita_mensal": fin.receita_patrocinio_mensal + fin.receita_tv_mensal + fin.receita_socios_mensal,
            "folha_salarial": t.folha_salarial,
            "orcamento_transferencias": fin.orcamento_transferencias,
            "historico": fin.historico_mensal[-6:] if fin.historico_mensal else [],
        }

        # Forma recente (últimos resultados)
        forma = f"{t.vitorias}V {t.empates}E {t.derrotas}D"

        # Top artilheiros/assistentes
        artilheiros = sorted(t.jogadores, key=lambda j: j.historico_temporada.gols, reverse=True)[:5]
        assistentes = sorted(t.jogadores, key=lambda j: j.historico_temporada.assistencias, reverse=True)[:5]

        return json.dumps({
            "time": t.nome,
            "temporada": gm.temporada,
            "semana": gm.semana,
            "jogadores": jogadores_stats,
            "media_overall": round(media_ovr, 1),
            "media_idade": round(media_idade, 1),
            "media_moral": round(media_moral, 1),
            "distribuicao_posicoes": pos_dist,
            "financeiro": financeiro,
            "forma": forma,
            "vitorias": t.vitorias, "empates": t.empates, "derrotas": t.derrotas,
            "gols_pro": t.gols_pro, "gols_contra": t.gols_contra,
            "top_artilheiros": [{"nome": j.nome, "gols": j.historico_temporada.gols} for j in artilheiros],
            "top_assistentes": [{"nome": j.nome, "assists": j.historico_temporada.assistencias} for j in assistentes],
        }, ensure_ascii=False, default=str)

    # ── Reunião de Staff ──────────────────────────────────────

    def get_reuniao_staff(self) -> str:
        """Retorna a última reunião de staff disponível."""
        gm = self._gm
        if not gm:
            return json.dumps(None)
        reuniao = getattr(gm, '_ultima_reuniao_staff', None)
        if reuniao:
            gm._ultima_reuniao_staff = None  # consumida
        return json.dumps(reuniao, ensure_ascii=False, default=str)

    # ── Rede de Scouts ────────────────────────────────────────

    def get_scout_network(self) -> str:
        """Retorna estado da rede de scouts."""
        gm = self._gm
        if not gm:
            return json.dumps(None)
        network = getattr(gm, '_scout_network', None)
        if not network:
            from services.scout_service import ScoutNetwork
            gm._scout_network = ScoutNetwork()
            network = gm._scout_network
        return json.dumps(network.regioes_ativas(), ensure_ascii=False)

    def ativar_regiao_scout(self, regiao: str) -> str:
        """Ativa cobertura de scout em uma região."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        from services.scout_service import ScoutNetwork
        network = getattr(gm, '_scout_network', None)
        if not network:
            gm._scout_network = ScoutNetwork()
            network = gm._scout_network
        custo = network.custo_ativacao(regiao)
        if gm.time_jogador.financas.saldo < custo:
            return json.dumps({"ok": False, "error": f"Saldo insuficiente (custo: R$ {custo:,.0f})"})
        if network.ativar_regiao(regiao):
            gm.time_jogador.financas.saldo -= custo
            return json.dumps({"ok": True, "custo": custo})
        return json.dumps({"ok": False, "error": "Região já ativa ou inválida"})

    # ── Treino Individual ─────────────────────────────────────

    def set_treino_individual(self, jogador_id: int, foco: str) -> str:
        """Define plano de treino individual para um jogador."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        focos_validos = [
            "finalizacao", "desarme", "armacao", "gol", "cabecear",
            "drible", "passe", "cruzamento", "velocidade", "forca",
            "resistencia", "agilidade", "mentalidade", "lideranca",
            "visao", "posicionamento",
        ]
        if foco not in focos_validos:
            return json.dumps({"ok": False, "error": f"Foco inválido. Opções: {', '.join(focos_validos)}"})
        t = gm.time_jogador
        j = t.jogador_por_id(jogador_id)
        if not j:
            return json.dumps({"ok": False, "error": "Jogador não encontrado"})
        t.treinamento.planos_individuais[jogador_id] = {"foco": foco}
        return json.dumps({"ok": True, "jogador": j.nome, "foco": foco})

    def remover_treino_individual(self, jogador_id: int) -> str:
        """Remove plano de treino individual."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = gm.time_jogador
        t.treinamento.planos_individuais.pop(jogador_id, None)
        return json.dumps({"ok": True})

    def get_treinos_individuais(self) -> str:
        """Retorna planos de treino individual de todos os jogadores."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({})
        t = gm.time_jogador
        planos = {}
        for jid, plano in t.treinamento.planos_individuais.items():
            j = t.jogador_por_id(jid)
            if j:
                planos[str(jid)] = {
                    "nome": j.nome, "posicao": j.posicao.value,
                    "foco": plano.get("foco", ""),
                    "overall": j.overall,
                }
        return json.dumps(planos, ensure_ascii=False)

    # ── Set Pieces (Estratégias de Bola Parada) ───────────────

    def set_estrategia_bola_parada(self, escanteio_estilo: str = None,
                                     falta_estilo: str = None,
                                     lateral_longo: bool = None,
                                     defesa_escanteio: str = None,
                                     num_barreira: int = None) -> str:
        """Configura estratégias de bola parada."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        tac = gm.time_jogador.tatica
        if escanteio_estilo and escanteio_estilo in ("areaCentral", "primeiro_pau", "segundo_pau", "curto", "direto_area"):
            tac.escanteio_estilo = escanteio_estilo
        if falta_estilo and falta_estilo in ("direto", "cruzamento", "toque_curto", "por_cima"):
            tac.falta_estilo = falta_estilo
        if lateral_longo is not None:
            tac.lateral_longo = bool(lateral_longo)
        if defesa_escanteio and defesa_escanteio in ("zona", "individual", "misto"):
            tac.defesa_escanteio = defesa_escanteio
        if num_barreira is not None:
            tac.num_barreira_falta = max(2, min(5, int(num_barreira)))
        return json.dumps({"ok": True})

    # ── Roles Táticos ─────────────────────────────────────────

    def set_role_jogador(self, slot_idx: int, role: str, duty: str) -> str:
        """Define role e duty para um slot da formação."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        if slot_idx < 0 or slot_idx > 10:
            return json.dumps({"ok": False, "error": "Slot inválido (0-10)"})
        valid_duties = ("Defender", "Apoiar", "Atacar")
        if duty not in valid_duties:
            return json.dumps({"ok": False, "error": f"Duty inválido. Opções: {valid_duties}"})
        tac = gm.time_jogador.tatica
        tac.roles_jogadores[slot_idx] = {"role": role, "duty": duty}
        return json.dumps({"ok": True})

    def get_roles_disponiveis(self) -> str:
        """Retorna todos os roles e duties disponíveis."""
        from core.enums import TacticalRole, TacticalDuty
        roles = [{"id": r.name, "nome": r.value} for r in TacticalRole]
        duties = [{"id": d.name, "nome": d.value} for d in TacticalDuty]
        return json.dumps({"roles": roles, "duties": duties}, ensure_ascii=False)

    # ── Newgen Avatar ─────────────────────────────────────────

    def get_newgen_avatar(self, jogador_id: int) -> str:
        """Gera avatar procedural para um jogador."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        j = gm.time_jogador.jogador_por_id(jogador_id)
        if not j:
            # Buscar em todos os times
            for t in gm.todos_times():
                j = t.jogador_por_id(jogador_id)
                if j:
                    break
        if not j:
            return json.dumps(None)
        avatar = gm.newgen_avatar_engine.gerar_avatar(j)
        return json.dumps(avatar, ensure_ascii=False)

    def get_formacoes_disponiveis(self) -> str:
        """Retorna todas as formações disponíveis."""
        from core.enums import FormacaoTatica
        formacoes = [{"id": f.name, "nome": f.value} for f in FormacaoTatica]
        return json.dumps(formacoes, ensure_ascii=False)

    def get_traits_lista(self) -> str:
        """Retorna todos os traits disponíveis no jogo."""
        from core.enums import TraitJogador
        traits = [{"id": t.name, "nome": t.value} for t in TraitJogador]
        return json.dumps(traits, ensure_ascii=False)

    # ── Estádio ───────────────────────────────────────────────

    def get_estadio_detalhes(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        e = gm.time_jogador.estadio
        return json.dumps({
            "nome": e.nome,
            "capacidade": e.capacidade,
            "cap_geral": getattr(e, 'cap_geral', int(e.capacidade * 0.5)),
            "cap_arquibancada": getattr(e, 'cap_arquibancada', int(e.capacidade * 0.27)),
            "cap_cadeira": getattr(e, 'cap_cadeira', int(e.capacidade * 0.16)),
            "cap_camarote": getattr(e, 'cap_camarote', int(e.capacidade * 0.07)),
            "preco_geral": getattr(e, 'preco_geral', 30),
            "preco_arquibancada": getattr(e, 'preco_arquibancada', 50),
            "preco_cadeira": getattr(e, 'preco_cadeira', 80),
            "preco_camarote": getattr(e, 'preco_camarote', 150),
            "nivel_gramado": e.nivel_gramado,
            "nivel_estrutura": e.nivel_estrutura,
            "custo_expansao": int(e.capacidade * 500),
        }, ensure_ascii=False)

    def set_precos_estadio(self, geral: int, arquibancada: int,
                            cadeira: int, camarote: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        e = gm.time_jogador.estadio
        e.preco_geral = max(5, min(500, geral))
        e.preco_arquibancada = max(10, min(800, arquibancada))
        e.preco_cadeira = max(20, min(1200, cadeira))
        e.preco_camarote = max(50, min(2000, camarote))
        # Update average ingresso price
        total_cap = (getattr(e, 'cap_geral', 0) + getattr(e, 'cap_arquibancada', 0) +
                     getattr(e, 'cap_cadeira', 0) + getattr(e, 'cap_camarote', 0))
        if total_cap > 0:
            e.preco_ingresso = int(
                (e.preco_geral * getattr(e, 'cap_geral', 0) +
                 e.preco_arquibancada * getattr(e, 'cap_arquibancada', 0) +
                 e.preco_cadeira * getattr(e, 'cap_cadeira', 0) +
                 e.preco_camarote * getattr(e, 'cap_camarote', 0)) / total_cap
            )
        return json.dumps({"ok": True})

    def expandir_estadio(self, adicionar: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        e = gm.time_jogador.estadio
        custo = adicionar * 500
        if gm.time_jogador.financas.saldo < custo:
            return json.dumps({"ok": False, "error": "Saldo insuficiente"})
        gm.time_jogador.financas.saldo -= custo
        e.capacidade += adicionar
        # Distribute new seats proportionally
        e.cap_geral = getattr(e, 'cap_geral', 0) + int(adicionar * 0.5)
        e.cap_arquibancada = getattr(e, 'cap_arquibancada', 0) + int(adicionar * 0.27)
        e.cap_cadeira = getattr(e, 'cap_cadeira', 0) + int(adicionar * 0.16)
        e.cap_camarote = getattr(e, 'cap_camarote', 0) + int(adicionar * 0.07)
        return json.dumps({"ok": True, "nova_capacidade": e.capacidade,
                           "custo": custo})

    # ── Agenda / Calendário ───────────────────────────────────

    def get_agenda(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        jogos = []
        comps = gm.competicoes
        sem = getattr(comps, 'semana_atual', 0)
        calendario = getattr(comps, 'calendario', {})

        # Build week lists per calendar key for date mapping
        _comp_weeks: dict = {}
        for s in sorted(calendario.keys()):
            for ck in calendario[s]:
                _comp_weeks.setdefault(ck, []).append(s)

        def _add_comp_jogos(comp, comp_label, cal_key=None):
            if not comp:
                return
            tid = gm.time_jogador.id
            rodada_atual = getattr(comp, 'rodada_atual', 0)
            resultados = getattr(comp, 'resultados', [])
            weeks = _comp_weeks.get(cal_key, []) if cal_key else []
            for rodada_idx, rodada in enumerate(getattr(comp, 'jogos', [])):
                for c_id, f_id in rodada:
                    if c_id == tid or f_id == tid:
                        c = comp._time_por_id(c_id)
                        f = comp._time_por_id(f_id)
                        if not c or not f:
                            continue
                        is_passado = rodada_idx < rodada_atual
                        is_proximo = rodada_idx == rodada_atual
                        gols_casa = None
                        gols_fora = None
                        if is_passado and rodada_idx < len(resultados):
                            for r in resultados[rodada_idx]:
                                if r.time_casa == c.nome and r.time_fora == f.nome:
                                    gols_casa = r.gols_casa
                                    gols_fora = r.gols_fora
                                    break
                        status = "jogado" if is_passado else ("proximo" if is_proximo else "futuro")
                        semana_jogo = weeks[rodada_idx] if rodada_idx < len(weeks) else None
                        jogos.append({
                            "rodada": rodada_idx + 1,
                            "comp": comp_label,
                            "casa": c.nome,
                            "fora": f.nome,
                            "status": status,
                            "gols_casa": gols_casa,
                            "gols_fora": gols_fora,
                            "semana": semana_jogo,
                        })

        # Include all brasileirão divisions (no _comp_ativa gate)
        for attr_name, cal_key in [
            ('brasileirao_a', 'brasileirao'),
            ('brasileirao_b', 'serie_b_exclusiva'),
            ('brasileirao_c', 'brasileirao_c'),
            ('brasileirao_d', 'brasileirao_d'),
        ]:
            comp_obj = getattr(comps, attr_name, None)
            if comp_obj:
                _add_comp_jogos(comp_obj, attr_name.replace('_', ' ').title(), cal_key)

        # Include player's estadual
        uf = gm.time_jogador.estado
        if uf and uf in comps.estaduais:
            est = comps.estaduais[uf]
            if hasattr(est, 'fase_grupos') and est.fase_grupos:
                _add_comp_jogos(est.fase_grupos, est.nome, 'estadual')

        # Include Copa/Libertadores/Sul-Americana (knockout format)
        def _add_copa_jogos(copa, comp_label, cal_key=None):
            if not copa:
                return
            tid = gm.time_jogador.id
            weeks = _comp_weeks.get(cal_key, []) if cal_key else []
            for fase_idx, confrontos_fase in enumerate(copa.confrontos):
                for t1, t2 in confrontos_fase:
                    if not t1 or not t2:
                        continue
                    if t1.id != tid and t2.id != tid:
                        continue
                    fase_nome = copa.fases[fase_idx] if fase_idx < len(copa.fases) else f"Fase {fase_idx+1}"
                    idx_ida = fase_idx * 2
                    idx_volta = fase_idx * 2 + 1
                    semana_ida = weeks[idx_ida] if idx_ida < len(weeks) else None
                    semana_volta = weeks[idx_volta] if idx_volta < len(weeks) else None
                    # Jogo de ida
                    is_passado_ida = fase_idx < len(copa.resultados_ida)
                    gc_ida = gc_fora_ida = None
                    if is_passado_ida:
                        for r in copa.resultados_ida[fase_idx]:
                            if r.time_casa == t1.nome and r.time_fora == t2.nome:
                                gc_ida = r.gols_casa
                                gc_fora_ida = r.gols_fora
                                break
                    is_current_ida = fase_idx == copa.fase_atual and copa.jogo_ida
                    status_ida = "jogado" if is_passado_ida else ("proximo" if is_current_ida else "futuro")
                    jogos.append({
                        "rodada": fase_idx * 2 + 1,
                        "comp": f"{comp_label} - {fase_nome} (Ida)",
                        "casa": t1.nome,
                        "fora": t2.nome,
                        "status": status_ida,
                        "gols_casa": gc_ida,
                        "gols_fora": gc_fora_ida,
                        "semana": semana_ida,
                    })
                    # Jogo de volta
                    is_passado_volta = fase_idx < len(copa.resultados_volta)
                    gc_volta = gc_fora_volta = None
                    if is_passado_volta:
                        for r in copa.resultados_volta[fase_idx]:
                            if r.time_casa == t2.nome and r.time_fora == t1.nome:
                                gc_volta = r.gols_casa
                                gc_fora_volta = r.gols_fora
                                break
                    is_current_volta = fase_idx == copa.fase_atual and not copa.jogo_ida
                    status_volta = "jogado" if is_passado_volta else ("proximo" if is_current_volta else "futuro")
                    jogos.append({
                        "rodada": fase_idx * 2 + 2,
                        "comp": f"{comp_label} - {fase_nome} (Volta)",
                        "casa": t2.nome,
                        "fora": t1.nome,
                        "status": status_volta,
                        "gols_casa": gc_volta,
                        "gols_fora": gc_fora_volta,
                        "semana": semana_volta,
                    })

        # Estadual mata-mata (after _add_copa_jogos is defined)
        if uf and uf in comps.estaduais:
            est = comps.estaduais[uf]
            if est.semifinal:
                _add_copa_jogos(est.semifinal, f"{est.nome} - Mata-Mata", 'estadual')

        def _add_comp_grupos_e_mata_mata(comp, comp_label, cal_key=None):
            if not comp:
                return
            grupos = getattr(comp, "grupos", None) or {}
            if isinstance(grupos, dict):
                grupos_iter = grupos.items()
            else:
                grupos_iter = [
                    (getattr(grupo, "nome", f"Grupo {idx + 1}"), grupo)
                    for idx, grupo in enumerate(grupos)
                ]
            for grupo_nome, grupo in grupos_iter:
                _add_comp_jogos(grupo, f"{comp_label} - {grupo_nome}", cal_key)
            mata_mata = getattr(comp, "mata_mata", None)
            if mata_mata:
                _add_copa_jogos(mata_mata, f"{comp_label} - Mata-Mata", cal_key)

        _add_copa_jogos(comps.copa_brasil, "Copa do Brasil", 'copa_brasil')
        _add_comp_grupos_e_mata_mata(comps.libertadores, "Libertadores", 'libertadores')
        _add_comp_grupos_e_mata_mata(comps.sul_americana, "Sul-Americana", 'sul_americana')

        # European domestic leagues
        if comps.ligas_europeias:
            from managers.competition_manager import _INT_LEAGUE_NAMES
            for pais, divs in comps.ligas_europeias.items():
                for div_num, liga in divs.items():
                    nome = _INT_LEAGUE_NAMES.get(pais, {}).get(div_num, f"Liga {pais} Div {div_num}")
                    _add_comp_jogos(liga, nome, 'europeias')

        _add_comp_grupos_e_mata_mata(comps.champions_league, "UEFA Champions League", 'champions_league')
        _add_comp_grupos_e_mata_mata(comps.europa_league, "UEFA Europa League", 'europa_league')
        _add_comp_grupos_e_mata_mata(comps.conference_league, "UEFA Conference League", 'conference_league')
        _add_comp_grupos_e_mata_mata(comps.afc_champions, "AFC Champions League", 'afc_champions')

        # Sort by semana, then by rodada
        jogos.sort(key=lambda j: (j.get("semana") or 999, j.get("rodada") or 0))

        return json.dumps(jogos, ensure_ascii=False)

    # ── Títulos recém-conquistados ────────────────────────────

    def get_titulos_semana(self) -> str:
        """Check if the player's team just became champion in any competition this week."""
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps([])
        t = gm.time_jogador
        comps = gm.competicoes
        titulos = []

        trophy_map = {
            "serie_a": "tr_nacional_BRA_d1.png",
            "serie_b": "tr_nacional_BRA_d2.png",
            "serie_c": "tr_nacional_BRA_d3.png",
            "serie_d": "tr_nacional_BRA_d4.png",
            "copa_brasil": "tr_copa_BRA.png",
            "libertadores": "tr_libertadores.png",
            "sul_americana": "tr_sulamericana.png",
            "champions_league": "tr_ligacampeoes.png",
            "europa_league": "tr_europaliga.png",
            "conference_league": "tr_conferenceliga.png",
            "afc_champions": "tr_afc.png",
        }

        # Check league-based competitions
        checks = [
            ("serie_a", comps.brasileirao_a, "Brasileirão Série A"),
            ("serie_b", comps.brasileirao_b, "Brasileirão Série B"),
            ("serie_c", comps.brasileirao_c, "Brasileirão Série C"),
            ("serie_d", comps.brasileirao_d, "Brasileirão Série D"),
        ]
        for key, comp, label in checks:
            if comp and comp.encerrado and comp.classificacao() and comp.classificacao()[0].id == t.id:
                titulos.append({"comp": label, "trofeu": trophy_map.get(key, "tr_nacionalgenerico.png")})

        # Check cup-based competitions
        cup_checks = [
            ("copa_brasil", comps.copa_brasil, "Copa do Brasil"),
            ("libertadores", comps.libertadores, "CONMEBOL Libertadores"),
            ("sul_americana", comps.sul_americana, "CONMEBOL Sul-Americana"),
        ]
        for key, comp, label in cup_checks:
            if comp and comp.encerrado and comp.campeao and comp.campeao.id == t.id:
                titulos.append({"comp": label, "trofeu": trophy_map.get(key, "tr_nacionalgenerico.png")})

        # Check estaduais
        uf = getattr(t, 'estado', '')
        if uf and uf in comps.estaduais:
            est = comps.estaduais[uf]
            if est.encerrado and est.campeao and est.campeao.id == t.id:
                tr = f"tr_estadual_{uf}.png"
                from managers.competition_manager import ESTADUAL_NOME_COMERCIAL
                label = ESTADUAL_NOME_COMERCIAL.get(uf, f"Estadual {uf}")
                titulos.append({"comp": label, "trofeu": tr})

        # Check European leagues
        if comps.ligas_europeias:
            for pais, divs in comps.ligas_europeias.items():
                for div_num, liga in divs.items():
                    if liga.encerrado and liga.classificacao() and liga.classificacao()[0].id == t.id:
                        key = f"liga_{pais}_{div_num}"
                        tr = f"tr_nacional_{pais}.png" if div_num == 1 else f"tr_nacional_{pais}_d{div_num}.png"
                        titulos.append({"comp": liga.nome, "trofeu": tr})

        # Check champions league
        if comps.champions_league and comps.champions_league.encerrado:
            cl = comps.champions_league
            if hasattr(cl, 'campeao') and cl.campeao and cl.campeao.id == t.id:
                titulos.append({"comp": "UEFA Champions League", "trofeu": "tr_ligacampeoes.png"})

        # Check europa league
        if comps.europa_league and comps.europa_league.encerrado:
            el = comps.europa_league
            if hasattr(el, 'campeao') and el.campeao and el.campeao.id == t.id:
                titulos.append({"comp": "UEFA Europa League", "trofeu": "tr_europaliga.png"})

        # Check conference league
        if comps.conference_league and comps.conference_league.encerrado:
            ecl = comps.conference_league
            if hasattr(ecl, 'campeao') and ecl.campeao and ecl.campeao.id == t.id:
                titulos.append({"comp": "UEFA Conference League", "trofeu": "tr_conferenceliga.png"})

        # Check AFC champions league
        if comps.afc_champions and comps.afc_champions.encerrado:
            afc = comps.afc_champions
            if hasattr(afc, 'campeao') and afc.campeao and afc.campeao.id == t.id:
                titulos.append({"comp": "AFC Champions League", "trofeu": "tr_afc.png"})

        return json.dumps(titulos, ensure_ascii=False)

    # ── Resultados da Rodada ──────────────────────────────────

    def get_resultados_rodada(self) -> str:
        gm = self._gm
        if not gm or not gm.ultimo_resultado:
            return json.dumps([])
        from managers.competition_manager import ESTADUAL_NOME_COMERCIAL
        comp_labels = {
            'serie_a': 'Brasileirão Série A', 'serie_b': 'Brasileirão Série B',
            'serie_c': 'Brasileirão Série C', 'serie_d': 'Brasileirão Série D',
            'copa_brasil': 'Copa do Brasil', 'libertadores': 'CONMEBOL Libertadores',
            'sul_americana': 'CONMEBOL Sul-Americana', 'champions_league': 'UEFA Champions League',
            'europa_league': 'UEFA Europa League', 'conference_league': 'UEFA Conference League',
            'afc_champions': 'AFC Champions League',
        }
        eu_league_labels = {}
        if gm.competicoes.ligas_europeias:
            for pais, divs in gm.competicoes.ligas_europeias.items():
                for div_num, liga in divs.items():
                    key = f"liga_{pais}_{div_num}"
                    nome_limpo = liga.nome.split(f" {gm.temporada}")[0] if gm.temporada else liga.nome
                    eu_league_labels[key] = nome_limpo

        # Determine player context for filtering
        player_estado = getattr(gm.time_jogador, 'estado', '') if gm.time_jogador else ''
        br_states = {'SP','RJ','MG','RS','PR','BA','SC','PE','CE','GO','PA','MA','MT','MS','ES',
                     'RN','PB','AL','PI','SE','AM','RO','TO','AC','AP','RR','DF'}
        is_eu_player = player_estado and player_estado not in br_states and len(player_estado) <= 3

        results = []
        for comp, lista in gm.ultimo_resultado.items():
            # Determine label
            if comp.startswith('estadual_'):
                uf = comp[9:]
                label = ESTADUAL_NOME_COMERCIAL.get(uf, f'Estadual {uf}') + f' {gm.temporada}'
            elif comp.startswith('liga_'):
                label = eu_league_labels.get(comp, comp)
            else:
                label = comp_labels.get(comp, comp)

            # Filter: skip irrelevant competitions to avoid huge result lists
            if comp.startswith('estadual_'):
                # BR players: only show their own state championship
                if not is_eu_player and player_estado:
                    if uf.upper() != player_estado.upper():
                        continue
                # EU players: skip all estaduais
                elif is_eu_player:
                    continue
            elif comp.startswith('liga_'):
                if is_eu_player:
                    parts = comp.split('_')
                    comp_pais = parts[1] if len(parts) >= 3 else ''
                    if comp_pais != player_estado:
                        continue
                else:
                    continue
            elif is_eu_player and comp in ('serie_a', 'serie_b', 'serie_c', 'serie_d',
                                            'copa_brasil', 'libertadores', 'sul_americana'):
                continue
            elif not is_eu_player and comp == 'champions_league':
                continue

            for r in lista:
                is_my_game = gm.time_jogador and (r.time_casa == gm.time_jogador.nome or r.time_fora == gm.time_jogador.nome)
                entry = {
                    "comp": label,
                    "casa": r.time_casa,
                    "fora": r.time_fora,
                    "gols_casa": r.gols_casa,
                    "gols_fora": r.gols_fora,
                    "meu_jogo": is_my_game,
                }
                if is_my_game:
                    entry["clima"] = getattr(r, 'clima', '')
                    entry["eh_derby"] = getattr(r, 'eh_derby', False)
                results.append(entry)
        return json.dumps(results, ensure_ascii=False)

    def get_resumo_semana(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({})
        return json.dumps(gm.get_resumo_semana(), ensure_ascii=False, default=str)

    # ── Histórico ─────────────────────────────────────────────

    def get_historico(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        # Artilharia
        art = sorted(gm.artilharia_memoria.values(),
                     key=lambda x: (-x.get('gols', 0), -x.get('assists', 0)))[:10]
        # Classification snapshot (top 10)
        classif_a = []
        if gm.competicoes.brasileirao_a:
            camp = gm.competicoes.brasileirao_a
            for i, t in enumerate(camp.classificacao()[:10]):
                s = camp.get_stats(t.id)
                classif_a.append({
                    "pos": i+1, "nome": t.nome, "pontos": s["pontos"],
                    "v": s["v"], "e": s["e"], "d": s["d"],
                    "gm": s["gm"], "gs": s["gs"],
                    "eh_jogador": t.eh_jogador,
                })
        # Player team stats (per-competition, from main league)
        t = gm.time_jogador
        meu_time = {}
        if t:
            # Find the player's main league campeonato
            player_camp = gm.competicoes.brasileirao_a
            for camp_check in [gm.competicoes.brasileirao_a, gm.competicoes.brasileirao_b,
                               gm.competicoes.brasileirao_c]:
                if camp_check and t in camp_check.times:
                    player_camp = camp_check
                    break
            ps = player_camp.get_stats(t.id) if player_camp and hasattr(player_camp, 'get_stats') else None
            meu_time = {
                "nome": t.nome,
                "divisao": t.divisao,
                "pontos": ps["pontos"] if ps else t.pontos,
                "vitorias": ps["v"] if ps else t.vitorias,
                "empates": ps["e"] if ps else t.empates,
                "derrotas": ps["d"] if ps else t.derrotas,
                "gols_marcados": ps["gm"] if ps else t.gols_marcados,
                "gols_sofridos": ps["gs"] if ps else t.gols_sofridos,
                "elenco_tamanho": len(t.jogadores),
                "overall": t.overall_medio,
            }
        # Top scorers in the team
        artilheiros_time = []
        if t:
            for j in sorted(t.jogadores,
                           key=lambda x: -(x.historico_temporada.gols if x.historico_temporada else 0))[:5]:
                ht = j.historico_temporada
                if ht and ht.gols > 0:
                    artilheiros_time.append({
                        "nome": j.nome, "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
                        "gols": ht.gols, "assists": ht.assistencias,
                        "jogos": ht.jogos, "nota_media": round(ht.nota_media, 1),
                    })
        # Transfers/contratações da temporada
        contratacoes = []
        for o in getattr(gm.mercado, 'historico_ofertas', []):
            status_val = o.status.value if hasattr(o.status, 'value') else str(o.status)
            if status_val in ('Aceita', 'aceita', 'Concluída', 'concluida'):
                contratacoes.append({
                    "jogador": o.jogador_nome,
                    "de": o.time_origem, "para": o.time_destino,
                    "valor_fmt": format_reais(o.valor),
                })
        return json.dumps({
            "temporada": gm.temporada,
            "semana": gm.semana,
            "meu_time": meu_time,
            "artilheiros": [{
                "nome": a.get("nome", "?"),
                "time": a.get("time", "?"),
                "gols": a.get("gols", 0),
                "assists": a.get("assists", 0),
            } for a in art],
            "classif_a": classif_a,
            "artilheiros_time": artilheiros_time,
            "contratacoes": contratacoes[-10:],
            "tecnicos_demitidos": gm.tecnicos_demitidos[-20:],
        }, ensure_ascii=False)

    # ── Base Juvenil ──────────────────────────────────────────

    def get_base_juvenil(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        bj = gm.time_jogador.base_juvenil
        jovens = []
        for j in getattr(bj, 'jogadores', []):
            jovens.append({
                "id": j.id, "nome": j.nome, "idade": j.idade,
                "posicao": j.posicao.value if hasattr(j.posicao, 'value') else str(j.posicao),
                "overall": j.overall, "potencial": j.potencial,
                "nacionalidade": getattr(j, 'nacionalidade', 'Brasil'),
                "pe": j.pe_preferido.value if hasattr(j.pe_preferido, 'value') else 'Direito',
                "desenvolvimento_pct": min(100, max(0, int((j.overall / max(j.potencial, 1)) * 100))),
                "traits": [tr.value if hasattr(tr, 'value') else str(tr) for tr in getattr(j, 'traits', [])],
            })
        return json.dumps({
            "nivel": bj.nivel,
            "investimento_mensal": getattr(bj, 'investimento_mensal', 100000),
            "jogadores": jovens,
            "vagas": 100 - len(jovens),
        }, ensure_ascii=False, default=str)

    def promover_juvenil(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        bj = gm.time_jogador.base_juvenil
        jogadores_bj = getattr(bj, 'jogadores', [])
        for j in jogadores_bj:
            if j.id == jogador_id:
                jogadores_bj.remove(j)
                gm.time_jogador.jogadores.append(j)
                return json.dumps({"ok": True, "nome": j.nome})
        return json.dumps({"ok": False, "error": "Jogador não encontrado na base"})

    def dispensar_juvenil(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        bj = gm.time_jogador.base_juvenil
        jogadores_bj = getattr(bj, 'jogadores', [])
        for j in jogadores_bj:
            if j.id == jogador_id:
                jogadores_bj.remove(j)
                return json.dumps({"ok": True, "nome": j.nome})
        return json.dumps({"ok": False, "error": "Jogador não encontrado na base"})

    # ── Info do Time (uniformes, cores) ───────────────────────

    def get_time_info(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps(None)
        t = gm.time_jogador
        return json.dumps({
            "nome": t.nome,
            "nome_curto": t.nome_curto,
            "cor1": t.cor_principal,
            "cor2": t.cor_secundaria,
            "divisao": t.divisao,
            "prestigio": t.prestigio,
        }, ensure_ascii=False)

    def get_adversario_info(self, nome_time: str) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        for t in gm.todos_times():
            if t.nome == nome_time:
                return json.dumps({
                    "nome": t.nome,
                    "nome_curto": t.nome_curto,
                    "cor1": t.cor_principal,
                    "cor2": t.cor_secundaria,
                }, ensure_ascii=False)
        return json.dumps(None)

    def get_team_profile(self, nome_time: str) -> str:
        """Full team profile for classification double-click."""
        gm = self._gm
        if gm:
            t = None
            for tm in gm.todos_times():
                if tm.nome == nome_time:
                    t = tm
                    break
            if t:
                jogadores = []
                for j in sorted(t.jogadores, key=lambda x: -x.overall):
                    jogadores.append({
                        "nome": j.nome, "posicao": j.posicao,
                        "overall": j.overall, "idade": j.idade,
                        "titular": j.titular, "moral": getattr(j, 'moral', 50),
                        "id": j.id,
                    })
                return json.dumps({
                    "nome": t.nome, "nome_curto": t.nome_curto,
                    "cor1": t.cor_principal, "cor2": t.cor_secundaria,
                    "divisao": t.divisao, "prestigio": t.prestigio,
                    "estadio": getattr(t, 'estadio_nome', getattr(t.financas, 'estadio_nome', '')),
                    "capacidade": getattr(t.financas, 'capacidade_estadio', 0),
                    "tecnico": getattr(t, 'tecnico_nome', ''),
                    "formacao": getattr(t, 'formacao', '4-4-2'),
                    "saldo_fmt": format_reais(t.financas.saldo),
                    "jogadores": jogadores,
                    "total_jogadores": len(t.jogadores),
                    "media_ovr": round(sum(j.overall for j in t.jogadores) / max(1, len(t.jogadores)), 1),
                }, ensure_ascii=False)
        # Fallback: read from seed files (editor without active game)
        return self._get_team_profile_from_seeds(nome_time)

    def _get_team_profile_from_seeds(self, nome_time: str) -> str:
        """Read team profile from seed JSON files when no game is active."""
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        # Search BR teams
        br_path = os.path.join(seeds_dir, "teams_br.json")
        pl_path = os.path.join(seeds_dir, "players_br.json")
        team_data = None
        divisao = ""
        with open(br_path, "r", encoding="utf-8") as f:
            br = json.load(f)
        labels = {"serie_a": "Série A", "serie_b": "Série B", "serie_c": "Série C", "serie_d": "Série D", "sem_divisao": "Sem Divisão"}
        for cat, lbl in labels.items():
            for t in br.get(cat, []):
                if t["nome"] == nome_time:
                    team_data = t
                    divisao = lbl
                    break
            if team_data:
                break
        # Search EU teams
        if not team_data:
            eu_path = os.path.join(seeds_dir, "teams_eu.json")
            pl_path = os.path.join(seeds_dir, "players_eu.json")
            if os.path.exists(eu_path):
                with open(eu_path, "r", encoding="utf-8") as f:
                    eu = json.load(f)
                for cc, country in eu.items():
                    ligas = country.get("ligas", [])
                    for div_key, teams in country.get("divisoes", {}).items():
                        for t in teams:
                            if t["nome"] == nome_time:
                                team_data = t
                                div_num = int(div_key.replace("div_", ""))
                                divisao = ligas[div_num - 1]["nome"] if div_num <= len(ligas) else f"Div {div_num}"
                                break
                        if team_data:
                            break
                    if team_data:
                        break
        if not team_data:
            return json.dumps(None)
        # Load players
        jogadores = []
        if os.path.exists(pl_path):
            with open(pl_path, "r", encoding="utf-8") as f:
                pl = json.load(f)
            for p in sorted(pl.get(nome_time, []), key=lambda x: -x.get("base", 50)):
                jogadores.append({
                    "nome": p["nome"], "posicao": p.get("pos", "MC"),
                    "overall": p.get("base", 50), "idade": p.get("idade", 25),
                    "titular": False, "moral": 50, "id": 0,
                    "pais": p.get("pais", team_data.get("estado", "")),
                    "lado": p.get("lado", ""),
                })
        return json.dumps({
            "nome": team_data["nome"],
            "nome_curto": team_data.get("curto", ""),
            "cor1": team_data.get("cor1", "#555"),
            "cor2": team_data.get("cor2", "#fff"),
            "divisao": divisao,
            "prestigio": team_data.get("prestigio", 50),
            "estadio": team_data.get("estadio_nome", ""),
            "capacidade": team_data.get("estadio_cap", 0),
            "tecnico": "",
            "formacao": "4-4-2",
            "saldo_fmt": format_reais(team_data.get("saldo", 0)),
            "jogadores": jogadores,
            "total_jogadores": len(jogadores),
            "media_ovr": round(sum(j["overall"] for j in jogadores) / max(1, len(jogadores)), 1),
            "file_key": team_data.get("file_key", ""),
            "cidade": team_data.get("cidade", ""),
            "estado": team_data.get("estado", ""),
            "torcida": team_data.get("torcida", 0),
        }, ensure_ascii=False)

    def editor_save_team(self, nome_time: str, changes: list) -> str:
        """Apply editor changes to a team's players (name, position, overall)."""
        gm = self._gm
        if not gm:
            return json.dumps({"ok": False, "error": "Sem jogo ativo"})
        t = None
        for tm in gm.todos_times():
            if tm.nome == nome_time:
                t = tm
                break
        if not t:
            return json.dumps({"ok": False, "error": "Time não encontrado"})
        jogadores_sorted = sorted(t.jogadores, key=lambda x: -x.overall)
        for idx, ch in enumerate(changes):
            if not ch or idx >= len(jogadores_sorted):
                continue
            j = jogadores_sorted[idx]
            if "nome" in ch and isinstance(ch["nome"], str) and ch["nome"].strip():
                j.nome = ch["nome"].strip()
            if "posicao" in ch and ch["posicao"] in (
                "GOL", "ZAG", "LD", "LE", "VOL", "MC", "ME", "MD", "MEI", "PE", "PD", "SA", "CA"
            ):
                j.posicao = ch["posicao"]
            if "overall" in ch:
                ovr = int(ch["overall"])
                ovr = max(1, min(99, ovr))
                j.overall = ovr
        return json.dumps({"ok": True})

    def editor_add_team(self, dados_json: str) -> str:
        """Adiciona um novo time via editor (salva no JSON de seeds)."""
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        nome = dados.get("nome", "").strip()
        pais = dados.get("pais", "BRA")
        if not nome:
            return json.dumps({"ok": False, "error": "Nome obrigatório"})
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        if pais == "BRA":
            path = os.path.join(seeds_dir, "teams_br.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            new_team = {
                "nome": nome, "estadio": dados.get("estadio", ""), "capacidade": dados.get("capacidade", 10000),
                "estado": dados.get("estado", "SP"), "prestigio": dados.get("prestigio", 15),
                "file_key": dados.get("file_key", nome.replace(" ", "") + "_bra"),
                "cor_texto": dados.get("cor_texto", "#000000"), "cor_fundo": dados.get("cor_fundo", "#FFFFFF"),
                "tecnico": dados.get("tecnico", ""), "tecnico_nac": dados.get("tecnico_nac", "Brasil"),
                "nivel": dados.get("nivel", 15), "reputacao": dados.get("reputacao", "Nacional"),
            }
            data.setdefault("sem_divisao", []).append(new_team)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            path = os.path.join(seeds_dir, "teams_eu.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if pais not in data:
                return json.dumps({"ok": False, "error": "País não encontrado"})
            divs = data[pais].get("divisoes", {})
            last_div = sorted(divs.keys())[-1] if divs else "div_1"
            new_team = {
                "nome": nome, "estadio": dados.get("estadio", ""), "capacidade": dados.get("capacidade", 10000),
                "prestigio": dados.get("prestigio", 15),
                "file_key": dados.get("file_key", nome.replace(" ", "") + "_" + pais.lower()),
                "cor_texto": dados.get("cor_texto", "#000000"), "cor_fundo": dados.get("cor_fundo", "#FFFFFF"),
                "tecnico": dados.get("tecnico", ""), "tecnico_nac": dados.get("tecnico_nac", ""),
            }
            data[pais]["divisoes"][last_div].append(new_team)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        _limpar_cache_seeds()
        return json.dumps({"ok": True, "nome": nome})

    def editor_update_team(self, dados_json: str) -> str:
        """Atualiza dados de um time existente no seed JSON."""
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        nome_original = dados.get("nome_original", "").strip()
        if not nome_original:
            return json.dumps({"ok": False, "error": "Nome original obrigatório"})
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        updated = False
        for fname in ["teams_br.json", "teams_eu.json"]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if fname == "teams_br.json":
                for cat in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
                    for t in data.get(cat, []):
                        if t["nome"] == nome_original:
                            for k in ["nome", "estadio", "capacidade", "estado", "prestigio", "file_key", "cor1", "cor2", "tecnico", "tecnico_nac", "nivel", "reputacao"]:
                                if k in dados:
                                    t[k] = dados[k]
                            updated = True
                            break
                    if updated:
                        break
            else:
                for cc, country in data.items():
                    for div_key, teams in country.get("divisoes", {}).items():
                        for t in teams:
                            if t["nome"] == nome_original:
                                for k in ["nome", "estadio", "capacidade", "prestigio", "file_key", "cor1", "cor2", "tecnico", "tecnico_nac"]:
                                    if k in dados:
                                        t[k] = dados[k]
                                updated = True
                                break
                        if updated:
                            break
                    if updated:
                        break
            if updated:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                break
        if updated:
            _limpar_cache_seeds()
        return json.dumps({"ok": updated})

    def editor_delete_team(self, nome_time: str) -> str:
        """Remove um time do seed JSON."""
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        deleted = False
        for fname in ["teams_br.json", "teams_eu.json"]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if fname == "teams_br.json":
                for cat in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
                    original_len = len(data.get(cat, []))
                    data[cat] = [t for t in data.get(cat, []) if t["nome"] != nome_time]
                    if len(data[cat]) < original_len:
                        deleted = True
                        break
            else:
                for cc, country in data.items():
                    for div_key, teams in country.get("divisoes", {}).items():
                        original_len = len(teams)
                        country["divisoes"][div_key] = [t for t in teams if t["nome"] != nome_time]
                        if len(country["divisoes"][div_key]) < original_len:
                            deleted = True
                            break
                    if deleted:
                        break
            if deleted:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                break
        if deleted:
            _limpar_cache_seeds()
        return json.dumps({"ok": deleted})

    def editor_add_player(self, dados_json: str) -> str:
        """Adiciona jogador a um time no seed JSON."""
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        time_nome = dados.get("time", "").strip()
        nome_jogador = dados.get("nome", "").strip()
        if not time_nome or not nome_jogador:
            return json.dumps({"ok": False, "error": "Campos obrigatórios"})
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        new_player = {
            "nome": nome_jogador,
            "posicao": dados.get("posicao", "MC"),
            "lado": dados.get("lado", "D"),
            "nacionalidade": dados.get("nacionalidade", "Brasil"),
            "idade": dados.get("idade", 20),
            "carac1": dados.get("carac1", ""),
            "carac2": dados.get("carac2", ""),
            "estrela": dados.get("estrela", False),
            "top_mundial": dados.get("top_mundial", False),
        }
        added = False
        for fname, is_br in [("players_br.json", True), ("players_eu.json", False)]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time_nome in data:
                data[time_nome].append(new_player)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                added = True
                break
        if not added:
            # add to BR players by default
            path = os.path.join(seeds_dir, "players_br.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
            data.setdefault(time_nome, []).append(new_player)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        _limpar_cache_seeds()
        return json.dumps({"ok": True})

    def editor_edit_player(self, dados_json: str) -> str:
        """Edita jogador de um time no seed JSON."""
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        time_nome = dados.get("time", "").strip()
        nome_original = dados.get("nome_original", "").strip()
        if not time_nome or not nome_original:
            return json.dumps({"ok": False, "error": "Campos obrigatórios"})
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        edited = False
        for fname in ["players_br.json", "players_eu.json"]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time_nome in data:
                for p in data[time_nome]:
                    if p.get("nome") == nome_original:
                        for k in ["nome", "posicao", "lado", "nacionalidade", "idade", "carac1", "carac2", "estrela", "top_mundial"]:
                            if k in dados:
                                p[k] = dados[k]
                        edited = True
                        break
                if edited:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    break
        if edited:
            _limpar_cache_seeds()
        return json.dumps({"ok": edited})

    def editor_delete_player(self, dados_json: str) -> str:
        """Remove jogador de um time no seed JSON."""
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        time_nome = dados.get("time", "").strip()
        nome_jogador = dados.get("nome", "").strip()
        if not time_nome or not nome_jogador:
            return json.dumps({"ok": False, "error": "Campos obrigatórios"})
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        deleted = False
        for fname in ["players_br.json", "players_eu.json"]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time_nome in data:
                before = len(data[time_nome])
                data[time_nome] = [p for p in data[time_nome] if p.get("nome") != nome_jogador]
                if len(data[time_nome]) < before:
                    deleted = True
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    break
        if deleted:
            _limpar_cache_seeds()
        return json.dumps({"ok": deleted})

    def editor_get_team_players_raw(self, time_nome: str) -> str:
        """Retorna jogadores do seed JSON (sem criar objetos Time)."""
        seeds_dir = os.path.join(_BASE, "data", "seeds")
        for fname in ["players_br.json", "players_eu.json"]:
            path = os.path.join(seeds_dir, fname)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time_nome in data:
                players = data[time_nome]
                return json.dumps({"ok": True, "jogadores": players, "tipo": "principal"}, ensure_ascii=False)
        return json.dumps({"ok": False, "jogadores": []})

    # ── Assets ────────────────────────────────────────────────

    def get_asset_base(self) -> str:
        """Retorna URL base para assets locais (file:// ou relativo)."""
        return json.dumps(_ASSET_BASE_URL)

    def get_escudo_b64(self, file_key: str) -> str:
        """Retorna escudo PNG como data URI base64."""
        path = os.path.join(_ESCUDOS_DIR, file_key + ".png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return json.dumps("data:image/png;base64," + b64)
        return json.dumps(None)

    def get_camisa_b64(self, file_key: str) -> str:
        """Retorna camisa PNG como data URI base64."""
        path = os.path.join(_CAMISAS_DIR, file_key + ".png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return json.dumps("data:image/png;base64," + b64)
        return json.dumps(None)

    def get_camisas_all(self, file_key: str) -> str:
        """Retorna as 3 camisas (titular, reserva, alternativa) como data URIs."""
        result = []
        for folder in ("camisas", "camisas2", "camisas3"):
            path = os.path.join(_BASE, "teams", folder, file_key + ".png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                result.append("data:image/png;base64," + b64)
            else:
                result.append(None)
        return json.dumps(result)

    def get_sound_b64(self, nome: str, narrador: str = "") -> str:
        """Retorna som WAV como data URI base64. Se narrador informado, busca na pasta dele."""
        if narrador:
            narr_dir = os.path.join(_SONS_DIR, "narrações", narrador)
            path = os.path.join(narr_dir, nome)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                return json.dumps("data:audio/wav;base64," + b64)
        path = os.path.join(_SONS_DIR, nome)
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return json.dumps("data:audio/wav;base64," + b64)
        return json.dumps(None)

    def get_narradores(self) -> str:
        """Lista narradores disponíveis na pasta sons/narrações."""
        narr_dir = os.path.join(_SONS_DIR, "narrações")
        if not os.path.isdir(narr_dir):
            return json.dumps([])
        narradores = sorted(
            d for d in os.listdir(narr_dir)
            if os.path.isdir(os.path.join(narr_dir, d))
        )
        return json.dumps(narradores, ensure_ascii=False)

    @staticmethod
    def _load_eu_teams_json():
        """Carrega teams_eu.json e retorna lista flat de dicts de times europeus."""
        eu_path = os.path.join(_BASE, "data", "seeds", "teams_eu.json")
        if not os.path.exists(eu_path):
            return []
        with open(eu_path, "r", encoding="utf-8") as f:
            eu_data = json.load(f)
        teams = []
        for cc, country in eu_data.items():
            for div_key, team_list in country.get("divisoes", {}).items():
                div_num = int(div_key.replace("div_", ""))
                for t in team_list:
                    t["_cc"] = cc
                    t["_div"] = div_num
                    teams.append(t)
        return teams

    def get_file_key_map(self) -> str:
        """Retorna mapeamento nome_time -> file_key para todos os times."""
        import json as _json
        teams_path = os.path.join(_BASE, "data", "seeds", "teams_br.json")
        if not os.path.exists(teams_path):
            return json.dumps({})
        with open(teams_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        result = {}
        for div in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
            for t in data.get(div, []):
                result[t["nome"]] = t.get("file_key", "")
        for t in self._load_eu_teams_json():
            result[t["nome"]] = t.get("file_key", "")
        return json.dumps(result, ensure_ascii=False)

    def get_team_display_map(self) -> str:
        """Retorna {nome: {curto, cor1, cor2, divisao, estado, prestigio}} para todos os times."""
        teams_path = os.path.join(_BASE, "data", "seeds", "teams_br.json")
        if not os.path.exists(teams_path):
            return json.dumps({})
        with open(teams_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        div_map = {"serie_a": 1, "serie_b": 2, "serie_c": 3, "serie_d": 4, "sem_divisao": 0}
        result = {}
        for div in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
            for t in data.get(div, []):
                result[t["nome"]] = {
                    "curto": t.get("curto", ""),
                    "cor1": t.get("cor1", "#555"),
                    "cor2": t.get("cor2", "#fff"),
                    "divisao": div_map.get(div, 0),
                    "estado": t.get("estado", ""),
                    "prestigio": t.get("prestigio", 50),
                }
        for t in self._load_eu_teams_json():
            result[t["nome"]] = {
                "curto": t.get("curto", ""),
                "cor1": t.get("cor1", "#555"),
                "cor2": t.get("cor2", "#fff"),
                "divisao": t["_div"],
                "estado": t.get("estado", t["_cc"]),
                "prestigio": t.get("prestigio", 50),
            }
        return json.dumps(result, ensure_ascii=False)

    def get_all_escudos_b64(self) -> str:
        """Retorna todos os escudos como {file_key: dataURI} numa única chamada."""
        teams_path = os.path.join(_BASE, "data", "seeds", "teams_br.json")
        if not os.path.exists(teams_path):
            return json.dumps({})
        with open(teams_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = {}
        for div in ["serie_a", "serie_b", "serie_c", "serie_d", "sem_divisao"]:
            for t in data.get(div, []):
                fk = t.get("file_key", "")
                if not fk or fk in result:
                    continue
                path = os.path.join(_ESCUDOS_DIR, fk + ".png")
                if os.path.exists(path):
                    with open(path, "rb") as f2:
                        b64 = base64.b64encode(f2.read()).decode("ascii")
                    result[fk] = "data:image/png;base64," + b64
        # European teams
        for t in self._load_eu_teams_json():
            fk = t.get("file_key", "")
            if not fk or fk in result:
                continue
            path = os.path.join(_ESCUDOS_DIR, fk + ".png")
            if os.path.exists(path):
                with open(path, "rb") as f2:
                    b64 = base64.b64encode(f2.read()).decode("ascii")
                result[fk] = "data:image/png;base64," + b64
        return json.dumps(result, ensure_ascii=False)

    # ── Mercado Avançado ──────────────────────────────────────

    def buscar_mercado(self, filtro_pos: str = "", filtro_idade_min: int = 0,
                       filtro_idade_max: int = 99, filtro_ovr_min: int = 0,
                       filtro_nome: str = "", tab: str = "livres",
                       filtro_nacionalidade: str = "", filtro_pais_liga: str = "") -> str:
        """Busca avançada no mercado com filtros."""
        gm = self._gm
        if not gm:
            return json.dumps({"ofertas": [], "livres": [], "times": []})

        # Jogadores livres filtrados
        livres = []
        for j in gm.mercado.jogadores_livres:
            pos_str = j.posicao.value if hasattr(j.posicao, "value") else str(j.posicao)
            if filtro_pos and pos_str != filtro_pos:
                continue
            if j.idade < filtro_idade_min or j.idade > filtro_idade_max:
                continue
            if j.overall < filtro_ovr_min:
                continue
            if filtro_nome and filtro_nome.lower() not in j.nome.lower():
                continue
            if filtro_nacionalidade and j.nacionalidade != filtro_nacionalidade:
                continue
            livres.append({
                "id": j.id, "nome": j.nome, "idade": j.idade,
                "posicao": pos_str, "overall": j.overall,
                "valor": j.valor_mercado,
                "valor_fmt": format_reais(j.valor_mercado),
                "salario": j.contrato.salario,
                "salario_fmt": format_reais(j.contrato.salario),
                "foto": self._player_photo_src(j),
            })
            if len(livres) >= 50:
                break

        # Jogadores de outros times (para proposta)
        times_jogadores = []
        if tab == "times":
            for t in gm.todos_times():
                if t.nome == gm.time_jogador.nome:
                    continue
                for j in t.jogadores:
                    pos_str = j.posicao.value if hasattr(j.posicao, "value") else str(j.posicao)
                    if filtro_pos and pos_str != filtro_pos:
                        continue
                    if j.idade < filtro_idade_min or j.idade > filtro_idade_max:
                        continue
                    if j.overall < filtro_ovr_min:
                        continue
                    if filtro_nome and filtro_nome.lower() not in j.nome.lower():
                        continue
                    times_jogadores.append({
                        "id": j.id, "nome": j.nome, "idade": j.idade,
                        "posicao": pos_str, "overall": j.overall,
                        "time": t.nome, "time_curto": t.nome_curto,
                        "valor": j.valor_mercado,
                        "valor_fmt": format_reais(j.valor_mercado),
                        "salario_fmt": format_reais(j.contrato.salario),
                        "foto": self._player_photo_src(j, t),
                    })
                    if len(times_jogadores) >= 100:
                        break
                if len(times_jogadores) >= 100:
                    break

        # Ofertas
        ofertas = [{
            "id": o.id, "jogador": o.jogador_nome,
            "origem": o.time_origem, "destino": o.time_destino,
            "valor": o.valor, "valor_fmt": format_reais(o.valor),
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
        } for o in gm.mercado.ofertas_pendentes]

        return json.dumps({
            "livres": livres,
            "ofertas": ofertas,
            "times": times_jogadores,
            "mercado_aberto": gm.mercado_aberto(),
        }, ensure_ascii=False, default=str)

    # ── Demissão / Ofertas Técnico ─────────────────────────────

    def pedir_demissao(self) -> str:
        gm = self._gm
        if not gm or not gm.time_jogador:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        gm.iniciar_desemprego()
        _discord.atualizar_desemprego(
            semanas=gm._semanas_desempregado,
            reputacao=gm.carreira_engine.carreira.reputacao,
        )
        return json.dumps({
            "ok": True, "desempregado": True,
            "ofertas": gm._ofertas_emprego,
        }, ensure_ascii=False)

    def aceitar_oferta_tecnico(self, nome_time: str) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({"ok": False, "error": "Nenhum jogo ativo"})
        # Desempregado: usar novo fluxo
        if gm._desempregado:
            ok = gm.aceitar_oferta_emprego(nome_time)
            if ok and gm.time_jogador:
                _discord.atualizar_jogo(
                    time=gm.time_jogador.nome,
                    temporada=gm.temporada,
                    semana=gm.semana,
                )
            return json.dumps({"ok": ok}, ensure_ascii=False)
        novo_time = None
        for t in gm.todos_times():
            if t.nome == nome_time:
                novo_time = t
                break
        if not novo_time:
            return json.dumps({"ok": False, "error": "Time não encontrado"})
        # Resetar time anterior
        old = gm.time_jogador
        if old:
            old.eh_jogador = False
            old.diretoria.demitido = False
        # Configurar novo time
        novo_time.eh_jogador = True
        gm.time_jogador = novo_time
        novo_time.diretoria.demitido = False
        novo_time.diretoria.satisfacao = 60
        novo_time.diretoria.paciencia = 50
        # Registrar na carreira
        if hasattr(gm, 'carreira_engine'):
            old_nome = old.nome if old else ""
            gm.carreira_engine.registrar_novo_time(
                novo_time.nome, old_nome, gm.semana,
            )
        _discord.atualizar_jogo(
            time=novo_time.nome,
            temporada=gm.temporada,
            semana=gm.semana,
        )
        return json.dumps({"ok": True}, ensure_ascii=False)

    # ── Sistemas Avançados — API ──────────────────────────────

    def get_promessas(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps([])
        pe = gm.promessas_engine
        return json.dumps([{
            "id": p.id, "tipo": p.tipo.value if hasattr(p.tipo, 'value') else str(p.tipo),
            "descricao": p.descricao, "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
            "jogador_nome": p.jogador_nome, "semanas_restantes": p.semanas_restantes,
            "prazo": p.prazo_semanas,
        } for p in pe.promessas], ensure_ascii=False)

    def fazer_promessa(self, tipo: str, jogador_id: int = 0,
                       jogador_nome: str = "", prazo: int = 12) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({"ok": False})
        from core.enums import TipoPromessa
        try:
            tp = TipoPromessa(tipo)
        except (ValueError, KeyError):
            return json.dumps({"ok": False, "error": "Tipo inválido"})
        p = gm.promessas_engine.fazer_promessa(tp, jogador_id, jogador_nome, prazo)
        return json.dumps({"ok": True, "id": p.id, "descricao": p.descricao}, ensure_ascii=False)

    def get_vestiario(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({})
        ve = gm.vestiario_engine
        d = ve.vestiario
        return json.dumps({
            "harmonia": d.harmonia, "coesao": d.coesao,
            "status": d.status.value if hasattr(d, 'status') else "NORMAL",
            "lider_id": d.lider_id,
            "panelinhas": getattr(d, "panelinhas", []),
            "tensoes": getattr(d, "tensoes", []),
            "eventos": [{"tipo": e.tipo.value if hasattr(e.tipo, 'value') else str(e.tipo),
                         "descricao": e.descricao, "impacto": e.impacto_moral}
                        for e in d.eventos_recentes[-10:]],
        }, ensure_ascii=False, default=str)

    def get_quimica_tatica(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({})
        qe = gm.quimica_engine
        q = qe.quimica
        return json.dumps({
            "familiaridade": q.familiaridade_formacao,
            "semanas_formacao": q.semanas_mesma_formacao,
            "entrosamento": q.entrosamento_geral,
            "nivel": q.nivel.value if hasattr(q, 'nivel') else "",
            "bonus_tatico": round(q.bonus_tatico, 3) if hasattr(q, 'bonus_tatico') else 0,
            "parcerias": q.parcerias[:10],
        }, ensure_ascii=False, default=str)

    def get_carreira_tecnico(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({})
        c = gm.carreira_engine.carreira
        return json.dumps({
            "nome": c.nome, "reputacao": c.reputacao,
            "experiencia": c.experiencia,
            "vitorias": c.vitorias_total, "empates": c.empates_total,
            "derrotas": c.derrotas_total,
            "aproveitamento": round(c.aproveitamento, 1),
            "titulos": c.titulos,
            "times_anteriores": c.times_anteriores,
            "estilo": c.estilo_preferido,
            "especialidade": c.especialidade,
        }, ensure_ascii=False, default=str)

    def get_analise_partida(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        return json.dumps(getattr(gm, 'ultima_analise', None), ensure_ascii=False, default=str)

    def get_objetivos_jogadores(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps([])
        oe = gm.objetivos_engine
        return json.dumps([{
            "jogador_id": o.jogador_id, "tipo": o.tipo,
            "descricao": o.descricao, "meta": o.meta,
            "progresso": o.progresso,
            "pct": round(o.progresso / o.meta * 100, 1) if o.meta > 0 else 0,
        } for o in oe.objetivos], ensure_ascii=False)

    def get_adaptacao_cultural(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps([])
        ae = gm.adaptacao_engine
        return json.dumps([{
            "jogador_id": a.jogador_id,
            "pais_origem": a.pais_origem, "pais_atual": a.pais_atual,
            "progresso": a.progresso,
            "fator_rendimento": round(a.fator_rendimento, 2),
        } for a in ae.adaptacoes], ensure_ascii=False, default=str)

    def get_agente_jogador(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        agente = gm.agentes_engine.get_agente_jogador(jogador_id)
        if not agente:
            return json.dumps(None)
        return json.dumps({
            "nome": agente.nome,
            "tipo": agente.tipo.value if hasattr(agente.tipo, 'value') else str(agente.tipo),
            "influencia": agente.influencia,
            "comissao_pct": agente.comissao_pct,
            "multiplicador": round(agente.multiplicador_pedido, 2),
        }, ensure_ascii=False, default=str)

    def avancar_semana_desempregado(self) -> str:
        gm = self._gm
        if not gm or not gm._desempregado:
            return json.dumps({"ok": False, "error": "Não está desempregado"})
        info = gm.avancar_semana_desempregado()
        return json.dumps({"ok": True, **info}, ensure_ascii=False, default=str)

    def get_status_desemprego(self) -> str:
        gm = self._gm
        if not gm:
            return json.dumps({"desempregado": False})
        return json.dumps({
            "desempregado": gm._desempregado,
            "semanas": gm._semanas_desempregado,
            "reputacao": gm.carreira_engine.carreira.reputacao,
            "ofertas": gm._ofertas_emprego,
        }, ensure_ascii=False, default=str)

    def fechar_app(self) -> str:
        if self._window:
            self._window.destroy()
        return json.dumps({"ok": True})

    # ── Histórico de Jogador ─────────────────────────────────

    def get_jogador_historico(self, jogador_id: int) -> str:
        gm = self._gm
        if not gm:
            return json.dumps(None)
        for t in gm.todos_times():
            j = t.jogador_por_id(jogador_id)
            if j:
                hist = []
                # Current season stats
                ht = j.historico_temporada
                if ht:
                    hist.append({
                        "temporada": gm.temporada,
                        "time": ht.time or t.nome,
                        "jogos": ht.jogos,
                        "gols": ht.gols,
                        "assistencias": ht.assistencias,
                        "cartoes_amarelos": ht.cartoes_amarelos,
                        "cartoes_vermelhos": ht.cartoes_vermelhos,
                        "nota_media": round(ht.nota_media, 1),
                    })
                # Past seasons if available
                for h in getattr(j, 'historico_carreira', []):
                    hist.append({
                        "temporada": h.temporada,
                        "time": h.time,
                        "jogos": h.jogos,
                        "gols": h.gols,
                        "assistencias": h.assistencias,
                        "cartoes_amarelos": h.cartoes_amarelos,
                        "cartoes_vermelhos": h.cartoes_vermelhos,
                        "nota_media": round(h.nota_media, 1),
                    })
                return json.dumps(hist, ensure_ascii=False)
        return json.dumps([])

    # ══════════════════════════════════════════════════════════
    #  INBOX / CENTRAL DE NOTIFICAÇÕES
    # ══════════════════════════════════════════════════════════

    def get_inbox(self, categoria: str = "", remetente: str = "",
                  prioridade: str = "", limite: int = 50) -> str:
        """Retorna mensagens da inbox do técnico."""
        if not self._gm:
            return json.dumps({"mensagens": [], "nao_lidas": 0, "criticas": 0})
        inbox = self._gm.inbox
        msgs = inbox.to_api_list(
            limite=limite,
            categoria=categoria or None,
            remetente=remetente or None,
            prioridade=prioridade or None,
        )
        return json.dumps({
            "mensagens": msgs,
            "nao_lidas": inbox.nao_lidas,
            "criticas": inbox.criticas,
        }, ensure_ascii=False)

    def inbox_marcar_lida(self, msg_id: int) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        ok = self._gm.inbox.marcar_lida(msg_id)
        return json.dumps({"ok": ok})

    def inbox_fixar(self, msg_id: int) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        ok = self._gm.inbox.marcar_fixada(msg_id)
        return json.dumps({"ok": ok})

    def inbox_arquivar(self, msg_id: int) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        ok = self._gm.inbox.arquivar(msg_id)
        return json.dumps({"ok": ok})

    def inbox_acao(self, msg_id: int, acao_valor: str) -> str:
        """Processa uma ação do técnico em uma mensagem."""
        if not self._gm:
            return json.dumps({"ok": False, "erro": "Jogo não carregado"})
        if acao_valor.startswith("aceitar_emprego_"):
            nome_time = acao_valor.replace("aceitar_emprego_", "", 1)
            ok = self._gm.aceitar_oferta_emprego(nome_time)
            resultado = {
                "ok": ok,
                "impactos": {
                    "carreira": f"Novo clube assumido: {nome_time}" if ok else "Nao foi possivel assumir o clube.",
                },
            }
            if ok:
                self._gm.inbox.processar_acao(msg_id, acao_valor, None)
            return json.dumps(resultado, ensure_ascii=False)
        resultado = self._gm.inbox.processar_acao(
            msg_id, acao_valor, self._gm.time_jogador)
        return json.dumps(resultado, ensure_ascii=False)

    def get_inbox_resumo(self) -> str:
        """Retorna resumo para badge na sidebar."""
        if not self._gm:
            return json.dumps({"nao_lidas": 0, "criticas": 0})
        return json.dumps({
            "nao_lidas": self._gm.inbox.nao_lidas,
            "criticas": self._gm.inbox.criticas,
        })

    # ══════════════════════════════════════════════════════════
    #  LICENCIAMENTO
    # ══════════════════════════════════════════════════════════

    def get_licensing(self) -> str:
        """Retorna dados completos de licenciamento."""
        if not self._gm:
            self._gm = GameManager()
        payload = self._gm.licensing.to_api_dict()
        payload["assets"] = self._gm.get_asset_registry()
        payload["license"] = self._gm.get_license_status()
        if self._gm.save_nome:
            payload["save_integrity"] = self._gm.validar_save(self._gm.save_nome)
        return json.dumps(payload, ensure_ascii=False)

    def get_licensing_compliance(self) -> str:
        """Retorna relatório de compliance."""
        if not self._gm:
            self._gm = GameManager()
        return json.dumps(self._gm.licensing.relatorio_compliance(), ensure_ascii=False)

    def licensing_atualizar_liga(self, liga_id: str, status: str) -> str:
        """Atualiza status de licença de uma liga."""
        if not self._gm:
            return json.dumps({"ok": False})
        from core.enums import StatusLicenca
        ok = self._gm.licensing.atualizar_status_liga(liga_id, StatusLicenca(status))
        return json.dumps({"ok": ok})

    def licensing_atualizar_clube(self, clube_id: str, status: str) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        from core.enums import StatusLicenca
        ok = self._gm.licensing.atualizar_status_clube(clube_id, StatusLicenca(status))
        return json.dumps({"ok": ok})

    # ══════════════════════════════════════════════════════════
    #  MÚSICA & SONS
    # ══════════════════════════════════════════════════════════

    def music_get_playlist(self) -> str:
        if not self._gm:
            return json.dumps([])
        return json.dumps(self._gm.music.get_playlist_info(), ensure_ascii=False)

    def music_get_faixa_atual(self) -> str:
        if not self._gm:
            return json.dumps(None)
        return json.dumps(self._gm.music.get_faixa_atual(), ensure_ascii=False)

    def music_get_faixa_b64(self, nome: str = "") -> str:
        if not self._gm:
            return json.dumps(None)
        b64 = self._gm.music.get_faixa_b64(nome)
        return json.dumps(b64)

    def music_get_faixa_url(self) -> str:
        """Retorna file:// URL da faixa atual (sem base64)."""
        if not self._gm:
            return json.dumps(None)
        url = self._gm.music.get_faixa_url()
        return json.dumps(url)

    def music_proxima(self) -> str:
        if not self._gm:
            return json.dumps(None)
        return json.dumps(self._gm.music.proxima(), ensure_ascii=False)

    def music_anterior(self) -> str:
        if not self._gm:
            return json.dumps(None)
        return json.dumps(self._gm.music.anterior(), ensure_ascii=False)

    def music_tocar_faixa(self, indice: int) -> str:
        if not self._gm:
            return json.dumps(None)
        return json.dumps(self._gm.music.tocar_faixa_por_indice(indice), ensure_ascii=False)

    def music_play_pause(self) -> str:
        if not self._gm:
            return json.dumps(False)
        return json.dumps(self._gm.music.play_pause())

    def music_play(self) -> str:
        if not self._gm:
            return json.dumps(False)
        return json.dumps(self._gm.music.play())

    def music_pause(self) -> str:
        if not self._gm:
            return json.dumps(False)
        return json.dumps(self._gm.music.pause())

    def music_set_volume(self, tipo: str, valor: float) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        self._gm.music.set_volume(tipo, valor)
        return json.dumps({"ok": True})

    def music_set_contexto(self, contexto: str) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        faixa = self._gm.music.set_contexto(contexto)
        return json.dumps({"ok": True, "faixa": faixa}, ensure_ascii=False)

    def music_set_streamer_safe(self, ativo: bool) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        faixa = self._gm.music.set_streamer_safe(ativo)
        return json.dumps({"ok": True, "faixa": faixa}, ensure_ascii=False)

    def music_set_shuffle(self, ativo: bool) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        self._gm.music.set_shuffle(ativo)
        return json.dumps({"ok": True})

    def music_get_narradores(self) -> str:
        if not self._gm:
            return json.dumps([])
        return json.dumps(self._gm.music.get_narradores(), ensure_ascii=False)

    def music_set_narrador(self, nome: str) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        ok = self._gm.music.set_narrador(nome)
        return json.dumps({"ok": ok})

    def music_get_som_b64(self, nome: str, narrador: str = "") -> str:
        if not self._gm:
            return json.dumps(None)
        b64 = self._gm.music.get_som_b64(nome, narrador)
        return json.dumps(b64)

    def set_presence_context(self, page: str) -> str:
        gm = self._gm
        if not gm:
            _discord.atualizar_menu()
            return json.dumps({"ok": True})
        if getattr(gm, "_desempregado", False) or page == "desemprego":
            _discord.atualizar_desemprego(
                semanas=getattr(gm, "_semanas_desempregado", 0),
                reputacao=gm.carreira_engine.carreira.reputacao,
            )
            return json.dumps({"ok": True})
        clube = gm.time_jogador.nome if gm.time_jogador else ""
        _discord.atualizar_contexto(
            page,
            clube=clube,
            temporada=gm.temporada,
            semana=gm.semana,
        )
        return json.dumps({"ok": True})

    def update_match_presence(self, time_casa: str, time_fora: str,
                              gols_casa: int, gols_fora: int,
                              minuto: int) -> str:
        """Atualiza Discord RPC durante partida ao vivo."""
        _discord.atualizar_partida(
            time_casa=time_casa, time_fora=time_fora,
            gols_casa=int(gols_casa), gols_fora=int(gols_fora),
            minuto=int(minuto),
        )
        return json.dumps({"ok": True})

    # ══════════════════════════════════════════════════════════
    #  COLETIVA DE IMPRENSA
    # ══════════════════════════════════════════════════════════

    def coletiva_gerar_pos_jogo(self, resultado_json: str) -> str:
        if not self._gm:
            return json.dumps(None)
        try:
            r_data = json.loads(resultado_json)
        except (json.JSONDecodeError, TypeError):
            return json.dumps(None)
        sessao = self._gm.coletiva.gerar_coletiva_pos_jogo(
            time_nome=r_data.get("time_nome", ""),
            resultado=r_data.get("resultado", "empate"),
            gols_pro=r_data.get("gols_pro", 0),
            gols_contra=r_data.get("gols_contra", 0),
            adversario=r_data.get("adversario", ""),
            jogador_destaque=r_data.get("jogador_destaque", ""),
            eh_derby=r_data.get("eh_derby", False),
        )
        if not sessao:
            return json.dumps(None)
        return json.dumps({
            "tipo": sessao.tipo.value,
            "perguntas": [
                {"id": i, "texto": p.texto, "jornalista": p.jornalista,
                 "veiculo": p.veiculo, "tons_sugeridos": [t.value for t in p.tom_sugerido]}
                for i, p in enumerate(sessao.perguntas)
            ],
        }, ensure_ascii=False)

    def coletiva_responder(self, pergunta_id: int, tom: str) -> str:
        if not self._gm:
            return json.dumps(None)
        from core.enums import TomResposta
        try:
            tom_enum = TomResposta(tom)
        except ValueError:
            tom_enum = TomResposta.DIPLOMATICO
        resp = self._gm.coletiva.responder_pergunta(pergunta_id, tom_enum)
        if not resp:
            return json.dumps(None)
        return json.dumps({
            "tom": resp.tom.value,
            "texto": resp.texto,
            "impacto_moral": resp.impacto_moral,
            "impacto_torcida": resp.impacto_torcida,
            "impacto_midia": resp.impacto_midia,
            "impacto_diretoria": resp.impacto_diretoria,
        }, ensure_ascii=False)

    def coletiva_finalizar(self) -> str:
        if not self._gm:
            return json.dumps(None)
        impactos = self._gm.coletiva.finalizar_coletiva()
        # Aplicar impactos no time do jogador
        t = self._gm.time_jogador
        if t and impactos:
            for j in t.jogadores:
                j.moral = max(0, min(100, j.moral + impactos.get("moral", 0)))
            t.diretoria.satisfacao = max(0, min(100,
                t.diretoria.satisfacao + impactos.get("diretoria", 0)))
        return json.dumps(impactos)

    # ══════════════════════════════════════════════════════════
    #  CONQUISTAS (ACHIEVEMENTS)
    # ══════════════════════════════════════════════════════════

    def get_conquistas(self) -> str:
        if not self._gm:
            return json.dumps([])
        todas = self._gm.conquistas.get_todas()
        if todas and isinstance(todas[0], dict):
            return json.dumps(todas, ensure_ascii=False, default=str)
        return json.dumps([{
            "id": c.id, "titulo": c.titulo, "descricao": c.descricao,
            "icone": c.icone, "categoria": c.categoria.value,
            "desbloqueada": c.desbloqueada,
            "progresso": c.progresso, "meta": c.meta,
        } for c in todas], ensure_ascii=False)

    def get_conquistas_recentes(self) -> str:
        if not self._gm:
            return json.dumps([])
        recentes = self._gm.conquistas.get_recentes()
        if recentes and isinstance(recentes[0], dict):
            return json.dumps(recentes, ensure_ascii=False, default=str)
        return json.dumps([{
            "id": c.id, "titulo": c.titulo, "descricao": c.descricao,
            "icone": c.icone,
        } for c in recentes], ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  PREMIAÇÕES (AWARDS)
    # ══════════════════════════════════════════════════════════

    def get_premiacoes(self, temporada: int = 0) -> str:
        if not self._gm:
            return json.dumps([])
        temp = temporada if temporada > 0 else self._gm.temporada
        lista = self._gm.premiacoes.get_premiacoes(temp)
        if lista and isinstance(lista[0], dict):
            return json.dumps(lista, ensure_ascii=False, default=str)
        return json.dumps([{
            "tipo": p.tipo.value, "temporada": p.temporada,
            "jogador_nome": p.jogador_nome, "time_nome": p.time_nome,
            "competicao": p.competicao, "valor": p.valor,
        } for p in lista], ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  RECORDES DE CARREIRA
    # ══════════════════════════════════════════════════════════

    def get_recordes(self) -> str:
        if not self._gm:
            return json.dumps([])
        todos = self._gm.recordes.get_todos()
        if todos and isinstance(todos[0], dict):
            return json.dumps(todos, ensure_ascii=False, default=str)
        return json.dumps([{
            "chave": r.chave, "descricao": r.descricao,
            "valor": r.valor, "detalhe": r.detalhe,
        } for r in todos], ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  TREINO INDIVIDUAL
    # ══════════════════════════════════════════════════════════

    def treino_individual(self, jogador_id: int, atributo: str) -> str:
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({"ok": False, "msg": "Sem jogo ativo"})
        t = self._gm.time_jogador
        jogador = t.jogador_por_id(jogador_id)
        if not jogador:
            return json.dumps({"ok": False, "msg": "Jogador não encontrado"})
        msg = self._gm.motor_temporada.processar_treino_individual(jogador, atributo)
        return json.dumps({"ok": True, "msg": msg}, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  DERBY / RIVALIDADES
    # ══════════════════════════════════════════════════════════

    def get_rivalidades(self) -> str:
        if not self._gm or not self._gm.time_jogador:
            return json.dumps([])
        nome = self._gm.time_jogador.nome
        rivais = self._gm._rivalidades.get(nome, [])
        return json.dumps(rivais, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  TUTORIAL / AUTO-SAVE
    # ══════════════════════════════════════════════════════════

    def get_tutorial_visto(self) -> str:
        if not self._gm:
            return json.dumps(False)
        return json.dumps(self._gm.tutorial_visto)

    def set_tutorial_visto(self) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        self._gm.tutorial_visto = True
        return json.dumps({"ok": True})

    def get_auto_save(self) -> str:
        if not self._gm:
            return json.dumps(True)
        return json.dumps(self._gm.auto_save_ativo)

    def set_auto_save(self, ativo: bool) -> str:
        if not self._gm:
            return json.dumps({"ok": False})
        self._gm.auto_save_ativo = ativo
        return json.dumps({"ok": True})

    # ══════════════════════════════════════════════════════════
    #  UPGRADES DE ESTÁDIO
    # ══════════════════════════════════════════════════════════

    def get_stadium_upgrades(self) -> str:
        if not self._gm or not self._gm.time_jogador:
            return json.dumps(None)
        t = self._gm.time_jogador
        est = t.estadio
        obras = getattr(est, 'obras_em_andamento', [])
        return json.dumps({
            "nome": est.nome,
            "capacidade": est.capacidade,
            "gramado": est.nivel_gramado,
            "estrutura": est.nivel_estrutura,
            "obras_em_andamento": obras,
            "semana_atual": self._gm.semana,
            "upgrades_disponiveis": [
                {"tipo": "capacidade", "custo": est.capacidade * 500,
                 "descricao": f"Ampliar para {est.capacidade + 5000} lugares",
                 "semanas": 8},
                {"tipo": "gramado", "custo": 2_000_000,
                 "descricao": f"Melhorar gramado ({est.nivel_gramado} → {min(100, est.nivel_gramado + 10)})",
                 "semanas": 4},
                {"tipo": "estrutura", "custo": 5_000_000,
                 "descricao": f"Melhorar estrutura ({est.nivel_estrutura} → {min(100, est.nivel_estrutura + 10)})",
                 "semanas": 6},
                {"tipo": "iluminacao", "custo": 3_000_000,
                 "descricao": "Instalar iluminação de LED",
                 "semanas": 4},
                {"tipo": "camarotes", "custo": 8_000_000,
                 "descricao": "Construir camarotes VIP",
                 "semanas": 10},
            ],
        }, ensure_ascii=False)

    def iniciar_upgrade_estadio(self, tipo: str) -> str:
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({"ok": False, "msg": "Sem jogo ativo"})
        t = self._gm.time_jogador
        est = t.estadio
        if not hasattr(est, 'obras_em_andamento'):
            est.obras_em_andamento = []
        # Check if already building this type
        for obra in est.obras_em_andamento:
            if obra.get("tipo") == tipo:
                return json.dumps({"ok": False, "msg": "Já existe uma obra deste tipo em andamento"})
        custos = {
            "capacidade": est.capacidade * 500,
            "gramado": 2_000_000,
            "estrutura": 5_000_000,
            "iluminacao": 3_000_000,
            "camarotes": 8_000_000,
        }
        semanas_map = {
            "capacidade": 8, "gramado": 4, "estrutura": 6,
            "iluminacao": 4, "camarotes": 10,
        }
        descricoes = {
            "capacidade": f"Ampliar para {est.capacidade + 5000} lugares",
            "gramado": f"Melhorar gramado ({est.nivel_gramado} → {min(100, est.nivel_gramado + 10)})",
            "estrutura": f"Melhorar estrutura ({est.nivel_estrutura} → {min(100, est.nivel_estrutura + 10)})",
            "iluminacao": "Instalar iluminação de LED",
            "camarotes": "Construir camarotes VIP",
        }
        custo = custos.get(tipo, 0)
        if custo <= 0:
            return json.dumps({"ok": False, "msg": "Tipo de upgrade inválido"})
        if t.financas.saldo < custo:
            return json.dumps({"ok": False, "msg": "Saldo insuficiente"})
        t.financas.saldo -= custo
        semanas = semanas_map.get(tipo, 4)
        semana_conclusao = self._gm.semana + semanas
        est.obras_em_andamento.append({
            "tipo": tipo,
            "descricao": descricoes.get(tipo, tipo),
            "custo": custo,
            "semanas_total": semanas,
            "semanas_restantes": semanas,
            "semana_conclusao": semana_conclusao,
        })
        return json.dumps({"ok": True,
                          "msg": f"Obra iniciada! Conclusão em {semanas} semanas.",
                          "semana_conclusao": semana_conclusao,
                          "novo_saldo": t.financas.saldo}, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    #  MERCADO DE STAFF
    # ══════════════════════════════════════════════════════════

    def get_staff_mercado(self) -> str:
        """Lista staff disponível no mercado para contratação."""
        if not self._gm:
            return json.dumps([])
        import random as _r
        nomes_treinadores = [
            "Abel Ferreira", "Renato Gaúcho", "Mano Menezes", "Luís Castro",
            "Fernando Diniz", "Dorival Júnior", "Tite", "Vanderlei Luxemburgo",
            "Rogério Ceni", "Felipão", "Cuca", "Jorge Jesus", "Artur Jorge",
            "Ramón Díaz", "Eduardo Coudet", "Diego Aguirre", "Vojvoda",
        ]
        nomes_prep = [
            "Paulo Lima", "Ricardo Duarte", "Marcos Souza", "André Cunha",
            "Eduardo Martins", "Felipe Oliveira", "Gustavo Santos",
        ]
        nomes_medicos = [
            "Dr. Carlos Ribeiro", "Dr. Paulo Andrade", "Dr. Marcos Ferreira",
            "Dr. Jorge Lima", "Dr. Roberto Nunes", "Dra. Ana Costa",
        ]
        nomes_olheiros = [
            "José Pereira", "Antonio Silva", "Manuel Costa", "Pedro Alves",
            "Francisco Souza", "Carlos Mendes", "Rafael Batista",
        ]
        mercado = []
        from core.enums import TipoStaff
        for tipo, nomes, sal_range in [
            (TipoStaff.TREINADOR, nomes_treinadores, (200_000, 2_000_000)),
            (TipoStaff.PREPARADOR, nomes_prep, (50_000, 300_000)),
            (TipoStaff.MEDICO, nomes_medicos, (80_000, 400_000)),
            (TipoStaff.SCOUT, nomes_olheiros, (40_000, 200_000)),
        ]:
            _r.shuffle(nomes)
            for nome in nomes[:4]:
                hab = _r.randint(40, 90)
                sal = int(sal_range[0] + (sal_range[1] - sal_range[0]) * hab / 100)
                mercado.append({
                    "nome": nome, "tipo": tipo.value,
                    "habilidade": hab, "salario": sal,
                    "idade": _r.randint(35, 65),
                })
        self._staff_mercado_cache = mercado
        return json.dumps(mercado, ensure_ascii=False)

    def contratar_staff(self, nome: str, tipo: str) -> str:
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({"ok": False, "msg": "Sem jogo ativo"})
        from core.enums import TipoStaff
        from core.models import StaffMembro
        t = self._gm.time_jogador
        # Use cached market (generated by get_staff_mercado)
        mercado = getattr(self, '_staff_mercado_cache', None)
        if not mercado:
            mercado_json = self.get_staff_mercado()
            mercado = json.loads(mercado_json)
        staff_dados = None
        for s in mercado:
            if s["nome"] == nome and s["tipo"] == tipo:
                staff_dados = s
                break
        if not staff_dados:
            return json.dumps({"ok": False, "msg": "Staff não encontrado no mercado"})
        # Substituir o staff do mesmo tipo existente
        tipo_enum = TipoStaff(tipo)
        max_id = max((s.id for s in t.staff), default=0) + 1
        novo = StaffMembro(
            id=max_id, nome=staff_dados["nome"],
            idade=staff_dados["idade"], tipo=tipo_enum,
            habilidade=staff_dados["habilidade"],
            salario=staff_dados["salario"],
        )
        # Remove staff antigo do mesmo tipo
        t.staff = [s for s in t.staff if s.tipo != tipo_enum]
        t.staff.append(novo)
        return json.dumps({"ok": True, "msg": f"{nome} contratado como {tipo}!"},
                         ensure_ascii=False)

    # ═══════════════════════════════════════════════════════════
    #  FFP / RANKING / HALL OF FAME / SCOUT ADVERSÁRIO
    # ═══════════════════════════════════════════════════════════

    def get_ffp_status(self) -> str:
        """Retorna status do Financial Fair Play."""
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({})
        limites = self._gm.ffp_engine.calcular_limites(self._gm.time_jogador)
        return json.dumps(limites, ensure_ascii=False, default=str)

    def get_world_ranking(self, top_n: int = 50) -> str:
        """Retorna ranking mundial de clubes."""
        if not self._gm:
            return json.dumps([])
        ranking = self._gm.rankings_engine.get_ranking(top_n)
        # Inclui posição do time do jogador
        minha_pos = None
        if self._gm.time_jogador:
            minha_pos = self._gm.rankings_engine.get_posicao(self._gm.time_jogador.nome)
        return json.dumps({"ranking": ranking, "meu_time": minha_pos}, ensure_ascii=False, default=str)

    def get_hall_of_fame(self) -> str:
        """Retorna Hall of Fame cumulativo."""
        if not self._gm:
            return json.dumps({"entradas": [], "lendas": []})
        return json.dumps({
            "entradas": self._gm.hall_of_fame.get_todos(),
            "lendas": self._gm.hall_of_fame.get_lendas(),
        }, ensure_ascii=False, default=str)

    def scout_relatorio_adversario(self, nome_time: str) -> str:
        """Relatório tático de um adversário via scout."""
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({})
        from core.enums import TipoStaff
        adversario = None
        for t in self._gm.todos_times():
            if t.nome == nome_time:
                adversario = t
                break
        if not adversario:
            return json.dumps({"erro": "Time não encontrado"})
        olheiro = self._gm.time_jogador.staff_por_tipo(TipoStaff.SCOUT)
        precisao = olheiro.habilidade if olheiro else 50
        rel = self._scout.relatorio_adversario(adversario, precisao)
        return json.dumps(rel, ensure_ascii=False, default=str)

    def get_world_hub(self) -> str:
        """Dados do Hub Futebol Mundial — resumo de várias ligas e competições."""
        if not self._gm:
            return json.dumps({})
        comp = self._gm.competicoes
        hub = {"ligas": [], "ranking_top10": [], "meu_time": None}

        # Top 10 ranking
        hub["ranking_top10"] = self._gm.rankings_engine.get_ranking(10)
        if self._gm.time_jogador:
            hub["meu_time"] = self._gm.rankings_engine.get_posicao(self._gm.time_jogador.nome)

        # Séries BR
        for label, liga in [("Série A", comp.brasileirao_a), ("Série B", comp.brasileirao_b),
                            ("Série C", comp.brasileirao_c), ("Série D", comp.brasileirao_d)]:
            if liga:
                cl = liga.classificacao()
                lider = cl[0].nome if cl else "—"
                hub["ligas"].append({"nome": label, "pais": "BR", "lider": lider, "times": len(cl)})

        # Europeias (1ª divisão de cada país)
        for pais, divs in self._gm.competicoes.ligas_europeias.items():
            liga1 = divs.get(1)
            if liga1:
                cl = liga1.classificacao()
                lider = cl[0].nome if cl else "—"
                hub["ligas"].append({"nome": f"{pais} - 1ª", "pais": pais, "lider": lider, "times": len(cl)})

        return json.dumps(hub, ensure_ascii=False, default=str)

    def get_dicas_assistente(self) -> str:
        """Retorna dicas contextuais do assistente técnico interno."""
        if not self._gm or not self._gm.time_jogador:
            return json.dumps({"dicas": []})
        t = self._gm.time_jogador
        dicas = []

        # Dica de condição física
        fatigados = [j for j in t.jogadores if j.id in t.titulares and j.condicao_fisica < 50]
        if fatigados:
            nomes = ", ".join(j.nome.split()[-1] for j in fatigados[:3])
            dicas.append({"tipo": "fadiga", "texto": f"Jogadores cansados: {nomes}. Considere poupar.", "prioridade": "alta"})

        # Dica moral baixa
        baixa_moral = [j for j in t.jogadores if j.id in t.titulares and j.moral < 40]
        if baixa_moral:
            nomes = ", ".join(j.nome.split()[-1] for j in baixa_moral[:3])
            dicas.append({"tipo": "moral", "texto": f"Moral baixa: {nomes}. Pode afetar desempenho.", "prioridade": "media"})

        # Dica de contrato
        expirando = [j for j in t.jogadores if j.contrato.meses_restantes <= 6 and j.overall > 60]
        if expirando:
            nomes = ", ".join(j.nome.split()[-1] for j in expirando[:3])
            dicas.append({"tipo": "contrato", "texto": f"Contratos expirando: {nomes}. Renove ou venda.", "prioridade": "media"})

        # Dica de lesão
        lesionados = [j for j in t.jogadores if j.status_lesao.name != "SAUDAVEL"]
        if lesionados:
            dicas.append({"tipo": "lesao", "texto": f"{len(lesionados)} jogador(es) lesionado(s).", "prioridade": "media"})

        # Dica FFP
        limites = self._gm.ffp_engine.calcular_limites(t)
        if not limites["em_conformidade_folha"]:
            dicas.append({"tipo": "ffp", "texto": "Atenção: folha salarial acima do limite FFP!", "prioridade": "alta"})

        # Dica de vestiário
        if hasattr(self._gm, 'vestiario_engine'):
            vest = self._gm.vestiario_engine
            if hasattr(vest, 'vestiario') and vest.vestiario.harmonia < 40:
                dicas.append({"tipo": "vestiario", "texto": "Clima tenso no vestiário. Cuidado com conflitos.", "prioridade": "alta"})

        return json.dumps({"dicas": dicas}, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
#  MAIN — Lançamento da janela desktop
# ══════════════════════════════════════════════════════════════

def _sync_index_html():
    """Copia index.html raiz para web/ (Tauri) ao iniciar em modo dev."""
    if getattr(sys, 'frozen', False):
        return  # EXE já tem index.html correto
    import shutil
    src = os.path.join(_BASE, "index.html")
    web_dest = os.path.join(_BASE, "web", "index.html")
    if os.path.exists(src) and os.path.isdir(os.path.dirname(web_dest)):
        shutil.copy2(src, web_dest)


def main():
    log.info("Iniciando Ultrafoot Desktop v%s", GAME_VERSION)
    _sync_index_html()  # Auto-sync web/index.html em dev mode
    _discord.iniciar()
    _discord.atualizar_menu()

    window_settings = UserSettingsService().load()
    api = UltrafootAPI()
    html_path = os.path.join(_BASE, "index.html")

    window = webview.create_window(
        title=f"{GAME_TITLE} v{GAME_VERSION}",
        url=html_path,
        js_api=api,
        width=int(window_settings.get("window_width", WINDOW_WIDTH)),
        height=int(window_settings.get("window_height", WINDOW_HEIGHT)),
        min_size=(1024, 600),
        background_color="#090a0f",
        text_select=False,
        zoomable=False,
        fullscreen=bool(window_settings.get("window_fullscreen", False)),
        maximized=bool(window_settings.get("window_maximized", True) and not window_settings.get("window_fullscreen", False)),
    )
    api.set_window(window)

    # private_mode=True evita cache persistente de webview (reduz uso de disco)
    # gui='edgechromium' garante o Edge WebView2 no Windows (mais leve que CEF)
    webview.start(debug=False, private_mode=True, gui="edgechromium")
    _discord.parar()


if __name__ == "__main__":
    main()
