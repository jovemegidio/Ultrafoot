# -*- coding: utf-8 -*-
"""Smoke tests for contextual soundtrack management."""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.music_manager import MusicManager


def test_contextos_e_streamer_safe():
    base_tmp = os.path.join(os.path.dirname(__file__), "..", "saves", ".tmp_music")
    tmp = os.path.join(base_tmp, "case_music_manager")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    try:
        music_dir = os.path.join(tmp, "music")
        os.makedirs(music_dir, exist_ok=True)

        menu_file = os.path.join(music_dir, "01 - Menu Theme.mp3")
        pre_file = os.path.join(music_dir, "02 - Pre Match.ogg")
        with open(menu_file, "wb") as f:
            f.write(b"menu")
        with open(pre_file, "wb") as f:
            f.write(b"pre")

        manifest_path = os.path.join(music_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "tracks": [
                        {
                            "arquivo": "01 - Menu Theme.mp3",
                            "titulo": "Menu Theme",
                            "contextos": ["menu"],
                            "streamer_safe": False,
                            "licenca": "nao_verificada",
                        },
                        {
                            "arquivo": "02 - Pre Match.ogg",
                            "titulo": "Pre Match",
                            "contextos": ["pre_match"],
                            "streamer_safe": True,
                            "licenca": "royalty_free",
                        },
                    ]
                },
                f,
                ensure_ascii=False,
            )

        mm = MusicManager(music_dirs=[music_dir], manifest_paths=[manifest_path])

        faixa_menu = mm.get_faixa_atual()
        assert faixa_menu is not None
        assert faixa_menu["titulo"] == "Menu Theme"

        faixa_pre = mm.set_contexto("partida")
        assert faixa_pre is not None
        assert faixa_pre["titulo"] == "Pre Match"

        mm.set_contexto("menu")
        faixa_silenciosa = mm.set_streamer_safe(True)
        assert faixa_silenciosa is None

        faixa_pre_safe = mm.set_contexto("partida")
        assert faixa_pre_safe is not None
        assert faixa_pre_safe["streamer_safe"] is True
        print("[OK] test_contextos_e_streamer_safe PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_contextos_e_streamer_safe()
    print("\n[OK] Todos os testes do music_manager passaram!")
