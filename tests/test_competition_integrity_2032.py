# -*- coding: utf-8 -*-
"""Integridade de calendário e competições até 2032."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from managers.game_manager import GameManager


def _assert(ok, msg):
    if not ok:
        raise AssertionError(msg)


def main():
    gm = GameManager()
    gm.novo_jogo_config(
        "Flamengo",
        ["BRA", "ARG", "BOL", "VEN", "COL", "ING", "ESP", "ITA", "FRA"],
        tecnico_nome="Integrity Tester",
        temporada_inicio=2026,
        comp_selecoes=True,
        tacas_internacionais=True,
    )
    gm.configurar_performance(True)
    gm.auto_save_ativo = False

    serie_a_inicial = {t.nome for t in gm.times_serie_a}
    seen_wc = gm.competicoes.copa_mundo is not None
    seen_euro = gm.competicoes.eurocopa is not None
    seen_copa_america = gm.competicoes.copa_america is not None

    while gm.temporada < 2032:
        gm.avancar_semana()
        seen_wc = seen_wc or (gm.competicoes.copa_mundo is not None)
        seen_euro = seen_euro or (gm.competicoes.eurocopa is not None)
        seen_copa_america = seen_copa_america or (gm.competicoes.copa_america is not None)

        _assert(len(gm.times_serie_a) == 20, "Serie A perdeu integridade")
        _assert(len(gm.times_serie_b) == 20, "Serie B perdeu integridade")
        _assert(len(gm.times_serie_c) == 20, "Serie C perdeu integridade")
        _assert(len(gm.times_serie_d) >= 64, "Serie D ficou pequena demais")

    serie_a_final = {t.nome for t in gm.times_serie_a}
    _assert(seen_wc, "Copa do Mundo nao apareceu ate 2032")
    _assert(seen_euro, "Eurocopa nao apareceu ate 2032")
    _assert(seen_copa_america, "Copa America nao apareceu ate 2032")
    _assert(serie_a_inicial != serie_a_final, "Promocao/rebaixamento nao alterou a Serie A")

    print("[OK] test_competition_integrity_2032 PASSED")
    print("Temporada final:", gm.temporada, "semana:", gm.semana)
    print("Seleções:", {"wc": seen_wc, "euro": seen_euro, "copa_america": seen_copa_america})


if __name__ == "__main__":
    main()
