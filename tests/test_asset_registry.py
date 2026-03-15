# -*- coding: utf-8 -*-
"""Smoke tests for packaged asset registry/compliance summary."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.asset_registry import AssetRegistryService
from services.licensing_engine import LicensingEngine


def test_asset_registry_summary():
    service = AssetRegistryService()
    licensing = LicensingEngine()
    data = service.to_api_dict(licensing)

    assert "summary" in data
    assert data["summary"]["clubes_esperados"] > 0
    assert "missing" in data
    assert "music_tracks" in data

    resolved = service.resolve_team_asset("flamengo")
    assert resolved["file_key"] == "flamengo"
    assert "exists" in resolved
    assert "placeholder" in resolved
    print("[OK] test_asset_registry_summary PASSED")


if __name__ == "__main__":
    test_asset_registry_summary()
    print("\n[OK] Todos os testes de asset registry passaram!")
