#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Importa metadados do BID/CBF utilizáveis offline.

O BID expõe os códigos dos clubes sem captcha, mas a busca completa de atletas
depende de captcha e de IDs de atletas. Por isso o fluxo suportado aqui é:

1. Atualizar o registro local de clubes do BID.
2. Ler um arquivo opcional `data/seeds/bid_player_map.json` com códigos de atletas.
3. Baixar as fotos dos atletas mapeados para `data/assets/players/`.
4. Atualizar `data/seeds/player_photo_overrides.json` para o jogo exibir os rostos.

Formato esperado de `bid_player_map.json`:
{
  "Flamengo": {
    "Pedro": {"codigo_atleta": 123456},
    "Arrascaeta": {"codigo_atleta": 654321}
  }
}
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS_DIR = os.path.join(BASE_DIR, "data", "seeds")
ASSETS_DIR = os.path.join(BASE_DIR, "data", "assets", "players")
CLUB_REGISTRY = os.path.join(SEEDS_DIR, "bid_club_registry.json")
PLAYER_MAP = os.path.join(SEEDS_DIR, "bid_player_map.json")
PHOTO_OVERRIDES = os.path.join(SEEDS_DIR, "player_photo_overrides.json")

BID_HOME = "https://bid.cbf.com.br/"
BID_CLUBS = "https://bid.cbf.com.br/combo-clubes-json"
BID_PHOTO = "https://bid.cbf.com.br/foto-atleta/{codigo}"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "jogador"


def make_opener():
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    opener.addheaders = [("User-Agent", "UltrafootAssetImporter/1.0")]
    opener.open(BID_HOME, timeout=30).read()
    xsrf = ""
    for cookie in cookies:
        if cookie.name == "XSRF-TOKEN":
            xsrf = urllib.parse.unquote(cookie.value)
            break
    opener.addheaders = [
        ("User-Agent", "UltrafootAssetImporter/1.0"),
        ("X-XSRF-TOKEN", xsrf),
        ("X-Requested-With", "XMLHttpRequest"),
        ("Referer", BID_HOME),
    ]
    return opener


def fetch_club_registry(opener) -> list[dict]:
    payload = opener.open(BID_CLUBS, data=b"", timeout=30).read().decode("utf-8")
    data = json.loads(payload)
    data.sort(key=lambda item: (item.get("uf") or "", item.get("clube") or ""))
    return data


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_player_photos(opener) -> int:
    player_map = load_json(PLAYER_MAP, {})
    if not isinstance(player_map, dict) or not player_map:
        return 0

    overrides = load_json(PHOTO_OVERRIDES, {})
    imported = 0
    for clube, jogadores in player_map.items():
        if not isinstance(jogadores, dict):
            continue
        overrides.setdefault(clube, {})
        club_dir = os.path.join(ASSETS_DIR, slugify(clube))
        os.makedirs(club_dir, exist_ok=True)
        for nome, meta in jogadores.items():
            if not isinstance(meta, dict):
                continue
            codigo = str(meta.get("codigo_atleta") or "").strip()
            if not codigo:
                continue
            dest = os.path.join(club_dir, slugify(nome) + ".jpg")
            if not os.path.exists(dest):
                raw = opener.open(BID_PHOTO.format(codigo=codigo), timeout=30).read()
                if raw:
                    with open(dest, "wb") as f:
                        f.write(raw)
            if os.path.exists(dest):
                rel = os.path.relpath(dest, BASE_DIR).replace("\\", "/")
                overrides[clube][nome] = rel
                imported += 1
    save_json(PHOTO_OVERRIDES, overrides)
    return imported


def main() -> None:
    opener = make_opener()
    clubs = fetch_club_registry(opener)
    save_json(CLUB_REGISTRY, clubs)
    imported = import_player_photos(opener)
    print(f"Registro de clubes BID atualizado: {len(clubs)} clubes")
    print(f"Fotos importadas: {imported}")


if __name__ == "__main__":
    main()
