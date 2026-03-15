# -*- coding: utf-8 -*-
"""Smoke tests for save integrity, backup rotation and recovery."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from managers.game_manager import GameManager


def test_save_backup_and_restore():
    gm = GameManager()
    nome = "test_save_integrity_case"
    gm.save_integrity.delete(nome, include_backups=True)

    try:
        gm.novo_jogo("Flamengo")
        gm.salvar(nome)
        status_1 = gm.validar_save(nome)
        assert status_1["ok"] is True
        assert status_1["backups"] == 0

        gm.avancar_semana()
        gm.salvar(nome)
        status_2 = gm.validar_save(nome)
        assert status_2["ok"] is True
        assert status_2["backups"] >= 1

        save_path = gm.save_integrity._save_path(nome)
        with open(save_path, "wb") as f:
            f.write(b"corrupted-save")

        status_corrompido = gm.validar_save(nome)
        assert status_corrompido["ok"] is False

        restaurado = gm.restaurar_ultimo_backup(nome)
        assert restaurado["ok"] is True
        status_restaurado = gm.validar_save(nome)
        assert status_restaurado["ok"] is True
        assert gm.semana == 0
        print("[OK] test_save_backup_and_restore PASSED")
    finally:
        gm.save_integrity.delete(nome, include_backups=True)


if __name__ == "__main__":
    test_save_backup_and_restore()
    print("\n[OK] Todos os testes de integridade de save passaram!")
