# -*- coding: utf-8 -*-
"""Tela Partida — visualização do último resultado e eventos."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from ui.app import App


class TelaPartida(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        self._titulo = ctk.CTkLabel(scroll, text="⚽ Partida",
                                     font=FONTS["title"],
                                     text_color=COLORS["text"])
        self._titulo.pack(anchor="w", pady=(0, 15))

        # Tabs
        self._tab = ctk.CTkTabview(scroll, fg_color=COLORS["bg_card"],
                                    segmented_button_fg_color=COLORS["bg_input"],
                                    segmented_button_selected_color=COLORS["accent"])
        self._tab.pack(fill="both", expand=True, pady=5)
        self._tab.add("Última Partida")
        self._tab.add("📋 Histórico")

        ultima = self._tab.tab("Última Partida")

        # Card placar
        self._placar_frame = ctk.CTkFrame(ultima, fg_color=COLORS["bg_card"],
                                           corner_radius=10, height=120)
        self._placar_frame.pack(fill="x", pady=10)

        self._placar_lbl = ctk.CTkLabel(self._placar_frame, text="Nenhum jogo realizado",
                                         font=("Segoe UI", 28, "bold"),
                                         text_color=COLORS["text"])
        self._placar_lbl.pack(pady=20)

        # Estatísticas
        self._stats_frame = ctk.CTkFrame(ultima, fg_color=COLORS["bg_card"],
                                          corner_radius=8)
        self._stats_frame.pack(fill="x", pady=10)

        self._stats_lbl = ctk.CTkLabel(self._stats_frame, text="",
                                        font=FONTS["mono"], text_color=COLORS["text"],
                                        justify="left")
        self._stats_lbl.pack(padx=15, pady=15, anchor="w")

        # Eventos (lance-a-lance)
        ctk.CTkLabel(ultima, text="📜 Eventos", font=FONTS["heading"],
                      text_color=COLORS["text"]).pack(anchor="w", pady=(15, 5))

        self._eventos_frame = ctk.CTkFrame(ultima, fg_color=COLORS["bg_card"],
                                            corner_radius=8)
        self._eventos_frame.pack(fill="x", pady=5)

        # Histórico
        self._historico_frame = self._tab.tab("📋 Histórico")

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None:
            return

        resultados = gm.ultimo_resultado
        if not resultados:
            self._placar_lbl.configure(text="Nenhum jogo realizado ainda")
            return

        # Encontrar o jogo do time do jogador nos resultados
        rp = None
        if gm.time_jogador:
            nome = gm.time_jogador.nome
            for comp_resultados in resultados.values():
                for r in comp_resultados:
                    if r.time_casa == nome or r.time_fora == nome:
                        rp = r
                        break
                if rp:
                    break

        if rp is None:
            self._placar_lbl.configure(text="Seu time não jogou nesta rodada")
            return

        self._placar_lbl.configure(text=f"{rp.time_casa}  {rp.gols_casa} x {rp.gols_fora}  {rp.time_fora}")

        stats = (
            f"{'Posse de bola:':<25} {rp.posse_casa:.0f}% x {100 - rp.posse_casa:.0f}%\n"
            f"{'Finalizações:':<25} {rp.finalizacoes_casa:>3} x {rp.finalizacoes_fora:<3}\n"
            f"{'Finalizações no gol:':<25} {rp.finalizacoes_gol_casa:>3} x {rp.finalizacoes_gol_fora:<3}\n"
            f"{'Escanteios:':<25} {rp.escanteios_casa:>3} x {rp.escanteios_fora:<3}\n"
            f"{'Faltas:':<25} {rp.faltas_casa:>3} x {rp.faltas_fora:<3}\n"
            f"{'Impedimentos:':<25} {rp.impedimentos_casa:>3} x {rp.impedimentos_fora:<3}\n"
            f"{'Público:':<25} {rp.publico:,}\n"
            f"{'Renda:':<25} R$ {rp.renda:,.0f}"
        )
        self._stats_lbl.configure(text=stats)

        # Eventos
        for w in self._eventos_frame.winfo_children():
            w.destroy()

        for ev in rp.eventos:
            icone = {"gol": "⚽", "cartao_amarelo": "🟡",
                     "cartao_vermelho": "🔴", "substituicao": "🔄",
                     "defesa_dificil": "🧤"}.get(ev.tipo, "▶")
            txt = f" {ev.minuto}' {icone} [{ev.time}] {ev.jogador_nome} — {ev.detalhe}"
            ctk.CTkLabel(self._eventos_frame, text=txt,
                          font=FONTS["mono_small"],
                          text_color=COLORS["text_secondary"],
                          anchor="w").pack(fill="x", padx=10, pady=1)

        # Histórico de partidas
        self._preencher_historico(gm)

    def _preencher_historico(self, gm) -> None:
        frame = self._historico_frame
        for w in frame.winfo_children():
            w.destroy()

        if not gm.save_id:
            ctk.CTkLabel(frame, text="Salve o jogo para registrar histórico de partidas.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        partidas = gm.repo.listar_partidas(gm.save_id, gm.temporada)
        if not partidas:
            ctk.CTkLabel(frame, text="Nenhuma partida registrada nesta temporada.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        # Cabeçalho
        header = ctk.CTkFrame(frame, fg_color=COLORS["bg_input"], corner_radius=0)
        header.pack(fill="x")

        cols = ["Sem", "Competição", "Casa", "Placar", "Fora", "Públ."]
        widths = [35, 160, 120, 60, 120, 60]
        for col, w in zip(cols, widths):
            ctk.CTkLabel(header, text=col, font=FONTS["small_bold"],
                          text_color=COLORS["text"], width=w
                          ).pack(side="left", padx=2, pady=4)

        nome_jog = gm.time_jogador.nome if gm.time_jogador else ""
        for p in reversed(partidas):
            row_color = COLORS["bg_card"]
            row = ctk.CTkFrame(frame, fg_color=row_color, corner_radius=0)
            row.pack(fill="x")

            envolvido = p.get("time_casa") == nome_jog or p.get("time_fora") == nome_jog
            txt_color = COLORS["accent"] if envolvido else COLORS["text"]

            placar = f"{p.get('gols_casa', 0)} x {p.get('gols_fora', 0)}"
            valores = [
                str(p.get("semana", "")),
                str(p.get("competicao", ""))[:22],
                str(p.get("time_casa", "")),
                placar,
                str(p.get("time_fora", "")),
                f"{p.get('publico', 0):,}" if p.get("publico") else "-",
            ]

            for val, w in zip(valores, widths):
                ctk.CTkLabel(row, text=val, font=FONTS["mono_small"],
                              text_color=txt_color, width=w
                              ).pack(side="left", padx=2, pady=2)
