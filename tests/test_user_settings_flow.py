# -*- coding: utf-8 -*-
"""Persistencia e aplicacao de configuracoes do app."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_app import BrasfootAPI


def _assert(ok, msg):
    if not ok:
        raise AssertionError(msg)


def main():
    api = BrasfootAPI()
    update = json.loads(api.update_user_settings(json.dumps({
        "window_fullscreen": False,
        "window_maximized": True,
        "window_width": 1366,
        "window_height": 768,
        "ui_scale": 0.95,
        "perf_mode": True,
        "music_volume": 0.35,
        "effects_volume": 0.55,
        "narration_volume": 0.65,
        "match_speed": 2.0,
        "difficulty": "dificil",
    })))
    _assert(update.get("ok"), "update_user_settings falhou")

    loaded = json.loads(api.get_user_settings())
    _assert(loaded["window_width"] == 1366, "largura nao persistiu")
    _assert(bool(loaded["window_maximized"]) is True, "window_maximized nao persistiu")
    _assert(abs(float(loaded["ui_scale"]) - 0.95) < 0.001, "ui_scale nao persistiu")
    _assert(bool(loaded["perf_mode"]) is True, "perf_mode nao persistiu")
    _assert(loaded["difficulty"] == "dificil", "difficulty nao persistiu")

    cfg = {
        "time": "Flamengo",
        "ligas": ["BRA", "ARG", "ING", "ESP"],
        "tecnico_nome": "Settings Tester",
        "temporada_inicio": 2026,
        "competicoes_selecoes": True,
        "tacas_internacionais": True,
    }
    result = json.loads(api.novo_jogo_config(json.dumps(cfg)))
    _assert(result.get("ok"), "novo_jogo_config falhou")

    gm = api._gm
    _assert(gm is not None, "GameManager nao foi criado")
    _assert(gm.modo_performance is True, "perf_mode nao foi aplicado ao jogo")
    _assert(gm.auto_save_intervalo_semanas == 24, "intervalo de autosave em modo performance incorreto")
    _assert(abs(gm.music.get_volume("musica") - 0.35) < 0.001, "volume de musica nao aplicado")
    _assert(abs(gm.music.get_volume("efeitos") - 0.55) < 0.001, "volume de efeitos nao aplicado")
    _assert(abs(gm.music.get_volume("narracao") - 0.65) < 0.001, "volume de narracao nao aplicado")

    print("[OK] test_user_settings_flow PASSED")


if __name__ == "__main__":
    main()
