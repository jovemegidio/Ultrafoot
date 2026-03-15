# -*- coding: utf-8 -*-
"""Tela Início — novo jogo / carregar / sobre."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from ui.app import App


class TelaInicio(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        # Container central
        center = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        center.place(relx=0.5, rely=0.5, anchor="center")

        titulo = ctk.CTkLabel(center, text="⚽ ULTRAFOOT",
                               font=FONTS["title"], text_color=COLORS["accent"])
        titulo.pack(pady=(40, 5))

        sub = ctk.CTkLabel(center, text="Simulador de Futebol Brasileiro",
                            font=FONTS["body"], text_color=COLORS["text_secondary"])
        sub.pack(pady=(0, 30))

        # Novo jogo
        lbl = ctk.CTkLabel(center, text="Escolha seu time:", font=FONTS["subheading"],
                            text_color=COLORS["text"])
        lbl.pack(pady=(10, 5))

        self._combo_time = ctk.CTkComboBox(
            center, width=300, font=FONTS["body"],
            values=self._listar_times(),
            state="readonly",
        )
        self._combo_time.pack(pady=5)
        if self._combo_time.cget("values"):
            self._combo_time.set(self._combo_time.cget("values")[0])

        btn_novo = ctk.CTkButton(
            center, text="🆕  Novo Jogo", font=FONTS["body_bold"],
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            height=40, width=300, corner_radius=8,
            command=self._novo_jogo,
        )
        btn_novo.pack(pady=(15, 10))

        sep = ctk.CTkFrame(center, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", padx=40, pady=15)

        # Carregar
        lbl2 = ctk.CTkLabel(center, text="Ou carregar jogo salvo:",
                              font=FONTS["subheading"], text_color=COLORS["text"])
        lbl2.pack(pady=(5, 5))

        self._combo_save = ctk.CTkComboBox(
            center, width=300, font=FONTS["body"],
            values=self._listar_saves(),
            state="readonly",
        )
        self._combo_save.pack(pady=5)

        btn_carregar = ctk.CTkButton(
            center, text="📂  Carregar", font=FONTS["body_bold"],
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_hover"],
            height=40, width=300, corner_radius=8,
            command=self._carregar_jogo,
        )
        btn_carregar.pack(pady=(10, 20))

        # Rodapé
        versao = ctk.CTkLabel(center, text="v2.0.0 — Temporada 2026",
                                font=FONTS["mono_small"],
                                text_color=COLORS["text_muted"])
        versao.pack(pady=(5, 20))

    def ao_exibir(self) -> None:
        self._combo_save.configure(values=self._listar_saves())
        self._combo_time.configure(values=self._listar_times())

    def _listar_times(self) -> list[str]:
        try:
            import json, os
            path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "seeds", "teams_br.json")
            path = os.path.normpath(path)
            with open(path, encoding="utf-8") as f:
                dados = json.load(f)
            nomes = [t["nome"] for t in dados.get("serie_a", [])]
            nomes += [t["nome"] for t in dados.get("serie_b", [])]
            return nomes
        except Exception:
            return ["Flamengo", "Palmeiras", "Corinthians"]

    def _listar_saves(self) -> list[str]:
        try:
            from database import create_database_manager
            from database.repository import SaveRepository
            db = create_database_manager()
            repo = SaveRepository(db)
            saves = repo.listar_saves()
            return [s["nome"] for s in saves] if saves else ["(nenhum)"]
        except Exception:
            return ["(nenhum)"]

    def _novo_jogo(self) -> None:
        nome = self._combo_time.get()
        if nome:
            self.app.novo_jogo(nome)
            self.app.mostrar_toast(f"Novo jogo criado com {nome}!", "success")

    def _carregar_jogo(self) -> None:
        nome = self._combo_save.get()
        if nome and nome != "(nenhum)":
            ok = self.app.carregar_jogo(nome)
            if ok:
                self.app.mostrar_toast(f"Jogo carregado: {nome}", "success")
            else:
                self.app.mostrar_toast("Erro ao carregar o jogo.", "error")
