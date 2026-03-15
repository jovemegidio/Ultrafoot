# -*- coding: utf-8 -*-
"""
Discord Rich Presence para Ultrafoot.
Mostra estado do jogo no perfil do Discord do jogador.
"""
from __future__ import annotations

import threading
import time as _time
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)

# Application ID do Discord Developer Portal
_CLIENT_ID = "1481784878197637160"

_rpc: Optional["Presence"] = None
_thread: Optional[threading.Thread] = None
_running = False
_lock = threading.Lock()
_pending: dict | None = None  # last requested state, applied on connect


def _connect() -> bool:
    """Tenta conectar ao Discord RPC. Retorna True se ok."""
    global _rpc
    try:
        from pypresence import Presence
        rpc = Presence(_CLIENT_ID)
        rpc.connect()
        _rpc = rpc
        log.info("Discord RPC conectado")
        # Apply pending state if any
        if _pending:
            try:
                _rpc.update(**_pending)
            except Exception:
                pass
        return True
    except Exception as e:
        log.debug("Discord RPC indisponível: %s", e)
        _rpc = None
        return False


def iniciar() -> None:
    """Inicia conexão com Discord RPC. Tenta sync primeiro, depois background retry."""
    global _running, _thread
    with _lock:
        if _running:
            return
        _running = True

    # Tenta conectar agora (sync) — cobre o caso comum (Discord aberto)
    _connect()

    def _loop():
        global _running
        while _running:
            if _rpc is None:
                if not _connect():
                    _time.sleep(30)
                    continue
            _time.sleep(15)

    _thread = threading.Thread(target=_loop, daemon=True, name="discord-rpc")
    _thread.start()


def parar() -> None:
    """Desconecta do Discord RPC."""
    global _running, _rpc, _pending
    _running = False
    _pending = None
    if _rpc:
        try:
            _rpc.clear()
        except Exception:
            pass
        try:
            _rpc.close()
        except Exception:
            pass
        _rpc = None


def atualizar_menu() -> None:
    """Mostra que o jogador está no menu principal."""
    _update(
        state="Menu Principal",
        details="Ultrafoot",
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot — Football Manager",
    )


def atualizar_jogo(*, time: str, temporada: int, semana: int,
                   divisao: str = "", posicao: int = 0) -> None:
    """Atualiza presença com info do jogo ativo."""
    state = f"Temporada {temporada} — Semana {semana}"
    if posicao > 0 and divisao:
        details = f"{time} — {posicao}º {divisao}"
    elif divisao:
        details = f"{time} — {divisao}"
    else:
        details = time
    _update(
        state=state,
        details=details,
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot — Football Manager",
    )


def atualizar_partida(*, time_casa: str, time_fora: str,
                      gols_casa: int = 0, gols_fora: int = 0,
                      minuto: int = 0) -> None:
    """Atualiza presença durante uma partida ao vivo."""
    _update(
        state=f"{time_casa} {gols_casa} x {gols_fora} {time_fora}",
        details=f"⚽ Partida ao vivo — {minuto}'",
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot — Football Manager",
    )


def atualizar_editor() -> None:
    """Mostra que o jogador está no editor."""
    _update(
        state="Editor de Times",
        details="Ultrafoot",
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot — Football Manager",
    )


def atualizar_contexto(contexto: str, *, clube: str = "",
                       temporada: int = 0, semana: int = 0) -> None:
    """Atualiza a presenca para telas contextuais do save."""
    chave = (contexto or "menu").strip().lower()
    mapa = {
        "dashboard": ("Gerenciando temporada", clube or "Ultrafoot"),
        "menu": ("Menu Principal", "Ultrafoot"),
        "inicio": ("Menu Principal", "Ultrafoot"),
        "elenco": ("Ajustando elenco", clube or "Ultrafoot"),
        "tatica": ("Montando tatica", clube or "Ultrafoot"),
        "mercado": ("No mercado de transferencias", clube or "Ultrafoot"),
        "inbox": ("Lendo inbox do tecnico", clube or "Ultrafoot"),
        "financas": ("Revisando financas", clube or "Ultrafoot"),
        "staff": ("Gerindo comissao tecnica", clube or "Ultrafoot"),
        "partida": ("Dia de jogo", clube or "Ultrafoot"),
        "configs": ("Ajustando configuracoes", "Ultrafoot"),
        "licensing": ("Revisando licenciamento", "Ultrafoot"),
        "desemprego": ("Observando o mercado", "Treinador sem clube"),
    }
    state, details = mapa.get(chave, ("Jogando Ultrafoot", clube or "Ultrafoot"))
    if temporada and semana and chave not in {"menu", "inicio", "configs", "licensing"}:
        details = f"{details} - T{temporada} S{semana}"
    _update(
        state=state,
        details=details,
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot - Football Manager",
    )


def atualizar_desemprego(*, semanas: int = 0, reputacao: int = 0) -> None:
    """Estado especial para tecnico desempregado."""
    detalhes = f"{semanas} semana(s) sem clube"
    if reputacao:
        detalhes += f" - Rep {reputacao}"
    _update(
        state="Observando o mercado",
        details=detalhes,
        large_image="logotipo_ultrafoot",
        large_text="Ultrafoot - Football Manager",
    )


def _update(**kwargs) -> None:
    """Envia update ao Discord, ignorando erros. Guarda state pending se offline."""
    global _rpc, _pending
    _pending = kwargs  # always save for reconnection
    if _rpc is None:
        return
    try:
        _rpc.update(**kwargs)
    except Exception as e:
        log.debug("Discord RPC update falhou: %s", e)
        _rpc = None
