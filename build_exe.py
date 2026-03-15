# -*- coding: utf-8 -*-
"""
Build script para gerar o executável standalone do Ultrafoot.
Uso: python build_exe.py
"""
import os
import shutil
import subprocess
import sys
import time

import PyInstaller.__main__

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD_TOKEN = time.strftime("%Y%m%d_%H%M%S")
PYI_RELEASE_ROOT = os.path.join(BASE, "release_build")
PYI_DISTPATH = os.path.join(PYI_RELEASE_ROOT, BUILD_TOKEN)
PYI_APP_DIST = os.path.join(PYI_DISTPATH, "Ultrafoot")
PYI_WORKPATH = os.path.join(BASE, "build", "pyinstaller_runs", BUILD_TOKEN)
PYI_SPECPATH = os.path.join(BASE, "build", "spec")
LATEST_BUILD_FILE = os.path.join(PYI_RELEASE_ROOT, "latest_build.txt")
MIRROR_DIST_ROOT = os.path.join(BASE, "dist", "Ultrafoot")
MIRROR_BACKUP_ROOT = os.path.join(BASE, "dist")


def _sync_branding_assets() -> None:
    script = os.path.join(BASE, "scripts", "sync_branding_assets.py")
    if os.path.exists(script):
        subprocess.run([sys.executable, script], cwd=BASE, check=False)


def _sync_frontend_assets() -> None:
    """Sincroniza o frontend raiz com as copias usadas por Tauri e pelo dist do PyInstaller."""
    sync_pairs = [
        (os.path.join(BASE, "index.html"), os.path.join(BASE, "web", "index.html")),
        (
            os.path.join(BASE, "Tracker", "ultrafoot_match_center.css"),
            os.path.join(BASE, "web", "Tracker", "ultrafoot_match_center.css"),
        ),
        (
            os.path.join(BASE, "Tracker", "ultrafoot_match_center.js"),
            os.path.join(BASE, "web", "Tracker", "ultrafoot_match_center.js"),
        ),
        (os.path.join(BASE, "index.html"), os.path.join(PYI_APP_DIST, "_internal", "index.html")),
        (
            os.path.join(BASE, "Tracker", "ultrafoot_match_center.css"),
            os.path.join(PYI_APP_DIST, "_internal", "Tracker", "ultrafoot_match_center.css"),
        ),
        (
            os.path.join(BASE, "Tracker", "ultrafoot_match_center.js"),
            os.path.join(PYI_APP_DIST, "_internal", "Tracker", "ultrafoot_match_center.js"),
        ),
    ]
    for src, dest in sync_pairs:
        if not os.path.exists(src):
            continue
        dest_dir = os.path.dirname(dest)
        if os.path.isdir(dest_dir):
            shutil.copy2(src, dest)
            print(f"Synced frontend asset -> {os.path.relpath(dest, BASE)}")


def _write_latest_build_marker() -> None:
    os.makedirs(PYI_RELEASE_ROOT, exist_ok=True)
    with open(LATEST_BUILD_FILE, "w", encoding="utf-8") as fp:
        fp.write(_resolve_app_dist())


def _resolve_app_dist() -> str:
    if os.path.isdir(PYI_APP_DIST):
        return PYI_APP_DIST
    if os.path.isdir(PYI_DISTPATH):
        subdirs = [
            os.path.join(PYI_DISTPATH, name)
            for name in os.listdir(PYI_DISTPATH)
            if os.path.isdir(os.path.join(PYI_DISTPATH, name))
        ]
        if subdirs:
            return max(subdirs, key=os.path.getmtime)
    return PYI_APP_DIST


def _sync_tree_in_place(src_root: str, dst_root: str) -> list[str]:
    locked_files: list[str] = []
    for root, dirs, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        target_root = dst_root if rel == "." else os.path.join(dst_root, rel)
        os.makedirs(target_root, exist_ok=True)
        for dirname in dirs:
            os.makedirs(os.path.join(target_root, dirname), exist_ok=True)
        for filename in files:
            src_file = os.path.join(root, filename)
            dst_file = os.path.join(target_root, filename)
            try:
                shutil.copy2(src_file, dst_file)
            except PermissionError:
                locked_files.append(dst_file)
    return locked_files


def _mirror_build_to_dist(app_dist: str) -> bool:
    """Espelha a build mais recente para dist/Ultrafoot, caminho usado no fluxo manual."""
    if not os.path.isdir(app_dist):
        print(f"Warning: build output not found for mirroring: {app_dist}")
        return False

    if os.path.isdir(MIRROR_DIST_ROOT):
        try:
            backup_name = f"Ultrafoot_backup_{BUILD_TOKEN}"
            backup_path = os.path.join(MIRROR_BACKUP_ROOT, backup_name)
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            shutil.move(MIRROR_DIST_ROOT, backup_path)
            print(f"Backed up previous dist -> {os.path.relpath(backup_path, BASE)}")
        except PermissionError as exc:
            print(f"Warning: dist mirror is in use and could not be moved ({exc}). Trying in-place sync...")
            locked_files = _sync_tree_in_place(app_dist, MIRROR_DIST_ROOT)
            if locked_files:
                preview = ", ".join(os.path.relpath(path, BASE) for path in locked_files[:5])
                suffix = " ..." if len(locked_files) > 5 else ""
                print(
                    "Warning: some files could not be refreshed because they are open: "
                    f"{preview}{suffix}"
                )
            src_exe = os.path.join(app_dist, "Ultrafoot 26.exe")
            dst_exe = os.path.join(MIRROR_DIST_ROOT, "Ultrafoot 26.exe")
            exe_synced = (
                os.path.exists(src_exe)
                and os.path.exists(dst_exe)
                and os.path.getsize(src_exe) == os.path.getsize(dst_exe)
                and int(os.path.getmtime(src_exe)) <= int(os.path.getmtime(dst_exe))
            )
            if exe_synced:
                print(f"Mirrored build in-place -> {os.path.relpath(MIRROR_DIST_ROOT, BASE)}")
            else:
                print("Warning: main executable was not refreshed in dist/Ultrafoot. Close the app and rerun the build.")
            return exe_synced

    shutil.copytree(app_dist, MIRROR_DIST_ROOT)
    print(f"Mirrored build -> {os.path.relpath(MIRROR_DIST_ROOT, BASE)}")
    return True

