# -*- coding: utf-8 -*-
"""
App — Janela principal do Ultrafoot (CustomTkinter).
Gerencia sidebar, navegação de telas e loop de jogo.
"""
from __future__ import annotations

import customtkinter as ctk
from typing import Dict, Optional, Type

from config import WINDOW_WIDTH, WINDOW_HEIGHT, GAME_TITLE, GAME_VERSION
from ui.theme import COLORS, FONTS, SIDEBAR_WIDTH
from managers.game_manager import GameManager
from utils.logger import get_logger

logger = get_logger(__name__)


class App(ctk.CTk):
    """Janela raiz do aplicativo."""

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{GAME_TITLE} v{GAME_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(1024, 600)
        self.configure(fg_color=COLORS["bg_dark"])

        self.game: Optional[GameManager] = None
        self._screens: Dict[str, ctk.CTkFrame] = {}
        self._current: Optional[str] = None

        # Layout raiz
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self._sidebar = _Sidebar(self, command=self._navegar)
        self._sidebar.grid(row=0, column=0, sticky="ns")

        # Container de telas
        self._container = ctk.CTkFrame(self, fg_color=COLORS["bg_dark"], corner_radius=0)
        self._container.grid(row=0, column=1, sticky="nsew")
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        # Registrar telas (lazy import)
        self._registrar_telas()

        # Mostrar tela inicial
        self._navegar("inicio")

    # ── Registro de telas ─────────────────────────────────────

    def _registrar_telas(self) -> None:
        from ui.screens.inicio import TelaInicio
        from ui.screens.dashboard import TelaDashboard
        from ui.screens.elenco import TelaElenco
        from ui.screens.tatica import TelaTatica
        from ui.screens.partida import TelaPartida
        from ui.screens.mercado import TelaMercado
        from ui.screens.classificacao import TelaClassificacao
        from ui.screens.financas import TelaFinancas
        from ui.screens.fantasy import TelaFantasy

        telas: Dict[str, Type[ctk.CTkFrame]] = {
            "inicio": TelaInicio,
            "dashboard": TelaDashboard,
            "elenco": TelaElenco,
            "tatica": TelaTatica,
            "partida": TelaPartida,
            "mercado": TelaMercado,
            "classificacao": TelaClassificacao,
            "financas": TelaFinancas,
            "fantasy": TelaFantasy,
        }

        for nome, cls in telas.items():
            frame = cls(self._container, app=self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._screens[nome] = frame

    # ── Navegação ─────────────────────────────────────────────

    def _navegar(self, tela: str) -> None:
        if tela not in self._screens:
            return
        self._current = tela
        frame = self._screens[tela]
        if hasattr(frame, "ao_exibir"):
            frame.ao_exibir()
        frame.tkraise()
        self._sidebar.set_ativo(tela)

    # ── Ações de jogo ─────────────────────────────────────────

    def novo_jogo(self, nome_time: str) -> None:
        self.game = GameManager()
        self.game.novo_jogo(nome_time)
        logger.info("Novo jogo iniciado — time: %s", nome_time)
        self._navegar("dashboard")

    def carregar_jogo(self, nome_save: str) -> bool:
        self.game = GameManager()
        ok = self.game.carregar(nome_save)
        if ok:
            logger.info("Jogo carregado: %s", nome_save)
            self._navegar("dashboard")
        return ok

    def salvar_jogo(self, nome_save: str) -> bool:
        if self.game is None:
            return False
        return self.game.salvar(nome_save)

    def avancar_semana(self) -> dict:
        if self.game is None:
            return {}
        resultado = self.game.avancar_semana()
        return resultado

    def mostrar_toast(self, mensagem: str, tipo: str = "info") -> None:
        """Exibe notificação temporária no topo da tela."""
        cores = {
            "info": COLORS["accent"],
            "success": COLORS["success"],
            "warning": COLORS["warning"],
            "error": COLORS["danger"],
        }
        cor = cores.get(tipo, COLORS["accent"])
        toast = ctk.CTkFrame(self._container, fg_color=cor, corner_radius=8, height=40)
        toast.place(relx=0.5, rely=0.02, anchor="n")
        lbl = ctk.CTkLabel(toast, text=f"  {mensagem}  ", font=FONTS["body_bold"],
                            text_color="#ffffff")
        lbl.pack(padx=15, pady=8)
        self.after(2500, toast.destroy)


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════

_MENU_ITEMS = [
    ("inicio", "🏠", "Início"),
    ("dashboard", "📊", "Painel"),
    ("elenco", "👥", "Elenco"),
    ("tatica", "📋", "Tática"),
    ("partida", "⚽", "Partida"),
    ("mercado", "💰", "Mercado"),
    ("classificacao", "🏆", "Classificação"),
    ("financas", "💵", "Finanças"),
    ("fantasy", "🌟", "Fantasy"),
]


class _Sidebar(ctk.CTkFrame):
    """Barra lateral de navegação."""

    def __init__(self, master: App, command) -> None:
        super().__init__(master, width=SIDEBAR_WIDTH, corner_radius=0,
                         fg_color=COLORS["bg_sidebar"])
        self.grid_propagate(False)
        self._command = command
        self._buttons: Dict[str, ctk.CTkButton] = {}

        # Logo / título
        logo = ctk.CTkLabel(
            self, text="⚽ BRASFOOT", font=FONTS["heading"],
            text_color=COLORS["accent"],
        )
        logo.pack(pady=(20, 5))

        subtitle = ctk.CTkLabel(
            self, text="Ultimate", font=FONTS["small"],
            text_color=COLORS["text_secondary"],
        )
        subtitle.pack(pady=(0, 20))

        sep = ctk.CTkFrame(self, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=15, pady=5)

        for key, icon, label in _MENU_ITEMS:
            btn = ctk.CTkButton(
                self, text=f" {icon}  {label}", anchor="w",
                font=FONTS["body"], height=38,
                fg_color="transparent",
                text_color=COLORS["text_secondary"],
                hover_color=COLORS["bg_hover"],
                corner_radius=6,
                command=lambda k=key: self._command(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._buttons[key] = btn

        # Versão no rodapé
        self.pack_propagate(False)
        ver = ctk.CTkLabel(
            self, text=f"v{GAME_VERSION}",
            font=FONTS["mono_small"], text_color=COLORS["text_muted"],
        )
        ver.pack(side="bottom", pady=10)

    def set_ativo(self, key: str) -> None:
        for k, btn in self._buttons.items():
            if k == key:
                btn.configure(fg_color=COLORS["bg_active"],
                              text_color=COLORS["text"])
            else:
                btn.configure(fg_color="transparent",
                              text_color=COLORS["text_secondary"])
