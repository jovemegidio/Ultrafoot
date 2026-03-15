# -*- coding: utf-8 -*-
"""
Offline-ready license/demo service.

This is a local-first foundation for:
- demo/full edition switch
- trial period
- offline serial activation
- future build channel gating
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import string
import time
import uuid
from typing import Dict

from config import APP_DIR, BUILD_CHANNEL, GAME_TITLE, GAME_VERSION
from utils.logger import get_logger

log = get_logger(__name__)

_SERIAL_SALT = "ULTRAFOOT_OFFLINE_2026"
_HMAC_KEY = b"UF26_INTEGRITY_KEY_" + hashlib.sha256(b"ultrafoot_license_2026").digest()[:16]
_ALPHABET = string.digits + string.ascii_uppercase


def _base36(num: int) -> str:
    if num <= 0:
        return "0"
    out = []
    while num:
        num, rem = divmod(num, 36)
        out.append(_ALPHABET[rem])
    return "".join(reversed(out))


class LicenseService:
    """Stores local license/trial state for commercial desktop builds."""

    def __init__(self, app_dir: str = APP_DIR) -> None:
        self.app_dir = app_dir
        self.license_path = os.path.join(app_dir, "license_status.json")
        self._state = self._load_or_init()

    def _default_state(self) -> Dict:
        now = int(time.time())
        return {
            "edition": "demo",
            "activated": False,
            "build_channel": BUILD_CHANNEL,
            "game_version": GAME_VERSION,
            "trial_days": 14,
            "trial_started_at": now,
            "serial_hint": "",
            "last_validation": now,
        }

    def _compute_hmac(self, state: Dict) -> str:
        """Compute HMAC of state fields to detect tampering."""
        keys = sorted(k for k in state if k != "_hmac")
        payload = "|".join(f"{k}={state[k]}" for k in keys)
        return hmac.new(_HMAC_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _load_or_init(self) -> Dict:
        os.makedirs(self.app_dir, exist_ok=True)
        if os.path.isfile(self.license_path):
            try:
                with open(self.license_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    stored_hmac = data.pop("_hmac", None)
                    merged = {**self._default_state(), **data}
                    if stored_hmac and stored_hmac == self._compute_hmac(merged):
                        return merged
                    elif stored_hmac:
                        log.warning("license_status.json HMAC mismatch — resetting to demo")
                        state = self._default_state()
                        self._persist(state)
                        return state
                    else:
                        # Legacy file without HMAC — migrate
                        self._persist(merged)
                        return merged
            except Exception as e:
                log.warning("Erro ao carregar license_status.json: %s", e)
        state = self._default_state()
        self._persist(state)
        return state

    def _persist(self, state: Dict | None = None) -> None:
        state = state or self._state
        save_state = {k: v for k, v in state.items() if k != "_hmac"}
        save_state["_hmac"] = self._compute_hmac(save_state)
        tmp = self.license_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(save_state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.license_path)

    def _normalize_serial(self, serial: str) -> str:
        return "".join(ch for ch in (serial or "").upper() if ch.isalnum())

    def _expected_check(self, body: str) -> str:
        digest = hashlib.sha256((body + _SERIAL_SALT).encode("utf-8")).hexdigest().upper()
        return _base36(int(digest[:10], 16))[:6].rjust(6, "0")

    def validate_serial(self, serial: str) -> Dict:
        normalized = self._normalize_serial(serial)
        if not normalized.startswith("UF26") or len(normalized) < 18:
            return {"ok": False, "error": "serial_invalido"}
        body = normalized[:-6]
        provided = normalized[-6:]
        expected = self._expected_check(body)
        return {
            "ok": provided == expected,
            "error": "" if provided == expected else "checksum_invalido",
            "serial_hint": normalized[-4:],
        }

    def activate(self, serial: str) -> Dict:
        validation = self.validate_serial(serial)
        if not validation["ok"]:
            return validation
        self._state["activated"] = True
        self._state["edition"] = "full"
        self._state["serial_hint"] = validation["serial_hint"]
        self._state["last_validation"] = int(time.time())
        self._persist()
        return {"ok": True, "edition": "full", "serial_hint": validation["serial_hint"]}

    def status(self) -> Dict:
        now = int(time.time())
        started = int(self._state.get("trial_started_at", now))
        last_val = int(self._state.get("last_validation", now))
        trial_days = int(self._state.get("trial_days", 14))
        activated = bool(self._state.get("activated", False))

        # Anti-clock-tampering: if current time is before last_validation, trial expired
        clock_tampered = now < last_val - 300  # allow 5 min tolerance
        elapsed_days = max(0, int((now - started) / 86400))
        remaining = max(0, trial_days - elapsed_days)
        if clock_tampered and not activated:
            remaining = 0

        # Update last_validation
        if now >= last_val:
            self._state["last_validation"] = now
            self._persist()

        edition = "full" if activated else self._state.get("edition", "demo")
        trial_active = not activated and remaining > 0
        can_play = activated or trial_active
        return {
            "product": GAME_TITLE,
            "game_version": GAME_VERSION,
            "build_channel": self._state.get("build_channel", BUILD_CHANNEL),
            "edition": edition,
            "activated": activated,
            "trial_active": trial_active,
            "trial_days": trial_days,
            "trial_remaining_days": remaining,
            "serial_hint": self._state.get("serial_hint", ""),
            "can_play": can_play,
            "feature_flags": self.feature_flags(),
        }

    def feature_flags(self) -> Dict[str, bool]:
        activated = bool(self._state.get("activated", False))
        return {
            "multisave": True,
            "editor_database": activated,
            "assets_modding": activated,
            "ligas_internacionais": True,
            "updater_channel_beta": activated,
        }
