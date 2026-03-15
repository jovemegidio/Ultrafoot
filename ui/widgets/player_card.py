# -*- coding: utf-8 -*-
"""Widget PlayerCard — card visual de jogador."""
from __future__ import annotations

import customtkinter as ctk
from typing import TYPE_CHECKING

from ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from core.models import Jogador


class PlayerCard(ctk.CTkFrame):
    """Card compacto de jogador para listagens visuais."""

    def __init__(self, master, jogador: Jogador, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card"],
                         corner_radius=8, height=70, **kwargs)
        self.grid_propagate(False)

        j = jogador

        # Overall badge
        ovr_cor = COLORS["success"] if j.overall >= 75 else (
            COLORS["warning"] if j.overall >= 60 else COLORS["danger"]
        )
        ovr = ctk.CTkLabel(self, text=str(j.overall), font=FONTS["heading"],
                            text_color=ovr_cor, width=50)
        ovr.pack(side="left", padx=(10, 5), pady=10)

        # Info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=5)

        nome = ctk.CTkLabel(info_frame, text=j.nome, font=FONTS["body_bold"],
                             text_color=COLORS["text"], anchor="w")
        nome.pack(fill="x")

        sub = f"{j.posicao.name} | {j.idade} anos | #{j.numero_camisa}"
        ctk.CTkLabel(info_frame, text=sub, font=FONTS["small"],
                      text_color=COLORS["text_secondary"], anchor="w"
                      ).pack(fill="x")

        # Status
        status_icon = "🟢" if j.pode_jogar() else "🔴"
        ctk.CTkLabel(self, text=status_icon, font=FONTS["body"],
                      width=30).pack(side="right", padx=10)
