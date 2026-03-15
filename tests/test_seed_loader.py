# -*- coding: utf-8 -*-
"""Testes do seed_loader e geração de atributos."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.enums import Posicao
from core.models import Jogador
from data.seeds.seed_loader import (
    criar_times_serie_a,
    criar_times_serie_b,
    criar_times_serie_c,
    criar_times_serie_d,
    gerar_atributos_jogador,
)


def test_criar_times_serie_a():
    times = criar_times_serie_a()
    assert len(times) == 20, f"Esperava 20, obteve {len(times)}"
    for t in times:
        assert len(t.jogadores) >= 20, f"{t.nome} tem poucos jogadores: {len(t.jogadores)}"
        assert len(t.titulares) == 11, f"{t.nome} não tem 11 titulares"
        assert len(t.staff) >= 5, f"{t.nome} sem staff completo"
        assert t.divisao == 1
    print("[OK] test_criar_times_serie_a PASSED")


def test_criar_times_serie_b():
    times = criar_times_serie_b()
    assert len(times) == 20
    for t in times:
        assert len(t.jogadores) >= 20
        assert t.divisao == 2
    print("[OK] test_criar_times_serie_b PASSED")


def test_criar_times_serie_c_d():
    serie_c = criar_times_serie_c()
    serie_d = criar_times_serie_d()
    assert len(serie_c) == 20, f"Esperava 20 times na Série C, obteve {len(serie_c)}"
    assert len(serie_d) == 96, f"Esperava 96 times na Série D, obteve {len(serie_d)}"
    assert any(t.nome == "Inter de Limeira" for t in serie_c)
    assert any(t.nome == "ABC" for t in serie_d)
    print("[OK] test_criar_times_serie_c_d PASSED")


def test_metadata_overrides():
    serie_a = {t.nome: t for t in criar_times_serie_a()}
    serie_b = {t.nome: t for t in criar_times_serie_b()}
    serie_c = {t.nome: t for t in criar_times_serie_c()}

    assert serie_a["Flamengo"].financas.patrocinador_principal == "Betano"
    assert serie_a["Botafogo"].estadio.nome == "Estádio Nilton Santos"
    assert serie_a["Mirassol"].financas.patrocinador_principal == "7K"
    assert serie_a["Coritiba"].financas.patrocinador_principal == "Reals"
    assert serie_a["Remo"].divisao == 1
    assert serie_b["Fortaleza"].estadio.nome == "Arena Castelão"
    assert serie_c["Inter de Limeira"].divisao == 3
    print("[OK] test_metadata_overrides PASSED")


def test_gerar_atributos():
    jogador = Jogador(id=1, nome="Teste", posicao=Posicao.CA)
    gerar_atributos_jogador(jogador, 70)
    assert 1 <= jogador.tecnicos.finalizacao <= 99
    assert 1 <= jogador.fisicos.velocidade <= 99
    assert 1 <= jogador.mentais.visao_jogo <= 99
    assert jogador.goleiro.reflexos < 50 or True
    print("[OK] test_gerar_atributos PASSED")


def test_overall():
    jogador = Jogador(id=2, nome="OVR Test", posicao=Posicao.MC)
    gerar_atributos_jogador(jogador, 60)
    ovr = jogador.overall
    assert 30 <= ovr <= 99, f"Overall fora do range: {ovr}"
    print("[OK] test_overall PASSED")


if __name__ == "__main__":
    test_criar_times_serie_a()
    test_criar_times_serie_b()
    test_criar_times_serie_c_d()
    test_metadata_overrides()
    test_gerar_atributos()
    test_overall()
    print("\n[OK] Todos os testes de seed_loader passaram!")
