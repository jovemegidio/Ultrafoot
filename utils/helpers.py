# -*- coding: utf-8 -*-
"""Funções auxiliares genéricas."""
from __future__ import annotations


def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    """Restringe *value* ao intervalo [low, high]."""
    return max(low, min(high, value))


def format_reais(valor: int | float) -> str:
    """Formata valor monetário no padrão brasileiro: R$ 1.234.567"""
    return f"R$ {int(valor):,.0f}".replace(",", ".")


def enum_val(enum_class, value):
    """Converte string (name ou value) para membro de *enum_class*."""
    for item in enum_class:
        if item.value == value or item.name == value:
            return item
    return list(enum_class)[0]
