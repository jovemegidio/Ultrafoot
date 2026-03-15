# -*- coding: utf-8 -*-
"""
Save integrity, backup rotation and lightweight recovery.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import shutil
import time
import zlib
from typing import Dict, List, Optional, Tuple

from config import BUILD_CHANNEL, GAME_VERSION, SAVES_DIR
from utils.logger import get_logger

log = get_logger(__name__)

_SAVE_HMAC_KEY = b"UF26_SAVE_INTEGRITY_" + hashlib.sha256(b"ultrafoot_save_2026").digest()[:16]


class SaveIntegrityService:
    """Handles checksums, backup rotation and restore of local saves."""

    def __init__(self, saves_dir: str = SAVES_DIR, max_backups: int = 5) -> None:
        self.saves_dir = saves_dir
        self.backups_dir = os.path.join(saves_dir, "_backups")
        self.max_backups = max(1, max_backups)
        os.makedirs(self.saves_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

    @staticmethod
    def _sanitize_name(nome: str) -> str:
        """Remove path separators and parent-dir references to prevent traversal."""
        nome = os.path.basename(nome)
        nome = nome.replace("..", "").replace("/", "").replace("\\", "")
        if not nome:
            raise ValueError("Nome de save inválido")
        return nome

    def _save_path(self, nome: str) -> str:
        nome = self._sanitize_name(nome)
        return os.path.join(self.saves_dir, nome + ".sav")

    def _meta_path(self, nome: str) -> str:
        nome = self._sanitize_name(nome)
        return os.path.join(self.saves_dir, nome + ".meta")

    def _payload_sha(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _compute_save_hmac(self, checksum: str, nome: str, payload_size: int) -> str:
        """HMAC that authenticates the save — cannot be recalculated without the key."""
        msg = f"{nome}|{checksum}|{payload_size}".encode("utf-8")
        return hmac_mod.new(_SAVE_HMAC_KEY, msg, hashlib.sha256).hexdigest()

    def _load_meta(self, nome: str, *, backup_meta_path: str = "") -> Dict:
        path = backup_meta_path or self._meta_path(nome)
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_meta(self, path: str, data: Dict) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _rotate_backups(self, nome: str) -> None:
        prefix = nome + "__"
        entries = []
        for fn in os.listdir(self.backups_dir):
            if fn.startswith(prefix) and fn.endswith(".sav"):
                full = os.path.join(self.backups_dir, fn)
                entries.append((os.path.getmtime(full), full))
        entries.sort(reverse=True)
        for _, sav_path in entries[self.max_backups :]:
            meta_path = sav_path[:-4] + ".meta"
            try:
                os.remove(sav_path)
            except OSError:
                pass
            if os.path.isfile(meta_path):
                try:
                    os.remove(meta_path)
                except OSError:
                    pass

    def _create_backup_if_needed(self, nome: str) -> None:
        sav_path = self._save_path(nome)
        meta_path = self._meta_path(nome)
        if not os.path.isfile(sav_path):
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_base = os.path.join(self.backups_dir, f"{nome}__{stamp}")
        shutil.copy2(sav_path, backup_base + ".sav")
        if os.path.isfile(meta_path):
            shutil.copy2(meta_path, backup_base + ".meta")
        self._rotate_backups(nome)

    def save(self, nome: str, payload: bytes, meta: Dict) -> Dict:
        self._create_backup_if_needed(nome)

        blob = zlib.compress(payload, level=1)
        checksum = self._payload_sha(payload)
        sav_path = self._save_path(nome)
        tmp_path = sav_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(blob)
        os.replace(tmp_path, sav_path)

        meta_payload = {
            "nome": nome,
            "checksum_sha256": checksum,
            "hmac": self._compute_save_hmac(checksum, nome, len(payload)),
            "payload_size": len(payload),
            "compressed_size": len(blob),
            "format_version": 2,
            "game_version": GAME_VERSION,
            "build_channel": BUILD_CHANNEL,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **meta,
        }
        self._write_meta(self._meta_path(nome), meta_payload)
        return meta_payload

    def validate(self, nome: str) -> Dict:
        sav_path = self._save_path(nome)
        if not os.path.isfile(sav_path):
            return {"ok": False, "error": "save_not_found", "nome": nome}

        meta = self._load_meta(nome)
        backups = len(self.list_backups(nome))
        try:
            with open(sav_path, "rb") as f:
                blob = f.read()
            payload = zlib.decompress(blob)
        except Exception as e:
            return {
                "ok": False,
                "error": "decompress_failed",
                "nome": nome,
                "detalhe": str(e),
                "backups": backups,
                "updated_at": meta.get("updated_at", ""),
                "game_version": meta.get("game_version", ""),
            }

        checksum = self._payload_sha(payload)
        checksum_meta = meta.get("checksum_sha256", "")
        ok = not checksum_meta or checksum_meta == checksum
        # Verify HMAC if present (format_version >= 2)
        stored_hmac = meta.get("hmac", "")
        if ok and stored_hmac:
            expected_hmac = self._compute_save_hmac(checksum, nome, len(payload))
            if not hmac_mod.compare_digest(stored_hmac, expected_hmac):
                ok = False
        return {
            "ok": ok,
            "nome": nome,
            "checksum_atual": checksum,
            "checksum_meta": checksum_meta,
            "backups": backups,
            "updated_at": meta.get("updated_at", ""),
            "game_version": meta.get("game_version", ""),
            "payload_size": len(payload),
            "error": "" if ok else "checksum_mismatch",
        }

    def load(self, nome: str, attempt_recovery: bool = True) -> Tuple[bytes, Dict]:
        sav_path = self._save_path(nome)
        if not os.path.isfile(sav_path):
            raise FileNotFoundError(nome)

        validation = self.validate(nome)
        if validation.get("ok"):
            with open(sav_path, "rb") as f:
                return zlib.decompress(f.read()), validation

        if attempt_recovery:
            restored = self.restore_latest_backup(nome)
            if restored.get("ok"):
                validation = self.validate(nome)
                if validation.get("ok"):
                    with open(sav_path, "rb") as f:
                        payload = zlib.decompress(f.read())
                    validation["recovered_from_backup"] = restored.get("backup")
                    return payload, validation

        raise ValueError(validation.get("error", "invalid_save"))

    def list_backups(self, nome: str) -> List[Dict]:
        prefix = nome + "__"
        backups = []
        for fn in os.listdir(self.backups_dir):
            if not fn.startswith(prefix) or not fn.endswith(".sav"):
                continue
            sav_path = os.path.join(self.backups_dir, fn)
            meta_path = sav_path[:-4] + ".meta"
            meta = self._load_meta(nome, backup_meta_path=meta_path)
            backups.append(
                {
                    "backup": os.path.basename(sav_path),
                    "path": sav_path,
                    "updated_at": meta.get("updated_at", ""),
                    "game_version": meta.get("game_version", ""),
                    "mtime": os.path.getmtime(sav_path),
                }
            )
        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return backups

    def restore_latest_backup(self, nome: str) -> Dict:
        backups = self.list_backups(nome)
        if not backups:
            return {"ok": False, "error": "backup_not_found"}
        chosen = backups[0]
        sav_src = chosen["path"]
        meta_src = sav_src[:-4] + ".meta"
        shutil.copy2(sav_src, self._save_path(nome))
        if os.path.isfile(meta_src):
            shutil.copy2(meta_src, self._meta_path(nome))
        return {"ok": True, "backup": os.path.basename(sav_src)}

    def delete(self, nome: str, *, include_backups: bool = True) -> Dict:
        removed = False
        sav_path = self._save_path(nome)
        meta_path = self._meta_path(nome)
        if os.path.isfile(sav_path):
            os.remove(sav_path)
            removed = True
        if os.path.isfile(meta_path):
            os.remove(meta_path)

        removed_backups = 0
        if include_backups:
            for backup in self.list_backups(nome):
                try:
                    os.remove(backup["path"])
                    removed_backups += 1
                except OSError:
                    pass
                meta_backup = backup["path"][:-4] + ".meta"
                if os.path.isfile(meta_backup):
                    try:
                        os.remove(meta_backup)
                    except OSError:
                        pass
        return {"ok": removed, "removed_backups": removed_backups}
