# -*- coding: utf-8 -*-
"""Smoke test dos endpoints usados pelas telas da sidebar."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from desktop_app import BrasfootAPI


def test_sidebar_endpoints():
    api = BrasfootAPI()
    res = json.loads(api.novo_jogo("Flamengo"))
    assert res["ok"] is True

    checks = {
        "dashboard": lambda: json.loads(api.get_dashboard()),
        "classificacao": lambda: json.loads(api.get_classificacao("serie_a")),
        "mercado": lambda: json.loads(api.get_mercado()),
        "financas": lambda: json.loads(api.get_financas()),
        "treinamento": lambda: json.loads(api.get_treinamento()),
        "base": lambda: json.loads(api.get_base_juvenil()),
        "agenda": lambda: json.loads(api.get_agenda()),
        "historico": lambda: json.loads(api.get_historico()),
        "inbox": lambda: json.loads(api.get_inbox()),
        "conquistas": lambda: json.loads(api.get_conquistas()),
        "premiacoes": lambda: json.loads(api.get_premiacoes()),
        "recordes": lambda: json.loads(api.get_recordes()),
        "estadio": lambda: json.loads(api.get_estadio_detalhes()),
        "staff": lambda: json.loads(api.get_staff_mercado()),
        "vestiario": lambda: json.loads(api.get_vestiario()),
        "promessas": lambda: json.loads(api.get_promessas()),
        "quimica": lambda: json.loads(api.get_quimica_tatica()),
        "carreira": lambda: json.loads(api.get_carreira_tecnico()),
        "analise": lambda: json.loads(api.get_analise_partida()),
        "objetivos": lambda: json.loads(api.get_objetivos_jogadores()),
        "ffp": lambda: json.loads(api.get_ffp_status()),
        "hallfame": lambda: json.loads(api.get_hall_of_fame()),
        "worldhub": lambda: json.loads(api.get_world_hub()),
        "assistente": lambda: json.loads(api.get_dicas_assistente()),
    }

    resultados = {nome: fn() for nome, fn in checks.items()}

    assert resultados["dashboard"]["time"] == "Flamengo"
    assert isinstance(resultados["agenda"], list)
    assert isinstance(resultados["historico"], dict)
    assert isinstance(resultados["staff"], list)
    assert isinstance(resultados["vestiario"], dict)
    assert isinstance(resultados["worldhub"], dict)
    assert "dicas" in resultados["assistente"]
    print("[OK] test_sidebar_endpoints PASSED")


if __name__ == "__main__":
    test_sidebar_endpoints()
    print("\n[OK] Todos os testes da sidebar passaram!")
