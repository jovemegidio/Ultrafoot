# -*- coding: utf-8 -*-
"""Smokes do loop principal para prontidão jogável."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_app import BrasfootAPI
from managers.game_manager import GameManager


def test_pre_temporada_janela_e_resumo():
    gm = GameManager()
    gm.novo_jogo("Flamengo")

    assert gm.motor_temporada.pre_temporada_ativa is True
    assert gm.mercado_aberto(1) is True
    assert gm.mercado_aberto(11) is False

    for _ in range(4):
        gm.avancar_semana()

    resumo = gm.get_resumo_semana()
    assert gm.motor_temporada.pre_temporada_ativa is False
    assert resumo["semana"] == 4
    assert "mercado_aberto" in resumo
    assert isinstance(resumo["resultados"], list)
    print("[OK] test_pre_temporada_janela_e_resumo PASSED")


def test_contrato_nao_reduz_duas_vezes():
    gm = GameManager()
    gm.novo_jogo("Flamengo")

    jogador = gm.time_jogador.jogadores[0]
    jogador.idade = 24
    jogador.contrato.meses_restantes = 36
    gm._processar_fim_temporada()

    assert jogador.contrato.meses_restantes == 24
    print("[OK] test_contrato_nao_reduz_duas_vezes PASSED")


def test_api_elenco_e_mercado_tem_foto_e_valor():
    api = BrasfootAPI()
    assert json.loads(api.novo_jogo("Flamengo"))["ok"] is True

    elenco = json.loads(api.get_elenco())
    mercado = json.loads(api.buscar_mercado("", 0, 45, 0, "", "livres"))

    assert elenco and elenco[0]["valor_fmt"]
    assert elenco[0]["foto"]
    assert mercado["livres"] and mercado["livres"][0]["valor_fmt"]
    assert mercado["livres"][0]["foto"]
    print("[OK] test_api_elenco_e_mercado_tem_foto_e_valor PASSED")


def test_ligas_europeias_jogaveis():
    gm = GameManager()
    gm.novo_jogo_config("Chelsea", ["ING", "ESP"], tecnico_nome="Tester")

    assert gm.time_jogador is not None
    assert gm.time_jogador.nome == "Chelsea"
    assert "ING" in gm.times_europeus
    assert "ESP" in gm.times_europeus
    assert gm.competicoes.ligas_europeias
    print("[OK] test_ligas_europeias_jogaveis PASSED")


if __name__ == "__main__":
    test_pre_temporada_janela_e_resumo()
    test_contrato_nao_reduz_duas_vezes()
    test_api_elenco_e_mercado_tem_foto_e_valor()
    test_ligas_europeias_jogaveis()
    print("\n[OK] Todos os smokes de gameplay passaram!")
