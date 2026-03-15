# -*- coding: utf-8 -*-
"""Tela Finanças — demonstrativo financeiro, folha salarial, receitas."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS
from utils.helpers import format_reais

if TYPE_CHECKING:
    from ui.app import App


class TelaFinancas(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="💵 Finanças",
                      font=FONTS["title"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(0, 15))

        # Cards financeiros
        self._cards = ctk.CTkFrame(scroll, fg_color="transparent")
        self._cards.pack(fill="x", pady=10)

        # Detalhamento
        self._detalhe = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"], corner_radius=8)
        self._detalhe.pack(fill="x", pady=10)

        self._detalhe_lbl = ctk.CTkLabel(self._detalhe, text="",
                                          font=FONTS["mono"],
                                          text_color=COLORS["text"],
                                          justify="left")
        self._detalhe_lbl.pack(padx=15, pady=15, anchor="w")

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None or gm.time_jogador is None:
            return

        t = gm.time_jogador
        fin = t.financas

        # Limpar cards
        for w in self._cards.winfo_children():
            w.destroy()

        dados = [
            ("Saldo", format_reais(fin.saldo),
             COLORS["success"] if fin.saldo >= 0 else COLORS["danger"]),
            ("Folha Salarial", format_reais(t.folha_salarial), COLORS["warning"]),
            ("Orçamento Transf.", format_reais(fin.orcamento_transferencias), COLORS["text"]),
            ("Sócios", f"{fin.num_socios:,}", COLORS["text"]),
        ]

        for i, (label, valor, cor) in enumerate(dados):
            card = ctk.CTkFrame(self._cards, fg_color=COLORS["bg_card"],
                                 corner_radius=8, width=180, height=80)
            card.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
            card.grid_propagate(False)
            self._cards.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(card, text=label, font=FONTS["small"],
                          text_color=COLORS["text_muted"]).pack(pady=(12, 2))
            ctk.CTkLabel(card, text=valor, font=FONTS["subheading"],
                          text_color=cor).pack()

        # Detalhamento
        rec_total = (fin.receita_patrocinio_mensal + fin.receita_tv_mensal
                     + fin.receita_socios_mensal)

        info = (
            f"{'═' * 40}\n"
            f" RECEITAS MENSAIS\n"
            f"{'─' * 40}\n"
            f"  Patrocínio:   {format_reais(fin.receita_patrocinio_mensal)}\n"
            f"  TV:           {format_reais(fin.receita_tv_mensal)}\n"
            f"  Sócios:       {format_reais(fin.receita_socios_mensal)}\n"
            f"  TOTAL:        {format_reais(rec_total)}\n"
            f"\n"
            f" DESPESAS MENSAIS\n"
            f"{'─' * 40}\n"
            f"  Folha salarial: {format_reais(t.folha_salarial)}\n"
            f"  Estádio:        {format_reais(t.estadio.custo_manutencao)}\n"
            f"  Base juvenil:   {format_reais(t.base_juvenil.investimento_mensal)}\n"
            f"\n"
            f" ESTÁDIO: {t.estadio.nome}\n"
            f"  Capacidade: {t.estadio.capacidade:,}\n"
            f"  Gramado: {t.estadio.nivel_gramado}/99\n"
            f"  Ingresso: {format_reais(t.estadio.preco_ingresso)}\n"
            f"{'═' * 40}"
        )
        self._detalhe_lbl.configure(text=info)
