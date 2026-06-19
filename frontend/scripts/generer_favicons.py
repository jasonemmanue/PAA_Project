"""Génère favicon.ico (multi-tailles) et apple-touch-icon.png à partir du
logo HACKATONIA. À relancer si le logo change.

Sortie :
  - frontend/app/favicon.ico        (tailles 16, 32, 48 dans un ICO)
  - frontend/public/apple-touch-icon.png  (180x180)
  - frontend/public/icon-192.png    (PWA : 192x192)
  - frontend/public/icon-512.png    (PWA : 512x512)
"""

from pathlib import Path
from PIL import Image, ImageOps

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "public" / "logo-hackathon.jpg"
ICO_DEST = RACINE / "app" / "favicon.ico"
APPLE_DEST = RACINE / "public" / "apple-touch-icon.png"
PWA_192 = RACINE / "public" / "icon-192.png"
PWA_512 = RACINE / "public" / "icon-512.png"

TAILLES_ICO = [(16, 16), (32, 32), (48, 48)]


def carre(image: Image.Image, fond=(11, 37, 69, 255)) -> Image.Image:
    """Recadre l'image en carré centré, fond bleu marine PAA si transparence."""
    image = image.convert("RGBA")
    cote = max(image.size)
    canevas = Image.new("RGBA", (cote, cote), fond)
    offset = ((cote - image.width) // 2, (cote - image.height) // 2)
    canevas.paste(image, offset, image)
    return canevas


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Logo introuvable : {SOURCE}")

    logo = Image.open(SOURCE)
    print(f"Source : {SOURCE.name} ({logo.size[0]}x{logo.size[1]}, {logo.mode})")
    base = carre(logo)

    # 1) favicon.ico multi-tailles (Pillow embarque toutes les tailles dans un seul ICO)
    base.save(ICO_DEST, format="ICO", sizes=TAILLES_ICO)
    print(f"OK {ICO_DEST.relative_to(RACINE)} (tailles : {TAILLES_ICO})")

    # 2) apple-touch-icon.png 180x180
    base.resize((180, 180), Image.LANCZOS).save(APPLE_DEST, format="PNG")
    print(f"OK {APPLE_DEST.relative_to(RACINE)} (180x180)")

    # 3) Icônes PWA (utiles si on ajoute un manifest.json plus tard)
    base.resize((192, 192), Image.LANCZOS).save(PWA_192, format="PNG")
    print(f"OK {PWA_192.relative_to(RACINE)} (192x192)")
    base.resize((512, 512), Image.LANCZOS).save(PWA_512, format="PNG")
    print(f"OK {PWA_512.relative_to(RACINE)} (512x512)")


if __name__ == "__main__":
    main()