# ── Arquivos de dev/build a excluir do bundle ──
_EXCLUDE_SEEDS = {"all_teams.json"}  # ~10 MB, só usada por tools/
_EXCLUDE_TRACKER = {"radar.html", "radar_backup.html"}  # não usados em runtime

# Diretórios de dados para incluir
datas = [
    (os.path.join(BASE, "index.html"), "."),
    (os.path.join(BASE, "splash.html"), "."),
    (os.path.join(BASE, "three.min.js"), "."),
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
    (os.path.join(BASE, "data", "assets", "players"), os.path.join("data", "assets", "players")),
]

# Add optional image assets
for img in ["Logo - UF26 II.png", "Logo - UF26 III.png", "Fundo II.gif", "Fundo.png", "Icone.png", "Logo - Japa Rebranding.png"]:
    p = os.path.join(BASE, img)
    if os.path.exists(p):
        datas.append((p, "."))

# Pacotes Python internos do projeto
hidden_imports = [
    "config",
    "core",
    "core.enums",
    "core.models",
    "core.constants",
    "core.exceptions",
    "managers",
    "managers.game_manager",
    "managers.competition_manager",
    "services",
    "services.scout_service",
    "services.ai_service",
    "services.music_manager",
    "services.press_conference",
    "services.achievements_awards",
    "services.inbox_engine",
    "services.licensing_engine",
    "services.advanced_systems",
    "services.ffp_engine",
    "services.world_rankings",
    "services.hall_of_fame",
    "engine",
    "engine.match_engine",
    "engine.season_engine",
    "engine.transfer_engine",
    "fantasy",
    "fantasy.manager",
    "fantasy.scoring",
    "fantasy.models",
    "save_system",
    "save_system.save_manager",
    "utils",
    "utils.logger",
    "utils.helpers",
    "data",
    "data.seeds",
    "data.seeds.seed_loader",
    "orjson",
    "services.discord_rpc",
    "pypresence",
]

# Incluir apenas arquivos úteis de Tracker (CSS/JS, não HTMLs de dev)
for tf in os.listdir(os.path.join(BASE, "Tracker")):
    if tf in _EXCLUDE_TRACKER:
        continue
    src = os.path.join(BASE, "Tracker", tf)
    if os.path.isfile(src):
        datas.append((src, "Tracker"))

# Build arguments
_sync_branding_assets()
_sync_frontend_assets()  # Garante que o frontend empacotado use os assets mais recentes

args = [
    os.path.join(BASE, "desktop_app.py"),
    "--name=Ultrafoot 26",
    "--onedir",
    "--windowed",
    "--noconfirm",
    "--clean",
    f"--distpath={PYI_DISTPATH}",
    f"--workpath={PYI_WORKPATH}",
    f"--specpath={PYI_SPECPATH}",
    "--collect-all=webview",
]

# ── Excluir módulos pesados desnecessários (reduz ~50-80 MB) ──
for mod in [
    "tkinter", "_tkinter", "customtkinter",
    "matplotlib", "numpy", "scipy", "pandas",
    "pytest", "_pytest", "unittest",
    "PIL.ImageTk", "pydoc", "doctest",
    "lib2to3", "xmlrpc", "curses",
]:
    args.append(f"--exclude-module={mod}")

# Add data files
for src, dest in datas:
    args.append(f"--add-data={src};{dest}")

# Add hidden imports
for hi in hidden_imports:
    args.append(f"--hidden-import={hi}")

# Add icon — convert Icone.png to .ico if needed
icon_ico = os.path.join(BASE, "Icone.ico")
icon_png = os.path.join(BASE, "Icone.png")
if not os.path.exists(icon_ico) and os.path.exists(icon_png):
    try:
        from PIL import Image
        img = Image.open(icon_png)
        img.save(icon_ico, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        print(f"Converted {icon_png} -> {icon_ico}")
    except Exception as e:
        print(f"Warning: could not convert PNG to ICO: {e}")
if os.path.exists(icon_ico):
    args.append(f"--icon={icon_ico}")

print("Starting PyInstaller build...")
print(f"Args: {len(args)} parameters")
PyInstaller.__main__.run(args)
APP_DIST = _resolve_app_dist()

# ── Pós-build: remover arquivos desnecessários do dist ──
_dist_seeds = os.path.join(APP_DIST, "_internal", "data", "seeds")
if os.path.isdir(_dist_seeds):
    for ex in _EXCLUDE_SEEDS:
        fp = os.path.join(_dist_seeds, ex)
        if os.path.exists(fp):
            os.remove(fp)
            print(f"Removed unnecessary seed: {ex} (saves ~10 MB)")

# Sync pós-build: garantir que dist/ tenha os assets mais recentes do frontend
_sync_frontend_assets()
_write_latest_build_marker()
mirrored = _mirror_build_to_dist(APP_DIST)
if not mirrored:
    print("Build completed, but dist/Ultrafoot was not fully refreshed.")

print(f"\nBuild complete! Check {APP_DIST}")
