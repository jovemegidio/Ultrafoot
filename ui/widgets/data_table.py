# -*- coding: utf-8 -*-
"""Widget DataTable — tabela de dados configurável com seleção."""
from __future__ import annotations

import customtkinter as ctk
from typing import Callable, List, Dict, Optional

from ui.theme import COLORS, FONTS


class DataTable(ctk.CTkFrame):
    """Tabela estilizada com cabeçalho, linhas alternadas e callback de seleção."""

    def __init__(self, master, colunas: List[str],
                 on_select: Optional[Callable[[int], None]] = None,
                 **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=8, **kwargs)
        self._colunas = colunas
        self._on_select = on_select
        self._rows: List[Dict] = []

        # Scroll interno
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True)

        # Cabeçalho
        self._header = ctk.CTkFrame(self._scroll, fg_color=COLORS["bg_input"],
                                     corner_radius=0)
        self._header.pack(fill="x")

        for col in colunas:
            ctk.CTkLabel(self._header, text=col, font=FONTS["small_bold"],
                          text_color=COLORS["text"], width=90
                          ).pack(side="left", padx=4, pady=4)

        # Container de linhas
        self._body = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._body.pack(fill="both", expand=True)

    def set_dados(self, linhas: List[Dict]) -> None:
        """Atualiza dados. Cada linha = {"id": int, "valores": [str, ...]}"""
        self._rows = linhas

        # Limpar
        for w in self._body.winfo_children():
            w.destroy()

        for i, row in enumerate(linhas):
            bg = COLORS["bg_card"] if i % 2 == 0 else COLORS["bg_dark"]
            row_frame = ctk.CTkFrame(self._body, fg_color=bg, corner_radius=0,
                                      height=28)
            row_frame.pack(fill="x")

            for val in row["valores"]:
                lbl = ctk.CTkLabel(row_frame, text=str(val), font=FONTS["small"],
                                    text_color=COLORS["text"], width=90, anchor="w")
                lbl.pack(side="left", padx=4, pady=2)

            # Bind click + hover
            if self._on_select:
                item_id = row["id"]
                for child in row_frame.winfo_children():
                    child.bind("<Button-1>", lambda e, rid=item_id: self._on_select(rid))
                    child.bind("<Enter>", lambda e, f=row_frame: f.configure(fg_color=COLORS["bg_hover"]))
                    child.bind("<Leave>", lambda e, f=row_frame, c=bg: f.configure(fg_color=c))
                row_frame.bind("<Button-1>", lambda e, rid=item_id: self._on_select(rid))
                row_frame.bind("<Enter>", lambda e, f=row_frame: f.configure(fg_color=COLORS["bg_hover"]))
                row_frame.bind("<Leave>", lambda e, f=row_frame, c=bg: f.configure(fg_color=c))

    def limpar(self) -> None:
        self._rows = []
        for w in self._body.winfo_children():
            w.destroy()
