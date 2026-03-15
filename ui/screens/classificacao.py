# -*- coding: utf-8 -*-
"""Tela Classificação — tabela do campeonato, copa, libertadores."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from ui.app import App


class TelaClassificacao(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="🏆 Classificação",
                      font=FONTS["title"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(0, 15))

        # Abas
        self._tab = ctk.CTkTabview(scroll, fg_color=COLORS["bg_card"],
                                    segmented_button_fg_color=COLORS["bg_input"],
                                    segmented_button_selected_color=COLORS["accent"])
        self._tab.pack(fill="both", expand=True, pady=5)

        self._tab.add("Série A")
        self._tab.add("Série B")
        self._tab.add("Copa do Brasil")
        self._tab.add("Libertadores")
        self._tab.add("⚽ Artilharia")

        # Frames de conteúdo
        self._frame_a = self._tab.tab("Série A")
        self._frame_b = self._tab.tab("Série B")
        self._frame_copa = self._tab.tab("Copa do Brasil")
        self._frame_liberta = self._tab.tab("Libertadores")
        self._frame_artilharia = self._tab.tab("⚽ Artilharia")

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None:
            return

        comp = gm.competicoes
        if comp is None:
            return

        # Série A
        self._preencher_tabela(self._frame_a, comp.brasileirao_a)
        # Série B
        self._preencher_tabela(self._frame_b, comp.brasileirao_b)
        # Copa
        self._preencher_copa(self._frame_copa, comp.copa_brasil)
        # Libertadores
        self._preencher_copa(self._frame_liberta, comp.libertadores)
        # Artilharia
        self._preencher_artilharia(self._frame_artilharia, gm)

    def _preencher_tabela(self, frame, campeonato) -> None:
        for w in frame.winfo_children():
            w.destroy()

        if campeonato is None:
            ctk.CTkLabel(frame, text="Competição não iniciada",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        classificacao = campeonato.classificacao()

        # Cabeçalho
        header = ctk.CTkFrame(frame, fg_color=COLORS["bg_input"], corner_radius=0)
        header.pack(fill="x")

        cols = ["#", "Time", "P", "J", "V", "E", "D", "GM", "GS", "SG"]
        widths = [30, 180, 35, 35, 35, 35, 35, 35, 35, 35]
        for col, w in zip(cols, widths):
            ctk.CTkLabel(header, text=col, font=FONTS["small_bold"],
                          text_color=COLORS["text"], width=w
                          ).pack(side="left", padx=2, pady=4)

        for i, time in enumerate(classificacao, 1):
            row_color = COLORS["bg_card"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(frame, fg_color=row_color, corner_radius=0)
            row.pack(fill="x")

            # Destaque para o time do jogador
            gm = self.app.game
            is_jogador = gm and gm.time_jogador and time.nome == gm.time_jogador.nome
            txt_color = COLORS["accent"] if is_jogador else COLORS["text"]

            jogos = time.vitorias + time.empates + time.derrotas
            valores = [
                str(i), time.nome_curto,
                str(time.pontos), str(jogos),
                str(time.vitorias), str(time.empates), str(time.derrotas),
                str(time.gols_marcados), str(time.gols_sofridos),
                str(time.saldo_gols),
            ]

            for val, w in zip(valores, widths):
                ctk.CTkLabel(row, text=val, font=FONTS["mono_small"],
                              text_color=txt_color, width=w
                              ).pack(side="left", padx=2, pady=2)

    def _preencher_copa(self, frame, copa) -> None:
        for w in frame.winfo_children():
            w.destroy()

        if copa is None:
            ctk.CTkLabel(frame, text="Competição não iniciada",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        fase_nome = copa.fase_nome
        ctk.CTkLabel(frame, text=f"Fase atual: {fase_nome}",
                      font=FONTS["subheading"], text_color=COLORS["text"]
                      ).pack(anchor="w", padx=10, pady=(10, 5))

        if copa.encerrado and copa.campeao:
            ctk.CTkLabel(frame, text=f"🏆 Campeão: {copa.campeao.nome}",
                          font=FONTS["heading"], text_color=COLORS["gold"]
                          ).pack(anchor="w", padx=10, pady=5)
            return

        confrontos = copa.confrontos[copa.fase_atual] if copa.fase_atual < len(copa.confrontos) else []
        if not confrontos:
            ctk.CTkLabel(frame, text="Sem confrontos nesta fase.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=5)
            return

        for t1, t2 in confrontos:
            nome1 = t1.nome if t1 else "BYE"
            nome2 = t2.nome if t2 else "BYE"
            ctk.CTkLabel(frame, text=f"  {nome1}  vs  {nome2}",
                          font=FONTS["mono"], text_color=COLORS["text"],
                          ).pack(anchor="w", padx=15, pady=1)

    def _preencher_artilharia(self, frame, gm) -> None:
        for w in frame.winfo_children():
            w.destroy()

        if not gm.save_id:
            ctk.CTkLabel(frame, text="Salve o jogo primeiro para registrar artilharia.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        artilheiros = gm.repo.artilharia(gm.save_id, gm.temporada, limite=25)
        if not artilheiros:
            ctk.CTkLabel(frame, text="Nenhum gol registrado ainda nesta temporada.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        # Cabeçalho
        header = ctk.CTkFrame(frame, fg_color=COLORS["bg_input"], corner_radius=0)
        header.pack(fill="x")

        cols = ["#", "Jogador", "Time", "Gols", "Assist."]
        widths = [30, 200, 150, 50, 50]
        for col, w in zip(cols, widths):
            ctk.CTkLabel(header, text=col, font=FONTS["small_bold"],
                          text_color=COLORS["text"], width=w
                          ).pack(side="left", padx=2, pady=4)

        for i, art in enumerate(artilheiros, 1):
            row_color = COLORS["bg_card"] if i % 2 == 0 else "transparent"
            row = ctk.CTkFrame(frame, fg_color=row_color, corner_radius=0)
            row.pack(fill="x")

            # Destaque para jogadores do time do jogador
            is_jogador = gm.time_jogador and art.get("time_nome") == gm.time_jogador.nome
            txt_color = COLORS["accent"] if is_jogador else COLORS["text"]

            valores = [
                str(i),
                str(art.get("jogador_nome", "")),
                str(art.get("time_nome", "")),
                str(art.get("gols", 0)),
                str(art.get("assistencias", 0)),
            ]

            for val, w in zip(valores, widths):
                ctk.CTkLabel(row, text=val, font=FONTS["mono_small"],
                              text_color=txt_color, width=w
                              ).pack(side="left", padx=2, pady=2)
