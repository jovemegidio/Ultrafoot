# -*- coding: utf-8 -*-
"""
Otimizador de assets para Ultrafoot — reduz drasticamente o tamanho do jogo.
Foco: PCs fracos.

Uso: python scripts/optimize_assets.py
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image
except ImportError:
    print("ERRO: Pillow não instalado. Execute: pip install Pillow")
    sys.exit(1)

BASE = Path(__file__).resolve().parent.parent

# ── Configurações de compressão ──
STADIUM_MAX_WIDTH = 1280       # Resolução máx de estádios (eram até 5272px)
STADIUM_MAX_HEIGHT = 720
STADIUM_JPEG_QUALITY = 70      # Qualidade JPEG (era ~95-100)

PLAYER_MAX_WIDTH = 200         # Fotos de jogadores — max 200px
PLAYER_MAX_HEIGHT = 200
PLAYER_JPEG_QUALITY = 65

MUSIC_BITRATE = "128k"         # Era 320kbps → 128kbps (suficiente para BGM)

# ═══════════════════════════════════════════════════════
#  1. COMPRIMIR IMAGENS DE ESTÁDIOS
# ═══════════════════════════════════════════════════════
def optimize_stadiums():
    stadiums_dir = BASE / "data" / "assets" / "stadiums"
    if not stadiums_dir.exists():
        print("  [SKIP] Pasta de estádios não encontrada")
        return

    files = list(stadiums_dir.rglob("*"))
    img_files = [f for f in files if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    total_before = sum(f.stat().st_size for f in img_files)
    saved = 0
    count = 0

    for f in img_files:
        try:
            original_size = f.stat().st_size
            img = Image.open(f)

            # Converter RGBA→RGB se necessário (para salvar como JPEG)
            if img.mode in ('RGBA', 'P', 'LA'):
                bg = Image.new('RGB', img.size, (20, 30, 20))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = bg

            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Redimensionar se necessário
            w, h = img.size
            if w > STADIUM_MAX_WIDTH or h > STADIUM_MAX_HEIGHT:
                img.thumbnail((STADIUM_MAX_WIDTH, STADIUM_MAX_HEIGHT), Image.LANCZOS)

            # Salvar como JPEG (converter PNGs para JPG)
            out_path = f.with_suffix('.jpg')
            img.save(out_path, 'JPEG', quality=STADIUM_JPEG_QUALITY, optimize=True)

            # Remover o PNG original se convertemos
            if f.suffix.lower() == '.png' and out_path != f:
                f.unlink()

            new_size = out_path.stat().st_size
            saved += (original_size - new_size)
            count += 1
        except Exception as e:
            print(f"    ERRO: {f.name}: {e}")

    total_after = total_before - saved
    print(f"  Estádios: {count} imagens comprimidas")
    print(f"  {total_before // (1024*1024)} MB → {total_after // (1024*1024)} MB (economia: {saved // (1024*1024)} MB)")


# ═══════════════════════════════════════════════════════
#  2. COMPRIMIR IMAGENS DE JOGADORES
# ═══════════════════════════════════════════════════════
def optimize_players():
    players_dir = BASE / "data" / "assets" / "players"
    if not players_dir.exists():
        print("  [SKIP] Pasta de jogadores não encontrada")
        return

    files = list(players_dir.rglob("*"))
    img_files = [f for f in files if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    total_before = sum(f.stat().st_size for f in img_files)
    saved = 0
    count = 0

    for f in img_files:
        try:
            original_size = f.stat().st_size
            img = Image.open(f)

            if img.mode in ('RGBA', 'P', 'LA'):
                bg = Image.new('RGB', img.size, (30, 30, 40))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = bg

            if img.mode != 'RGB':
                img = img.convert('RGB')

            w, h = img.size
            if w > PLAYER_MAX_WIDTH or h > PLAYER_MAX_HEIGHT:
                img.thumbnail((PLAYER_MAX_WIDTH, PLAYER_MAX_HEIGHT), Image.LANCZOS)

            out_path = f.with_suffix('.jpg')
            img.save(out_path, 'JPEG', quality=PLAYER_JPEG_QUALITY, optimize=True)

            if f.suffix.lower() == '.png' and out_path != f:
                f.unlink()

            new_size = out_path.stat().st_size
            saved += (original_size - new_size)
            count += 1
        except Exception as e:
            print(f"    ERRO: {f.name}: {e}")

    total_after = total_before - saved
    print(f"  Jogadores: {count} imagens comprimidas")
    print(f"  {total_before // (1024*1024)} MB → {total_after // (1024*1024)} MB (economia: {saved // (1024*1024)} MB)")


# ═══════════════════════════════════════════════════════
#  3. REDUZIR BITRATE DAS MÚSICAS (320kbps → 128kbps)
# ═══════════════════════════════════════════════════════
def optimize_music():
    music_dir = BASE / "music"
    if not music_dir.exists():
        print("  [SKIP] Pasta de música não encontrada")
        return

    # Verificar se ffmpeg existe
    if not shutil.which("ffmpeg"):
        print("  [SKIP] ffmpeg não encontrado — pule a compressão de música")
        return

    mp3_files = list(music_dir.glob("*.mp3"))
    total_before = sum(f.stat().st_size for f in mp3_files)
    saved = 0
    count = 0

    for f in mp3_files:
        try:
            original_size = f.stat().st_size
            tmp = f.with_suffix('.tmp.mp3')

            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(f), "-b:a", MUSIC_BITRATE, "-map_metadata", "0", str(tmp)],
                capture_output=True, timeout=60
            )

            if result.returncode == 0 and tmp.exists():
                new_size = tmp.stat().st_size
                if new_size < original_size:
                    f.unlink()
                    tmp.rename(f)
                    saved += (original_size - new_size)
                    count += 1
                else:
                    tmp.unlink()
            else:
                if tmp.exists():
                    tmp.unlink()
        except Exception as e:
            print(f"    ERRO música: {f.name}: {e}")
            if tmp.exists():
                tmp.unlink()

    total_after = total_before - saved
    print(f"  Música: {count} arquivos comprimidos")
    print(f"  {total_before // (1024*1024)} MB → {total_after // (1024*1024)} MB (economia: {saved // (1024*1024)} MB)")


# ═══════════════════════════════════════════════════════
#  4. CONVERTER WAV → MP3 (sons de efeito)
# ═══════════════════════════════════════════════════════
def optimize_sounds():
    sons_dir = BASE / "sons"
    if not sons_dir.exists():
        print("  [SKIP] Pasta de sons não encontrada")
        return

    if not shutil.which("ffmpeg"):
        print("  [SKIP] ffmpeg não encontrado")
        return

    wav_files = list(sons_dir.glob("*.wav"))
    if not wav_files:
        print("  [SKIP] Nenhum WAV encontrado")
        return

    total_before = sum(f.stat().st_size for f in wav_files)
    saved = 0
    count = 0

    for f in wav_files:
        try:
            original_size = f.stat().st_size
            mp3_path = f.with_suffix('.mp3')

            result = subprocess.run(
                ["ffmpeg", "-y", "-i", str(f), "-b:a", "192k", str(mp3_path)],
                capture_output=True, timeout=30
            )

            if result.returncode == 0 and mp3_path.exists():
                new_size = mp3_path.stat().st_size
                f.unlink()  # Remove WAV original
                saved += (original_size - new_size)
                count += 1
            else:
                if mp3_path.exists():
                    mp3_path.unlink()
        except Exception as e:
            print(f"    ERRO som: {f.name}: {e}")

    total_after = total_before - saved
    print(f"  Sons: {count} WAVs convertidos para MP3")
    print(f"  {total_before // (1024*1024)} MB → {total_after // (1024*1024)} MB (economia: {saved // (1024*1024)} MB)")


# ═══════════════════════════════════════════════════════
#  5. OTIMIZAR GIF E IMAGENS DA RAIZ
# ═══════════════════════════════════════════════════════
def optimize_root_images():
    # Converter o GIF animado grande para PNG estático (ou WEBP)
    gif_path = BASE / "Fundo II.gif"
    if gif_path.exists() and gif_path.stat().st_size > 1024 * 1024:
        try:
            img = Image.open(gif_path)
            # Pegar primeiro frame e salvar como PNG
            first_frame = img.copy().convert('RGB')
            png_path = BASE / "Fundo II.png"
            if not png_path.exists() or png_path.stat().st_size > gif_path.stat().st_size:
                first_frame.save(png_path, 'PNG', optimize=True)
            original_size = gif_path.stat().st_size
            gif_path.unlink()
            print(f"  Removido Fundo II.gif ({original_size // (1024*1024)} MB) — usando PNG estático")
        except Exception as e:
            print(f"  ERRO gif: {e}")

    # Comprimir PNGs grandes na raiz
    for name in ['Fundo.png', 'Fundo II.png', 'Fundo III.png']:
        fp = BASE / name
        if fp.exists() and fp.stat().st_size > 500 * 1024:
            try:
                original_size = fp.stat().st_size
                img = Image.open(fp)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Converter para JPEG comprimido
                jpg_path = fp.with_suffix('.jpg')
                img.save(jpg_path, 'JPEG', quality=80, optimize=True)
                new_size = jpg_path.stat().st_size
                if new_size < original_size:
                    fp.unlink()
                    print(f"  {name} → {jpg_path.name}: {original_size // 1024}KB → {new_size // 1024}KB")
                else:
                    jpg_path.unlink()
            except Exception as e:
                print(f"  ERRO {name}: {e}")


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  ULTRAFOOT — Otimizador de Assets para PCs Fracos")
    print("=" * 60)

    print("\n[1/5] Comprimindo estádios...")
    optimize_stadiums()

    print("\n[2/5] Comprimindo fotos de jogadores...")
    optimize_players()

    print("\n[3/5] Reduzindo bitrate das músicas (320→128 kbps)...")
    optimize_music()

    print("\n[4/5] Convertendo sons WAV→MP3...")
    optimize_sounds()

    print("\n[5/5] Otimizando imagens da raiz...")
    optimize_root_images()

    print("\n" + "=" * 60)
    print("  Otimização concluída!")
    print("  Execute 'python build_exe.py' para reconstruir o jogo.")
    print("=" * 60)
