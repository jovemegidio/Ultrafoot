# -*- coding: utf-8 -*-
"""Exceções customizadas do Ultrafoot."""


class BrasfootError(Exception):
    """Exceção base do jogo."""


class SaldoInsuficienteError(BrasfootError):
    """Tentativa de gastar mais do que o saldo disponível."""


class JogadorIndisponivelError(BrasfootError):
    """Jogador lesionado, suspenso ou sem condições de jogar."""


class ElencoInvalidoError(BrasfootError):
    """Escalação com problemas (menos de 11, posição faltando, etc.)."""


class SaveCorruptError(BrasfootError):
    """Arquivo de save corrompido ou incompatível."""


class TransferenciaInvalidaError(BrasfootError):
    """Transferência não pode ser concluída."""


class CompeticaoEncerradaError(BrasfootError):
    """Tentativa de jogar rodada em competição encerrada."""
