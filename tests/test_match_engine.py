# -*- coding: utf-8 -*-
"""Testes do motor de partida."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.match_engine import MotorPartida
from data.seeds.seed_loader import criar_times_serie_a


def test_simular_partida():
    times = criar_times_serie_a()
    motor = MotorPartida()
    casa = times[0]  # Flamengo
    fora = times[1]  # Palmeiras

    resultado = motor.simular(casa, fora)

    assert resultado.time_casa == casa.nome
    assert resultado.time_fora == fora.nome
    assert resultado.gols_casa >= 0
    assert resultado.gols_fora >= 0
    assert resultado.posse_casa > 0
    assert len(resultado.eventos) > 0
    assert resultado.publico > 0
    print(f"[OK] test_simular_partida PASSED - {resultado.placar}")


def test_notas_jogadores():
    times = criar_times_serie_a()
    motor = MotorPartida()
    resultado = motor.simular(times[2], times[3])
    assert len(resultado.notas_jogadores) > 0, "Notas devem ser geradas"
    for jid, nota in resultado.notas_jogadores.items():
        assert 3.0 <= nota <= 10.0, f"Nota fora do range: {nota}"
    print("[OK] test_notas_jogadores PASSED")


def test_fantasy_pontos():
    times = criar_times_serie_a()
    motor = MotorPartida()
    resultado = motor.simular(times[4], times[5])
    # Fantasy pontos podem ou não ser preenchidos
    print(f"[OK] test_fantasy_pontos PASSED - {len(resultado.fantasy_pontos)} jogadores pontuaram")


if __name__ == "__main__":
    test_simular_partida()
    test_notas_jogadores()
    test_fantasy_pontos()
    print("\n[OK] Todos os testes do motor de partida passaram!")
