# -*- coding: utf-8 -*-
"""Testes do sistema de save/load."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from save_system.save_manager import serializar_jogo, desserializar_jogo
from managers.game_manager import GameManager


def test_serializar_desserializar():
    gm = GameManager()
    gm.novo_jogo("Flamengo")

    # Serializar
    json_str = serializar_jogo(gm)
    assert len(json_str) > 1000, "JSON muito curto"
    if isinstance(json_str, bytes):
        json_text = json_str.decode("utf-8")
    else:
        json_text = json_str
    assert "Flamengo" in json_text

    # Desserializar em novo GameManager
    gm2 = GameManager()
    desserializar_jogo(gm2, json_str)

    assert gm2.temporada == gm.temporada
    assert gm2.semana == gm.semana
    assert gm2.time_jogador is not None
    assert gm2.time_jogador.nome == "Flamengo"
    assert len(gm2.times_serie_a) == 20
    assert len(gm2.times_serie_b) == 20

    # Conferir jogadores
    for t in gm2.times_serie_a:
        assert len(t.jogadores) >= 20, f"{t.nome} perdeu jogadores no load"

    print("[OK] test_serializar_desserializar PASSED")


def test_round_trip_jogador():
    gm = GameManager()
    gm.novo_jogo("Palmeiras")

    j_original = gm.time_jogador.jogadores[0]
    json_str = serializar_jogo(gm)

    gm2 = GameManager()
    desserializar_jogo(gm2, json_str)

    j_loaded = gm2.time_jogador.jogadores[0]
    assert j_loaded.nome == j_original.nome
    assert j_loaded.posicao == j_original.posicao
    assert j_loaded.tecnicos.finalizacao == j_original.tecnicos.finalizacao
    assert j_loaded.fisicos.velocidade == j_original.fisicos.velocidade
    print("[OK] test_round_trip_jogador PASSED")


if __name__ == "__main__":
    test_serializar_desserializar()
    test_round_trip_jogador()
    print("\n[OK] Todos os testes de save/load passaram!")
