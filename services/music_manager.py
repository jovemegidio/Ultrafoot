# -*- coding: utf-8 -*-
"""
Background music and audio state manager.

Supports:
- local offline tracks
- optional manifest metadata
- contextual playlists (menu, squad, market, pre_match, settings)
- streamer-safe filtering
- silent fallback when no valid track exists for the current context
"""
from __future__ import annotations

import base64
import json
import os
import random
import sys
from typing import Dict, Iterable, List, Optional

from utils.logger import get_logger

log = get_logger(__name__)

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DEFAULT_MUSIC_DIRS = [
    os.path.join(_BASE, "data", "assets", "music"),
    os.path.join(_BASE, "music"),
]
_DEFAULT_MANIFEST_PATHS = [
    os.path.join(_BASE, "data", "assets", "music", "manifest.json"),
    os.path.join(_BASE, "music", "manifest.json"),
]
SONS_DIR = os.path.join(_BASE, "sons")
_AUDIO_EXTENSIONS = (".mp3", ".ogg", ".wav")
_MENU_CONTEXTS = {"menu", "squad", "market", "settings", "general"}


class MusicManager:
    """Keeps the current soundtrack state for the desktop client."""

    def __init__(
        self,
        music_dirs: Optional[List[str]] = None,
        manifest_paths: Optional[List[str]] = None,
        sons_dir: Optional[str] = None,
    ) -> None:
        self._music_dirs = music_dirs or list(_DEFAULT_MUSIC_DIRS)
        self._manifest_paths = manifest_paths or list(_DEFAULT_MANIFEST_PATHS)
        self._sons_dir = sons_dir or SONS_DIR

        self._catalogo: List[Dict] = []
        self.playlist: List[str] = []
        self.indice_atual: int = 0
        self.tocando: bool = False
        self.volume_musica: float = 0.5
        self.volume_efeitos: float = 0.8
        self.volume_narracao: float = 0.7
        self.narrador_atual: str = "Luis Roberto"
        self.shuffle: bool = True
        self.repeat: bool = True
        self.contexto_atual: str = "menu"
        self.streamer_safe: bool = False
        self.musica_menu_ativa: bool = True
        self.musica_pre_jogo_ativa: bool = True

        self._carregar_catalogo()
        self._reconstruir_playlist(keep_current=False)

    def _carregar_catalogo(self) -> None:
        arquivos = self._descobrir_arquivos()
        manifest_entries = self._carregar_manifestos()

        catalogo: List[Dict] = []
        usados: set[str] = set()

        for raw in manifest_entries:
            faixa = self._faixa_manifesto(raw, arquivos)
            if not faixa:
                continue
            catalogo.append(faixa)
            usados.add(faixa["arquivo"])

        for arquivo, caminho in sorted(arquivos.items()):
            if arquivo in usados:
                continue
            catalogo.append(self._faixa_scan_padrao(arquivo, caminho))

        self._catalogo = catalogo
        log.info("Catalogo de musica carregado: %d faixas", len(self._catalogo))

    def _descobrir_arquivos(self) -> Dict[str, str]:
        arquivos: Dict[str, str] = {}
        for pasta in self._music_dirs:
            if not os.path.isdir(pasta):
                continue
            for nome in sorted(os.listdir(pasta)):
                if not nome.lower().endswith(_AUDIO_EXTENSIONS):
                    continue
                if nome in arquivos:
                    continue
                arquivos[nome] = os.path.join(pasta, nome)
        return arquivos

    def _carregar_manifestos(self) -> List[Dict]:
        entradas: List[Dict] = []
        for caminho in self._manifest_paths:
            if not os.path.isfile(caminho):
                continue
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception as e:
                log.warning("Manifesto de musica invalido em %s: %s", caminho, e)
                continue

            if isinstance(raw, dict):
                faixas = raw.get("tracks", [])
            elif isinstance(raw, list):
                faixas = raw
            else:
                faixas = []

            for item in faixas:
                if isinstance(item, dict):
                    item = dict(item)
                    item["_manifest_path"] = caminho
                    entradas.append(item)
        return entradas

    def _faixa_manifesto(self, raw: Dict, arquivos: Dict[str, str]) -> Optional[Dict]:
        arquivo = raw.get("arquivo") or raw.get("file")
        if not arquivo:
            return None
        caminho = arquivos.get(arquivo)
        if not caminho or not os.path.isfile(caminho):
            log.warning("Faixa do manifesto nao encontrada: %s", arquivo)
            return None
        titulo = raw.get("titulo") or raw.get("title") or self._titulo_limpo(arquivo)
        artista = raw.get("artista") or raw.get("artist") or ""
        contextos = self._normalizar_contextos(raw.get("contextos") or raw.get("contexts"))
        return {
            "arquivo": arquivo,
            "caminho": caminho,
            "asset_path": self._asset_path(caminho),
            "titulo": titulo,
            "artista": artista,
            "contextos": contextos,
            "streamer_safe": bool(raw.get("streamer_safe", False)),
            "licenca": raw.get("licenca") or raw.get("license") or "nao_verificada",
            "origem": raw.get("origem") or os.path.basename(raw.get("_manifest_path", "")) or "manifest",
        }

    def _faixa_scan_padrao(self, arquivo: str, caminho: str) -> Dict:
        return {
            "arquivo": arquivo,
            "caminho": caminho,
            "asset_path": self._asset_path(caminho),
            "titulo": self._titulo_limpo(arquivo),
            "artista": "",
            "contextos": ["menu", "general"],
            "streamer_safe": False,
            "licenca": "nao_verificada",
            "origem": "scan_local",
        }

    def _asset_path(self, caminho: str) -> str:
        try:
            rel = os.path.relpath(caminho, _BASE)
        except ValueError:
            rel = os.path.basename(caminho)
        return "/" + rel.replace("\\", "/")

    def _titulo_limpo(self, nome: str) -> str:
        titulo = nome
        if " - " in titulo:
            titulo = titulo.split(" - ", 1)[1]
        return os.path.splitext(titulo)[0]

    def _normalizar_contexto(self, contexto: str) -> str:
        valor = (contexto or "menu").strip().lower()
        aliases = {
            "inicio": "menu",
            "dashboard": "menu",
            "classificacao": "menu",
            "financas": "menu",
            "treinamento": "menu",
            "base": "menu",
            "agenda": "menu",
            "historico": "menu",
            "inbox": "menu",
            "licensing": "menu",
            "coletiva": "pre_match",
            "conquistas": "menu",
            "premiacoes": "menu",
            "recordes": "menu",
            "estadio": "menu",
            "staff": "menu",
            "configs": "settings",
            "vestiario": "menu",
            "promessas": "menu",
            "quimica": "menu",
            "carreira": "menu",
            "analise": "menu",
            "objetivos": "menu",
            "desemprego": "menu",
            "rankings": "menu",
            "hallfame": "menu",
            "ffp": "menu",
            "world": "menu",
            "elenco": "squad",
            "mercado": "market",
            "partida": "pre_match",
        }
        return aliases.get(valor, valor or "menu")

    def _normalizar_contextos(self, contextos: Optional[Iterable[str]]) -> List[str]:
        if not contextos:
            return ["menu", "general"]
        saida = []
        for contexto in contextos:
            normalizado = self._normalizar_contexto(str(contexto))
            if normalizado not in saida:
                saida.append(normalizado)
        return saida or ["menu", "general"]

    def _faixa_por_arquivo(self, arquivo: str) -> Optional[Dict]:
        for faixa in self._catalogo:
            if faixa["arquivo"] == arquivo:
                return faixa
        return None

    def _faixa_valida_contexto(self, faixa: Dict, contexto: str, *, fallback: bool = False) -> bool:
        if self.streamer_safe and not faixa.get("streamer_safe", False):
            return False

        if contexto in _MENU_CONTEXTS and not self.musica_menu_ativa:
            return False
        if contexto == "pre_match" and not self.musica_pre_jogo_ativa:
            return False

        contextos = faixa.get("contextos", [])
        if fallback:
            return "general" in contextos or "menu" in contextos
        return contexto in contextos or "general" in contextos or "all" in contextos

    def _reconstruir_playlist(self, *, keep_current: bool = True) -> None:
        atual = ""
        if keep_current and self.playlist:
            atual = self.playlist[self.indice_atual % len(self.playlist)]

        contexto = self.contexto_atual
        filtradas = [
            faixa["arquivo"]
            for faixa in self._catalogo
            if self._faixa_valida_contexto(faixa, contexto)
        ]

        if not filtradas and contexto != "menu":
            filtradas = [
                faixa["arquivo"]
                for faixa in self._catalogo
                if self._faixa_valida_contexto(faixa, contexto, fallback=True)
            ]

        if self.shuffle and len(filtradas) > 1:
            random.shuffle(filtradas)

        self.playlist = filtradas
        if not self.playlist:
            self.indice_atual = 0
            self.tocando = False
            return

        if atual and atual in self.playlist:
            self.indice_atual = self.playlist.index(atual)
        else:
            self.indice_atual = 0

    def set_contexto(self, contexto: str) -> Optional[Dict]:
        self.contexto_atual = self._normalizar_contexto(contexto)
        self._reconstruir_playlist()
        return self.get_faixa_atual()

    def set_streamer_safe(self, ativo: bool) -> Optional[Dict]:
        self.streamer_safe = bool(ativo)
        self._reconstruir_playlist()
        return self.get_faixa_atual()

    def set_contexto_ativo(self, contexto: str, ativo: bool) -> Optional[Dict]:
        contexto = self._normalizar_contexto(contexto)
        if contexto in _MENU_CONTEXTS:
            self.musica_menu_ativa = bool(ativo)
        elif contexto == "pre_match":
            self.musica_pre_jogo_ativa = bool(ativo)
        self._reconstruir_playlist()
        return self.get_faixa_atual()

    def get_faixa_atual(self) -> Optional[Dict]:
        if not self.playlist:
            return None
        nome = self.playlist[self.indice_atual % len(self.playlist)]
        faixa = self._faixa_por_arquivo(nome)
        if not faixa:
            return None
        return {
            "arquivo": nome,
            "asset_path": faixa["asset_path"],
            "titulo": faixa["titulo"],
            "artista": faixa["artista"],
            "indice": self.indice_atual,
            "total": len(self.playlist),
            "tocando": self.tocando,
            "contexto": self.contexto_atual,
            "streamer_safe": faixa["streamer_safe"],
            "streamer_safe_mode": self.streamer_safe,
            "licenca": faixa["licenca"],
        }

    def get_faixa_b64(self, nome: str = "") -> Optional[str]:
        if not nome and self.playlist:
            nome = self.playlist[self.indice_atual % len(self.playlist)]
        faixa = self._faixa_por_arquivo(nome)
        if not faixa:
            return None
        caminho = faixa["caminho"]
        if not os.path.isfile(caminho):
            return None
        with open(caminho, "rb") as f:
            data = f.read()
        ext = os.path.splitext(nome)[1].lower()
        if ext == ".mp3":
            mime = "audio/mpeg"
        elif ext == ".ogg":
            mime = "audio/ogg"
        else:
            mime = "audio/wav"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    def proxima(self) -> Optional[Dict]:
        if not self.playlist:
            return None
        self.indice_atual = (self.indice_atual + 1) % len(self.playlist)
        return self.get_faixa_atual()

    def anterior(self) -> Optional[Dict]:
        if not self.playlist:
            return None
        self.indice_atual = (self.indice_atual - 1) % len(self.playlist)
        return self.get_faixa_atual()

    def tocar_faixa_por_indice(self, indice: int) -> Optional[Dict]:
        if not self.playlist:
            return None
        indice = max(0, min(indice, len(self.playlist) - 1))
        self.indice_atual = indice
        self.tocando = True
        return self.get_faixa_atual()

    def play_pause(self) -> bool:
        if not self.playlist:
            self.tocando = False
            return False
        self.tocando = not self.tocando
        return self.tocando

    def play(self) -> bool:
        if not self.playlist:
            self.tocando = False
            return False
        self.tocando = True
        return True

    def pause(self) -> bool:
        self.tocando = False
        return False

    def set_volume(self, tipo: str, valor: float) -> None:
        valor = max(0.0, min(1.0, valor))
        if tipo == "musica":
            self.volume_musica = valor
        elif tipo == "efeitos":
            self.volume_efeitos = valor
        elif tipo == "narracao":
            self.volume_narracao = valor

    def get_volume(self, tipo: str) -> float:
        if tipo == "musica":
            return self.volume_musica
        if tipo == "efeitos":
            return self.volume_efeitos
        if tipo == "narracao":
            return self.volume_narracao
        return 0.0

    def set_shuffle(self, ativo: bool) -> None:
        self.shuffle = bool(ativo)
        self._reconstruir_playlist()

    def set_narrador(self, nome: str) -> bool:
        if not nome:
            self.narrador_atual = "Luis Roberto"
            return True
        caminho = os.path.join(self._sons_dir, "narracoes", nome)
        if os.path.isdir(caminho):
            self.narrador_atual = nome
            return True
        caminho_legacy = os.path.join(self._sons_dir, "narrações", nome)
        if os.path.isdir(caminho_legacy):
            self.narrador_atual = nome
            return True
        return False

    def get_narradores(self) -> List[str]:
        candidatos = [
            os.path.join(self._sons_dir, "narracoes"),
            os.path.join(self._sons_dir, "narrações"),
        ]
        for caminho in candidatos:
            if os.path.isdir(caminho):
                return sorted(
                    d for d in os.listdir(caminho)
                    if os.path.isdir(os.path.join(caminho, d))
                )
        return []

    def get_som_b64(self, nome: str, narrador: str = "") -> Optional[str]:
        bases = []
        if narrador:
            bases.extend(
                [
                    os.path.join(self._sons_dir, "narracoes", narrador),
                    os.path.join(self._sons_dir, "narrações", narrador),
                ]
            )
        elif self.narrador_atual:
            bases.extend(
                [
                    os.path.join(self._sons_dir, "narracoes", self.narrador_atual),
                    os.path.join(self._sons_dir, "narrações", self.narrador_atual),
                ]
            )
        bases.append(self._sons_dir)

        caminho = ""
        for base in bases:
            candidato = os.path.join(base, nome)
            if os.path.isfile(candidato):
                caminho = candidato
                break
        if not caminho:
            return None
        with open(caminho, "rb") as f:
            data = f.read()
        return f"data:audio/wav;base64,{base64.b64encode(data).decode()}"

    def get_playlist_info(self) -> List[Dict]:
        faixas = []
        for arquivo in self.playlist:
            faixa = self._faixa_por_arquivo(arquivo)
            if not faixa:
                continue
            faixas.append(
                {
                    "arquivo": faixa["arquivo"],
                    "asset_path": faixa["asset_path"],
                    "titulo": faixa["titulo"],
                    "artista": faixa["artista"],
                    "contextos": list(faixa["contextos"]),
                    "streamer_safe": faixa["streamer_safe"],
                    "licenca": faixa["licenca"],
                }
            )
        return faixas

    def get_faixa_url(self) -> Optional[str]:
        faixa = self.get_faixa_atual()
        if not faixa:
            return None
        return faixa.get("asset_path")

    def to_save_dict(self) -> Dict:
        return {
            "vol_musica": self.volume_musica,
            "vol_efeitos": self.volume_efeitos,
            "vol_narracao": self.volume_narracao,
            "narrador": self.narrador_atual,
            "shuffle": self.shuffle,
            "contexto": self.contexto_atual,
            "streamer_safe_mode": self.streamer_safe,
            "menu_music_ativa": self.musica_menu_ativa,
            "pre_match_music_ativa": self.musica_pre_jogo_ativa,
        }

    def from_save_dict(self, data: Dict) -> None:
        self.volume_musica = data.get("vol_musica", 0.5)
        self.volume_efeitos = data.get("vol_efeitos", 0.8)
        self.volume_narracao = data.get("vol_narracao", 0.7)
        self.narrador_atual = data.get("narrador", "Luis Roberto")
        self.shuffle = data.get("shuffle", True)
        self.contexto_atual = self._normalizar_contexto(data.get("contexto", "menu"))
        self.streamer_safe = data.get("streamer_safe_mode", False)
        self.musica_menu_ativa = data.get("menu_music_ativa", True)
        self.musica_pre_jogo_ativa = data.get("pre_match_music_ativa", True)
        self._reconstruir_playlist(keep_current=False)
