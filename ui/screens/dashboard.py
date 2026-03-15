# -*- coding: utf-8 -*-
"""Tela Dashboard — visão geral do time, próximo jogo, notícias."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS
from utils.helpers import format_reais

if TYPE_CHECKING:
    from ui.app import App


class TelaDashboard(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        self._scroll.pack(fill="both", expand=True, padx=20, pady=20)

        self._titulo = ctk.CTkLabel(self._scroll, text="Painel do Time",
                                     font=FONTS["title"], text_color=COLORS["text"])
        self._titulo.pack(anchor="w", pady=(0, 15))

        # Linha de cards
        self._cards_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._cards_frame.pack(fill="x", pady=5)

        # Botão avançar semana
        self._btn_avancar = ctk.CTkButton(
            self._scroll, text="⏩  Avançar Semana",
            font=FONTS["body_bold"],
            fg_color=COLORS["success"], hover_color="#2ea043",
            height=44, width=220, corner_radius=8,
            command=self._avancar,
        )
        self._btn_avancar.pack(pady=15)

        # Botão salvar
        self._btn_salvar = ctk.CTkButton(
            self._scroll, text="💾  Salvar Jogo",
            font=FONTS["body"], fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_hover"],
            height=36, width=160, corner_radius=6,
            command=self._salvar,
        )
        self._btn_salvar.pack(pady=5)

        # Info
        self._info = ctk.CTkLabel(self._scroll, text="", font=FONTS["body"],
                                   text_color=COLORS["text_secondary"],
                                   wraplength=700, justify="left")
        self._info.pack(anchor="w", pady=10)

        # Notícias
        self._noticias_lbl = ctk.CTkLabel(self._scroll, text="📰 Notícias",
                                           font=FONTS["heading"],
                                           text_color=COLORS["text"])
        self._noticias_lbl.pack(anchor="w", pady=(15, 5))

        self._noticias_frame = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_card"],
                                             corner_radius=8)
        self._noticias_frame.pack(fill="x", pady=5)

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None:
            return

        t = gm.time_jogador
        if t is None:
            return

        self._titulo.configure(text=f"📊 {t.nome}")

        # Limpar e recriar cards
        for w in self._cards_frame.winfo_children():
            w.destroy()

        cards = [
            ("Temporada", str(gm.temporada)),
            ("Semana", f"{gm.semana}/48"),
            ("Saldo", format_reais(t.financas.saldo)),
            ("Elenco", f"{len(t.jogadores)} jogadores"),
            ("Overall", f"{t.overall_medio}"),
            ("V/E/D", f"{t.vitorias}/{t.empates}/{t.derrotas}"),
        ]

        for i, (label, valor) in enumerate(cards):
            card = ctk.CTkFrame(self._cards_frame, fg_color=COLORS["bg_card"],
                                 corner_radius=8, width=140, height=80)
            card.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            card.grid_propagate(False)
            self._cards_frame.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(card, text=label, font=FONTS["small"],
                          text_color=COLORS["text_muted"]).pack(pady=(10, 2))
            ctk.CTkLabel(card, text=valor, font=FONTS["heading"],
                          text_color=COLORS["text"]).pack()

        # Notícias recentes
        for w in self._noticias_frame.winfo_children():
            w.destroy()

        noticias = list(reversed(gm.noticias[-8:]))
        if not noticias:
            ctk.CTkLabel(self._noticias_frame, text="Nenhuma notícia ainda.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
        else:
            for n in noticias:
                txt = f"[Rod {n.rodada}] {n.titulo}"
                ctk.CTkLabel(self._noticias_frame, text=txt, font=FONTS["small"],
                              text_color=COLORS["text_secondary"],
                              anchor="w").pack(fill="x", padx=10, pady=2)

    def _avancar(self) -> None:
        self._btn_avancar.configure(state="disabled", text="⏳ Processando...")
        self.update_idletasks()
        resultados = self.app.avancar_semana()
        self._btn_avancar.configure(state="normal", text="⏩  Avançar Semana")
        info_parts = []
        if resultados and self.app.game and self.app.game.time_jogador:
            nome = self.app.game.time_jogador.nome
            for comp, lista in resultados.items():
                for rp in lista:
                    if rp.time_casa == nome or rp.time_fora == nome:
                        info_parts.append(f"⚽ {rp.placar}")
                        break
        if self.app.game:
            info_parts.append(f"Semana {self.app.game.semana} / Temporada {self.app.game.temporada}")
        self._info.configure(text="\n".join(info_parts))
        self.ao_exibir()

    def _salvar(self) -> None:
        if self.app.game and self.app.game.time_jogador:
            nome = self.app.game.time_jogador.nome
            ok = self.app.salvar_jogo(nome)
            if ok:
                self.app.mostrar_toast("Jogo salvo com sucesso!", "success")
            else:
                self.app.mostrar_toast("Erro ao salvar o jogo.", "error")
