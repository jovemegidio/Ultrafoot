# -*- coding: utf-8 -*-
"""Tela Fantasy — liga fantasy, escalação, classificação."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from ui.app import App


class TelaFantasy(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="🌟 Fantasy League",
                      font=FONTS["title"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(0, 15))

        # Meu time fantasy
        ctk.CTkLabel(scroll, text="Meu Time", font=FONTS["heading"],
                      text_color=COLORS["text"]).pack(anchor="w", pady=(10, 5))

        self._meu_time_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"],
                                              corner_radius=8)
        self._meu_time_frame.pack(fill="x", pady=5)

        self._meu_pts_lbl = ctk.CTkLabel(self._meu_time_frame, text="Pts: 0",
                                          font=FONTS["heading"],
                                          text_color=COLORS["gold"])
        self._meu_pts_lbl.pack(padx=15, pady=10)

        self._meu_escalacao_frame = ctk.CTkFrame(self._meu_time_frame,
                                                   fg_color="transparent")
        self._meu_escalacao_frame.pack(fill="x", padx=10, pady=(0, 10))

        sep = ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", pady=15)

        # Classificação fantasy
        ctk.CTkLabel(scroll, text="🏅 Classificação Fantasy",
                      font=FONTS["heading"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(5, 5))

        self._ranking_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"],
                                            corner_radius=8)
        self._ranking_frame.pack(fill="x", pady=5)

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None:
            return

        fm = getattr(gm, "fantasy", None)
        if fm is None:
            self._meu_pts_lbl.configure(text="Fantasy não inicializado")
            return

        # Meu time
        meu = fm.time_jogador()
        if meu:
            self._meu_pts_lbl.configure(
                text=f"Total: {meu.pontos_total:.1f} pts | Última rodada: {meu.pontos_rodada:.1f} pts"
            )
            for w in self._meu_escalacao_frame.winfo_children():
                w.destroy()
            for esc in meu.escalacao:
                cap = " (C)" if esc.capitao else ""
                txt = f"  {esc.jogador_nome} ({esc.posicao}) — {esc.time_real}{cap}  [{esc.pontos:.1f} pts]"
                ctk.CTkLabel(self._meu_escalacao_frame, text=txt,
                              font=FONTS["mono_small"],
                              text_color=COLORS["text_secondary"],
                              anchor="w").pack(fill="x", pady=1)

        # Ranking
        for w in self._ranking_frame.winfo_children():
            w.destroy()

        ranking = fm.classificacao()
        for i, tf in enumerate(ranking, 1):
            cor = {1: COLORS["gold"], 2: COLORS["silver"],
                   3: COLORS["bronze"]}.get(i, COLORS["text"])

            marcador = " ★" if tf.dono == "jogador" else ""
            txt = f" {i:>2}. {tf.nome:<20} {tf.pontos_total:>8.1f} pts{marcador}"
            ctk.CTkLabel(self._ranking_frame, text=txt,
                          font=FONTS["mono"], text_color=cor,
                          anchor="w").pack(fill="x", padx=10, pady=2)
