# -*- coding: utf-8 -*-
"""Tela Mercado de Transferências — buscar, comprar, vender, ofertas."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS
from ui.widgets.data_table import DataTable
from utils.helpers import format_reais
from core.enums import StatusOferta

if TYPE_CHECKING:
    from ui.app import App


class TelaMercado(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="💰 Mercado de Transferências",
                      font=FONTS["title"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(0, 15))

        # Ofertas recebidas
        ctk.CTkLabel(scroll, text="📩 Ofertas Recebidas",
                      font=FONTS["heading"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(10, 5))

        self._ofertas_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"],
                                            corner_radius=8)
        self._ofertas_frame.pack(fill="x", pady=5)

        sep = ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", pady=15)

        # Jogadores livres
        ctk.CTkLabel(scroll, text="🆓 Jogadores Livres",
                      font=FONTS["heading"], text_color=COLORS["text"]
                      ).pack(anchor="w", pady=(5, 5))

        colunas = ["Nome", "Pos", "Idade", "OVR", "Valor"]
        self._tabela_livres = DataTable(scroll, colunas=colunas,
                                         on_select=self._selecionar_livre)
        self._tabela_livres.pack(fill="x", pady=5)

        # Botão contratar
        self._btn_contratar = ctk.CTkButton(
            scroll, text="✅  Contratar Selecionado",
            font=FONTS["body_bold"], fg_color=COLORS["success"],
            hover_color="#2ea043", height=38, width=200,
            corner_radius=6, command=self._contratar,
        )
        self._btn_contratar.pack(pady=10)

        self._status = ctk.CTkLabel(scroll, text="", font=FONTS["small"],
                                     text_color=COLORS["text_secondary"])
        self._status.pack()

        self._livre_selecionado = None

    def ao_exibir(self) -> None:
        self._atualizar_ofertas()
        self._atualizar_livres()

    def _atualizar_ofertas(self) -> None:
        for w in self._ofertas_frame.winfo_children():
            w.destroy()

        gm = self.app.game
        if gm is None:
            return

        motor = gm.mercado
        if motor is None:
            return

        ofertas = [o for o in motor.ofertas_pendentes
                   if o.time_destino == (gm.time_jogador.nome if gm.time_jogador else "")]

        if not ofertas:
            ctk.CTkLabel(self._ofertas_frame, text="Nenhuma oferta pendente.",
                          font=FONTS["small"], text_color=COLORS["text_muted"]
                          ).pack(padx=10, pady=10)
            return

        for of in ofertas:
            row = ctk.CTkFrame(self._ofertas_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)

            txt = f"{of.jogador_nome} | {of.time_origem} → {format_reais(of.valor)}"
            ctk.CTkLabel(row, text=txt, font=FONTS["small"],
                          text_color=COLORS["text"]).pack(side="left")

            ctk.CTkButton(row, text="✅", width=30, height=28,
                           fg_color=COLORS["success"],
                           command=lambda o=of: self._aceitar_oferta(o)
                           ).pack(side="right", padx=2)

            ctk.CTkButton(row, text="❌", width=30, height=28,
                           fg_color=COLORS["danger"],
                           command=lambda o=of: self._recusar_oferta(o)
                           ).pack(side="right", padx=2)

    def _atualizar_livres(self) -> None:
        gm = self.app.game
        if gm is None:
            return

        motor = gm.mercado
        if motor is None:
            return

        livres = motor.jogadores_livres[:50]

        linhas = []
        for j in sorted(livres, key=lambda x: x.overall, reverse=True):
            linhas.append({
                "id": j.id,
                "valores": [j.nome, j.posicao.name, str(j.idade),
                            str(j.overall), format_reais(j.valor_mercado)],
            })

        self._tabela_livres.set_dados(linhas)

    def _selecionar_livre(self, item_id: int) -> None:
        gm = self.app.game
        if gm is None:
            return
        motor = gm.mercado
        if motor is None:
            return
        for j in motor.jogadores_livres:
            if j.id == item_id:
                self._livre_selecionado = j
                self._status.configure(text=f"Selecionado: {j.nome} (OVR {j.overall})")
                return

    def _contratar(self) -> None:
        gm = self.app.game
        if gm is None or gm.time_jogador is None or self._livre_selecionado is None:
            return
        motor = gm.mercado
        if motor is None:
            return
        j = self._livre_selecionado
        salario = max(5000, j.valor_mercado // 60)
        ok = motor.contratar_livre(gm.time_jogador, j, salario)
        if ok:
            self._status.configure(text=f"✅ {j.nome} contratado!")
            self.app.mostrar_toast(f"{j.nome} contratado com sucesso!", "success")
            self._livre_selecionado = None
            self._atualizar_livres()
        else:
            self._status.configure(text=f"❌ Não foi possível contratar {j.nome}")
            self.app.mostrar_toast("Contratação falhou.", "error")

    def _aceitar_oferta(self, oferta) -> None:
        gm = self.app.game
        if gm is None:
            return
        motor = gm.mercado
        if motor:
            oferta.status = StatusOferta.ACEITA
            motor._executar_transferencia(oferta, gm.times_serie_a + gm.times_serie_b)
        self._atualizar_ofertas()

    def _recusar_oferta(self, oferta) -> None:
        gm = self.app.game
        if gm is None:
            return
        motor = gm.mercado
        if motor:
            oferta.status = StatusOferta.RECUSADA
        self._atualizar_ofertas()
