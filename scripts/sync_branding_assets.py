from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_ICON = BASE_DIR / "Icone.png"
ROOT_ICO = BASE_DIR / "Icone.ico"
TAURI_ICONS_DIR = BASE_DIR / "src-tauri" / "icons"


def _prepare_square(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fitted = ImageOps.contain(image, (size, size), Image.Resampling.LANCZOS)
    x = (size - fitted.width) // 2
    y = (size - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def main() -> None:
    if not SOURCE_ICON.exists():
        raise SystemExit(f"Icon source not found: {SOURCE_ICON}")

    TAURI_ICONS_DIR.mkdir(parents=True, exist_ok=True)

    image = Image.open(SOURCE_ICON).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    root_icon = _prepare_square(image, 256)
    for icon_path in (ROOT_ICO, TAURI_ICONS_DIR / "icon.ico"):
        try:
            if icon_path.exists():
                icon_path.unlink()
        except OSError:
            pass
        root_icon.save(icon_path, format="ICO", sizes=sizes)

    for size, filename in (
        (32, "32x32.png"),
        (128, "128x128.png"),
        (256, "128x128@2x.png"),
    ):
        _prepare_square(image, size).save(TAURI_ICONS_DIR / filename, format="PNG")

    print("Branding assets synchronized from Icone.png")


if __name__ == "__main__":
    main()
