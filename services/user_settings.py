from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict

from config import APP_DIR, WINDOW_HEIGHT, WINDOW_WIDTH
from utils.logger import get_logger

log = get_logger(__name__)


class UserSettingsService:
    """Persiste preferencias globais do app fora dos saves."""

    _FILE_NAME = "user_settings.json"

    _DEFAULTS: Dict[str, Any] = {
        "window_fullscreen": False,
        "window_maximized": False,
        "window_width": WINDOW_WIDTH,
        "window_height": WINDOW_HEIGHT,
        "ui_scale": 1.0,
        "perf_mode": False,
        "music_volume": 0.5,
        "effects_volume": 0.8,
        "narration_volume": 0.7,
        "narrator": "",
        "streamer_safe": False,
        "menu_music": True,
        "pre_match_music": True,
        "auto_save": True,
        "show_notifications": True,
        "animations": True,
        "match_speed": 1.0,
        "difficulty": "normal",
    }

    def __init__(self, app_dir: str = APP_DIR) -> None:
        self._app_dir = app_dir
        self._path = os.path.join(app_dir, self._FILE_NAME)
        os.makedirs(self._app_dir, exist_ok=True)

    def defaults(self) -> Dict[str, Any]:
        return deepcopy(self._DEFAULTS)

    def load(self) -> Dict[str, Any]:
        data = self.defaults()
        if not os.path.isfile(self._path):
            return data
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            log.warning("Erro ao carregar user_settings.json: %s", e)
            return data
        if isinstance(raw, dict):
            data = self._merge(data, raw)
        return self._sanitize(data)

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = self._sanitize(self._merge(self.defaults(), payload or {}))
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        current = self.load()
        current = self._merge(current, patch or {})
        return self.save(current)

    def _merge(self, base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge(result[key], value)
            else:
                result[key] = value
        return result

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = self.defaults()
        cleaned.update(data or {})

        cleaned["window_fullscreen"] = bool(cleaned.get("window_fullscreen", False))
        cleaned["window_maximized"] = bool(cleaned.get("window_maximized", False))
        cleaned["window_width"] = max(1024, min(3840, int(cleaned.get("window_width", WINDOW_WIDTH))))
        cleaned["window_height"] = max(600, min(2160, int(cleaned.get("window_height", WINDOW_HEIGHT))))
        cleaned["ui_scale"] = round(max(0.85, min(1.15, float(cleaned.get("ui_scale", 1.0)))), 2)
        cleaned["perf_mode"] = bool(cleaned.get("perf_mode", False))

        for key, default in (
            ("music_volume", 0.5),
            ("effects_volume", 0.8),
            ("narration_volume", 0.7),
            ("match_speed", 1.0),
        ):
            cleaned[key] = max(0.0, min(1.0 if key != "match_speed" else 8.0, float(cleaned.get(key, default))))
        if cleaned["match_speed"] not in (0.5, 1.0, 2.0, 4.0, 8.0):
            cleaned["match_speed"] = 1.0

        cleaned["narrator"] = str(cleaned.get("narrator", "") or "")
        cleaned["streamer_safe"] = bool(cleaned.get("streamer_safe", False))
        cleaned["menu_music"] = bool(cleaned.get("menu_music", True))
        cleaned["pre_match_music"] = bool(cleaned.get("pre_match_music", True))
        cleaned["auto_save"] = bool(cleaned.get("auto_save", True))
        cleaned["show_notifications"] = bool(cleaned.get("show_notifications", True))
        cleaned["animations"] = bool(cleaned.get("animations", True))

        difficulty = str(cleaned.get("difficulty", "normal") or "normal").lower()
        cleaned["difficulty"] = difficulty if difficulty in {"facil", "normal", "dificil", "lendario"} else "normal"
        return cleaned
