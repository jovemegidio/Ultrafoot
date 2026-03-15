# -*- coding: utf-8 -*-
"""
Build script para gerar o sidecar do Tauri (brasfoot-server EXE).
Uso: python build_sidecar.py

O executável gerado é colocado em src-tauri/binaries/ com o nome
que o Tauri espera: brasfoot-server-x86_64-pc-windows-msvc.exe
"""
import os
import shutil
import sys

import PyInstaller.__main__

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BASE, "src-tauri", "binaries")


def _sync_index_html() -> None:
    """Copia index.html raiz para web/ (Tauri) antes do build."""
    src = os.path.join(BASE, "index.html")
    dest = os.path.join(BASE, "web", "index.html")
    if os.path.exists(src) and os.path.isdir(os.path.dirname(dest)):
        shutil.copy2(src, dest)
        print(f"Synced index.html -> web/index.html")


_sync_index_html()

# Seeds que não precisam ir no sidecar (dev-only)
_EXCLUDE_SEEDS = {"all_teams.json"}

# Dados embarcados no sidecar (o servidor HTTP serve esses arquivos)
datas = [
    (os.path.join(BASE, "index.html"), "."),
    (os.path.join(BASE, "splash.html"), "."),
    (os.path.join(BASE, "data", "seeds"), os.path.join("data", "seeds")),
    (os.path.join(BASE, "teams", "escudos"), os.path.join("teams", "escudos")),
    (os.path.join(BASE, "teams", "camisas"), os.path.join("teams", "camisas")),
    (os.path.join(BASE, "teams", "camisas2"), os.path.join("teams", "camisas2")),
    (os.path.join(BASE, "teams", "camisas3"), os.path.join("teams", "camisas3")),
    (os.path.join(BASE, "sons"), "sons"),
    (os.path.join(BASE, "music"), "music"),
    (os.path.join(BASE, "trofeus"), "trofeus"),
    (os.path.join(BASE, "selecoes"), "selecoes"),
    (os.path.join(BASE, "conf_estadual"), "conf_estadual"),
    (os.path.join(BASE, "conf_ligas_nacionais"), "conf_ligas_nacionais"),
    (os.path.join(BASE, "Tracker", "ultrafoot_match_center.css"), "Tracker"),
    (os.path.join(BASE, "Tracker", "ultrafoot_match_center.js"), "Tracker"),
]

# Imagens opcionais
for img in ["Logo - UF26 III.png", "Fundo II.gif", "Fundo.png", "Icone.png"]:
    p = os.path.join(BASE, img)
    if os.path.exists(p):
        datas.append((p, "."))

# Hidden imports — mesmos do build_exe.py
hidden_imports = [
    "config",
    "core", "core.enums", "core.models", "core.constants", "core.exceptions",
    "managers", "managers.game_manager", "managers.competition_manager",
    "services", "services.scout_service", "services.ai_service",
    "services.music_manager", "services.press_conference",
    "services.achievements_awards", "services.inbox_engine",
    "services.licensing_engine", "services.advanced_systems",
    "services.ffp_engine", "services.world_rankings", "services.hall_of_fame",
    "engine", "engine.match_engine", "engine.season_engine", "engine.transfer_engine",
    "fantasy", "fantasy.manager", "fantasy.scoring", "fantasy.models",
    "save_system", "save_system.save_manager",
    "utils", "utils.logger", "utils.helpers",
    "data", "data.seeds", "data.seeds.seed_loader",
    "desktop_app",
    "orjson",
    "services.discord_rpc",
    "pypresence",
]

args = [
    os.path.join(BASE, "server.py"),
    "--name=brasfoot-server",
    "--onefile",
    "--console",          # sidecar precisa stdout para comunicar porta
    "--noconfirm",
    "--clean",
    f"--distpath={os.path.join(BASE, 'build', 'sidecar')}",
    f"--workpath={os.path.join(BASE, 'build', 'sidecar_work')}",
    f"--specpath={BASE}",
]

# Excluir módulos pesados
for mod in [
    "tkinter", "_tkinter", "customtkinter",
    "matplotlib", "numpy", "scipy", "pandas",
    "pytest", "_pytest", "unittest",
    "PIL", "Pillow", "pydoc", "doctest",
    "lib2to3", "xmlrpc", "curses",
]:
    args.append(f"--exclude-module={mod}")

for src, dest in datas:
    args.append(f"--add-data={src};{dest}")

for hi in hidden_imports:
    args.append(f"--hidden-import={hi}")

# Icon
icon_ico = os.path.join(BASE, "Icone.ico")
if os.path.exists(icon_ico):
    args.append(f"--icon={icon_ico}")

print("Building sidecar (brasfoot-server)...")
print(f"Args: {len(args)} parameters")
PyInstaller.__main__.run(args)

# Mover o EXE para src-tauri/binaries/ com o nome correto
src_exe = os.path.join(BASE, "build", "sidecar", "brasfoot-server.exe")
dst_exe = os.path.join(TARGET, "brasfoot-server-x86_64-pc-windows-msvc.exe")

if os.path.exists(src_exe):
    os.makedirs(TARGET, exist_ok=True)
    shutil.copy2(src_exe, dst_exe)
    size_mb = os.path.getsize(dst_exe) / (1024 * 1024)
    print(f"\nSidecar built: {dst_exe}")
    print(f"Size: {size_mb:.1f} MB")
else:
    print("\nERROR: sidecar build failed — EXE not found")
    sys.exit(1)

print("\nNext step: cd src-tauri && cargo tauri build")
