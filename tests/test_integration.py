# -*- coding: utf-8 -*-
"""Teste de integração — fluxo completo do jogo sem UI."""
import sys
import os
from functools import lru_cache
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from managers.game_manager import GameManager
from save_system.save_manager import serializar_jogo, desserializar_jogo


@lru_cache(maxsize=1)
def _estado_base():
    gm = GameManager()
    gm.novo_jogo("Flamengo")
    return serializar_jogo(gm)


def _novo_gm():
    gm = GameManager()
    desserializar_jogo(gm, _estado_base())
    return gm


def test_fluxo_completo():
    gm = _novo_gm()

    assert gm.time_jogador is not None
    assert gm.time_jogador.nome == "Flamengo"
    assert len(gm.times_serie_a) == 20
    assert len(gm.times_serie_b) == 20
    assert gm.competicoes.brasileirao_a is not None
    assert gm.fantasy.liga is not None
    assert len(gm.fantasy.liga.times) == 8

    # Avançar algumas semanas para exercitar temporada, tabela e save/load.
    for i in range(1, 5):
        resultados = gm.avancar_semana()
        assert isinstance(resultados, dict)
        assert gm.semana == i

    # Classificação existe e está ordenada
    classif = gm.competicoes.brasileirao_a.classificacao()
    assert len(classif) == 20
    camp = gm.competicoes.brasileirao_a
    for i in range(len(classif) - 1):
        atual = camp.get_stats(classif[i].id)
        prox = camp.get_stats(classif[i + 1].id)
        assert (
            atual["pontos"],
            atual["gm"] - atual["gs"],
            atual["gm"],
            atual["v"],
        ) >= (
            prox["pontos"],
            prox["gm"] - prox["gs"],
            prox["gm"],
            prox["v"],
        )

    # Mercado funciona
    assert len(gm.mercado.jogadores_livres) > 0

    # Save/load
    dados = serializar_jogo(gm)
    gm2 = GameManager()
    desserializar_jogo(gm2, dados)
    assert gm2.time_jogador.nome == "Flamengo"
    assert gm2.semana == 4
    assert len(gm2.times_serie_a) == 20

    print("[OK] test_fluxo_completo PASSED")


def test_multiplos_saves():
    gm = _novo_gm()
    for _ in range(2):
        gm.avancar_semana()

    sid1 = gm.salvar("integ_teste_1")
    assert sid1

    for _ in range(2):
        gm.avancar_semana()
    assert gm.semana == 4

    ok = gm.carregar("integ_teste_1")
    assert ok
    assert gm.semana == 2
    print("[OK] test_multiplos_saves PASSED")


def test_contratar_livre():
    gm = _novo_gm()

    livres = gm.mercado.jogadores_livres
    assert len(livres) > 0

    j = livres[0]
    elenco_antes = len(gm.time_jogador.jogadores)
    ok = gm.mercado.contratar_livre(gm.time_jogador, j, salario=10000)
    assert ok
    assert len(gm.time_jogador.jogadores) == elenco_antes + 1
    assert j not in gm.mercado.jogadores_livres
    print("[OK] test_contratar_livre PASSED")


def test_fantasy_integrado():
    gm = _novo_gm()

    fm = gm.fantasy
    assert fm is not None
    tj = fm.time_jogador()
    assert tj is not None
    assert tj.dono == "jogador"

    ranking = fm.classificacao()
    assert len(ranking) == 8
    print("[OK] test_fantasy_integrado PASSED")


if __name__ == "__main__":
    test_fluxo_completo()
    test_multiplos_saves()
    test_contratar_livre()
    test_fantasy_integrado()
    print("\n[OK] Todos os testes de integracao passaram!")
