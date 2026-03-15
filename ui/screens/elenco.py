# -*- coding: utf-8 -*-
"""Tela Elenco — lista de jogadores, detalhes, filtros."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING, Optional

from ui.theme import COLORS, FONTS
from ui.widgets.data_table import DataTable
from utils.helpers import format_reais

if TYPE_CHECKING:
    from ui.app import App


class TelaElenco(ctk.CTkFrame):
    def __init__(self, master, app: App) -> None:
        super().__init__(master, fg_color=COLORS["bg_dark"])
        self.app = app
        self._jogador_selecionado = None

        # Título
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(header, text="👥 Elenco", font=FONTS["title"],
                      text_color=COLORS["text"]).pack(side="left")

        # Filtro posição
        self._filtro = ctk.CTkComboBox(
            header, values=["Todos", "GOL", "ZAG", "LD", "LE", "VOL", "MC",
                             "ME", "MD", "MEI", "PE", "PD", "CA", "SA"],
            width=130, font=FONTS["small"], state="readonly",
            command=self._aplicar_filtro,
        )
        self._filtro.set("Todos")
        self._filtro.pack(side="right", padx=5)

        # Corpo principal
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # Tabela de jogadores
        colunas = ["#", "Nome", "Pos", "Idade", "OVR", "Cond", "Moral", "Valor"]
        self._tabela = DataTable(body, colunas=colunas, on_select=self._selecionar)
        self._tabela.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Painel de detalhes
        self._detalhe = ctk.CTkFrame(body, fg_color=COLORS["bg_card"], corner_radius=8)
        self._detalhe.grid(row=0, column=1, sticky="nsew")

        self._det_nome = ctk.CTkLabel(self._detalhe, text="Selecione um jogador",
                                       font=FONTS["heading"],
                                       text_color=COLORS["text"])
        self._det_nome.pack(pady=(15, 5))

        self._det_info = ctk.CTkLabel(self._detalhe, text="",
                                       font=FONTS["small"],
                                       text_color=COLORS["text_secondary"],
                                       justify="left", wraplength=280)
        self._det_info.pack(padx=15, pady=10, anchor="w")

    def ao_exibir(self) -> None:
        self._atualizar_tabela()

    def _atualizar_tabela(self, filtro_pos: Optional[str] = None) -> None:
        gm = self.app.game
        if gm is None or gm.time_jogador is None:
            return

        jogadores = gm.time_jogador.jogadores
        if filtro_pos and filtro_pos != "Todos":
            jogadores = [j for j in jogadores if j.posicao.name == filtro_pos]

        jogadores = sorted(jogadores, key=lambda j: j.overall, reverse=True)

        linhas = []
        for j in jogadores:
            estado = "🟢" if j.pode_jogar() else "🔴"
            linhas.append({
                "id": j.id,
                "valores": [
                    str(j.numero_camisa),
                    j.nome,
                    j.posicao.name,
                    str(j.idade),
                    str(j.overall),
                    f"{j.condicao_fisica}%",
                    str(j.moral),
                    format_reais(j.valor_mercado),
                ],
            })

        self._tabela.set_dados(linhas)

    def _aplicar_filtro(self, valor: str) -> None:
        self._atualizar_tabela(valor)

    def _selecionar(self, item_id: int) -> None:
        gm = self.app.game
        if gm is None or gm.time_jogador is None:
            return

        j = gm.time_jogador.jogador_por_id(item_id)
        if j is None:
            return

        self._jogador_selecionado = j
        self._det_nome.configure(text=f"⚽ {j.nome}")

        traits_str = ", ".join(t.value for t in j.traits) if j.traits else "Nenhum"
        status = "✅ Disponível" if j.pode_jogar() else "❌ Indisponível"

        info = (
            f"Posição: {j.posicao.value}\n"
            f"Idade: {j.idade} | Altura: {j.altura}m\n"
            f"Pé: {j.pe_preferido.value}\n"
            f"Overall: {j.overall} | Potencial: {j.potencial}\n"
            f"Condição: {j.condicao_fisica}% | Moral: {j.moral}\n"
            f"Status: {status}\n"
            f"Lesão: {j.status_lesao.value}\n\n"
            f"── Técnicos ──\n"
            f"Passe Curto: {j.tecnicos.passe_curto} | Longo: {j.tecnicos.passe_longo}\n"
            f"Finalização: {j.tecnicos.finalizacao} | Drible: {j.tecnicos.drible}\n"
            f"Desarme: {j.tecnicos.desarme} | Marcação: {j.tecnicos.marcacao}\n"
            f"Cabeceio: {j.tecnicos.cabeceio}\n\n"
            f"── Físicos ──\n"
            f"Velocidade: {j.fisicos.velocidade} | Força: {j.fisicos.forca}\n"
            f"Resistência: {j.fisicos.resistencia} | Agilidade: {j.fisicos.agilidade}\n\n"
            f"── Mentais ──\n"
            f"Visão: {j.mentais.visao_jogo} | Decisão: {j.mentais.decisao}\n"
            f"Liderança: {j.mentais.lideranca} | Compostura: {j.mentais.compostura}\n\n"
            f"── Contrato ──\n"
            f"Salário: {format_reais(j.contrato.salario)}/mês\n"
            f"Multa: {format_reais(j.contrato.multa_rescisoria)}\n"
            f"Restam: {j.contrato.meses_restantes} meses\n\n"
            f"Traits: {traits_str}\n"
            f"Valor de mercado: {format_reais(j.valor_mercado)}"
        )

        self._det_info.configure(text=info)
