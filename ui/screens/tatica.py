# -*- coding: utf-8 -*-
"""Tela Tática — formação, estilo, escalação de titulares."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS
from core.enums import FormacaoTatica, EstiloJogo, VelocidadeJogo, MarcacaoPressao

if TYPE_CHECKING:
    from ui.app import App


class TelaTatica(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_dark"])
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="📋 Tática", font=FONTS["title"],
                      text_color=COLORS["text"]).pack(anchor="w", pady=(0, 15))

        # Formação
        row1 = ctk.CTkFrame(scroll, fg_color="transparent")
        row1.pack(fill="x", pady=5)

        ctk.CTkLabel(row1, text="Formação:", font=FONTS["body_bold"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 10))

        self._combo_formacao = ctk.CTkComboBox(
            row1, values=[f.value for f in FormacaoTatica],
            width=150, font=FONTS["body"], state="readonly",
            command=self._mudar_formacao,
        )
        self._combo_formacao.pack(side="left")

        # Estilo de jogo
        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", pady=5)

        ctk.CTkLabel(row2, text="Estilo:", font=FONTS["body_bold"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 10))

        self._combo_estilo = ctk.CTkComboBox(
            row2, values=[e.value for e in EstiloJogo],
            width=180, font=FONTS["body"], state="readonly",
            command=self._mudar_estilo,
        )
        self._combo_estilo.pack(side="left")

        # Velocidade
        row3 = ctk.CTkFrame(scroll, fg_color="transparent")
        row3.pack(fill="x", pady=5)

        ctk.CTkLabel(row3, text="Velocidade:", font=FONTS["body_bold"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 10))

        self._combo_vel = ctk.CTkComboBox(
            row3, values=[v.value for v in VelocidadeJogo],
            width=150, font=FONTS["body"], state="readonly",
            command=self._mudar_velocidade,
        )
        self._combo_vel.pack(side="left")

        # Marcação
        row4 = ctk.CTkFrame(scroll, fg_color="transparent")
        row4.pack(fill="x", pady=5)

        ctk.CTkLabel(row4, text="Marcação:", font=FONTS["body_bold"],
                      text_color=COLORS["text"]).pack(side="left", padx=(0, 10))

        self._combo_marc = ctk.CTkComboBox(
            row4, values=[m.value for m in MarcacaoPressao],
            width=150, font=FONTS["body"], state="readonly",
            command=self._mudar_marcacao,
        )
        self._combo_marc.pack(side="left")

        sep = ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"])
        sep.pack(fill="x", pady=15)

        # Switches
        self._switches_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._switches_frame.pack(fill="x", pady=5)

        self._sw = {}
        opcoes = [
            ("linha_alta", "Linha Alta"), ("contra_ataque", "Contra-Ataque"),
            ("jogo_pelas_laterais", "Jogo pelas Laterais"),
            ("jogo_pelo_centro", "Jogo pelo Centro"),
            ("bola_longa", "Bola Longa"), ("toque_curto", "Toque Curto"),
            ("pressao_saida_bola", "Pressão na Saída"),
            ("zaga_adiantada", "Zaga Adiantada"),
        ]

        for i, (attr, label) in enumerate(opcoes):
            sw = ctk.CTkSwitch(self._switches_frame, text=label,
                                font=FONTS["small"], text_color=COLORS["text"],
                                command=lambda a=attr: self._toggle_switch(a))
            sw.grid(row=i // 2, column=i % 2, padx=10, pady=4, sticky="w")
            self._sw[attr] = sw

        sep2 = ctk.CTkFrame(scroll, height=1, fg_color=COLORS["border"])
        sep2.pack(fill="x", pady=15)

        # Titulares
        ctk.CTkLabel(scroll, text="Titulares (11):", font=FONTS["heading"],
                      text_color=COLORS["text"]).pack(anchor="w", pady=(5, 5))

        self._titulares_frame = ctk.CTkFrame(scroll, fg_color=COLORS["bg_card"],
                                              corner_radius=8)
        self._titulares_frame.pack(fill="x", pady=5)

        # Auto-escalar
        btn_auto = ctk.CTkButton(
            scroll, text="🤖  Auto-Escalar",
            font=FONTS["body_bold"], fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            height=38, width=180, corner_radius=6,
            command=self._auto_escalar,
        )
        btn_auto.pack(pady=10)

        self._status = ctk.CTkLabel(scroll, text="", font=FONTS["small"],
                                     text_color=COLORS["text_secondary"])
        self._status.pack()

    def ao_exibir(self) -> None:
        gm = self.app.game
        if gm is None or gm.time_jogador is None:
            return

        t = gm.time_jogador
        tat = t.tatica

        self._combo_formacao.set(tat.formacao.value)
        self._combo_estilo.set(tat.estilo.value)
        self._combo_vel.set(tat.velocidade.value)
        self._combo_marc.set(tat.marcacao.value)

        for attr, sw in self._sw.items():
            if getattr(tat, attr, False):
                sw.select()
            else:
                sw.deselect()

        self._atualizar_titulares()

    def _atualizar_titulares(self) -> None:
        for w in self._titulares_frame.winfo_children():
            w.destroy()

        gm = self.app.game
        if gm is None or gm.time_jogador is None:
            return

        t = gm.time_jogador
        for i, jid in enumerate(t.titulares):
            j = t.jogador_por_id(jid)
            if j is None:
                continue
            txt = f"{j.numero_camisa:2d}. {j.nome}  ({j.posicao.name}, OVR {j.overall})"
            cor = COLORS["success"] if j.pode_jogar() else COLORS["danger"]
            ctk.CTkLabel(self._titulares_frame, text=txt,
                          font=FONTS["mono"], text_color=cor,
                          anchor="w").pack(fill="x", padx=10, pady=1)

    def _mudar_formacao(self, valor: str) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            for f in FormacaoTatica:
                if f.value == valor:
                    gm.time_jogador.tatica.formacao = f
                    break
            # Re-escalar titulares
            from data.seeds.seed_loader import _selecionar_titulares_auto
            gm.time_jogador.titulares = _selecionar_titulares_auto(gm.time_jogador)
            self._atualizar_titulares()
            self._status.configure(text=f"Formação alterada para {valor}")

    def _mudar_estilo(self, valor: str) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            for e in EstiloJogo:
                if e.value == valor:
                    gm.time_jogador.tatica.estilo = e
                    break

    def _mudar_velocidade(self, valor: str) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            for v in VelocidadeJogo:
                if v.value == valor:
                    gm.time_jogador.tatica.velocidade = v
                    break

    def _mudar_marcacao(self, valor: str) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            for m in MarcacaoPressao:
                if m.value == valor:
                    gm.time_jogador.tatica.marcacao = m
                    break

    def _toggle_switch(self, attr: str) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            sw = self._sw[attr]
            setattr(gm.time_jogador.tatica, attr, bool(sw.get()))

    def _auto_escalar(self) -> None:
        gm = self.app.game
        if gm and gm.time_jogador:
            from data.seeds.seed_loader import _selecionar_titulares_auto
            gm.time_jogador.titulares = _selecionar_titulares_auto(gm.time_jogador)
            self._atualizar_titulares()
            self._status.configure(text="✅ Escalação automática aplicada")
