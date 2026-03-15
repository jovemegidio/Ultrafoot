# -*- coding: utf-8 -*-
"""Smoke tests for offline license/demo flow."""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.license_service import LicenseService


def test_trial_and_activation():
    base_tmp = os.path.join(os.path.dirname(__file__), "..", "saves", ".tmp_license")
    tmp = os.path.join(base_tmp, "case_license_service")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    try:
        service = LicenseService(app_dir=tmp)
        status = service.status()
        assert status["edition"] == "demo"
        assert status["trial_active"] is True
        assert status["can_play"] is True

        body = "UF26OFFLINEFULLKEY2026"
        serial = body + service._expected_check(body)
        validation = service.validate_serial(serial)
        assert validation["ok"] is True

        activated = service.activate(serial)
        assert activated["ok"] is True

        status_full = service.status()
        assert status_full["activated"] is True
        assert status_full["edition"] == "full"
        assert status_full["feature_flags"]["editor_database"] is True
        print("[OK] test_trial_and_activation PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_trial_and_activation()
    print("\n[OK] Todos os testes de licença passaram!")
