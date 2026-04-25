"""Render the School Tool app-icon MSIX tile set.

Writes into msix/staging/Assets/, replacing the v1 MB placeholders.

Design:
  * Navy #185787 rounded-square chip
  * White "ST" monogram (School Tool) in a semibold sans serif
  * Supersampled 4× then LANCZOS-downscaled for crisp edges at 44×44

Run:  python3 assets/brand/render_app_tiles.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (24, 87, 135, 255)  # #185787
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)
CORNER_R_FRAC = 0.157  # matches Vurctne mark geometry

SS = 4  # supersampling factor
BRAND = "ST"
WORDMARK = "School Tool"

# Font candidates, picked in order of preference.
_SANS_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]


def _find_font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _SANS_BOLD_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size_px)
    return ImageFont.load_default()


def _rounded_square_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _draw_monogram(img: Image.Image, *, origin: tuple[int, int], chip_size: int, text: str) -> None:
    x0, y0 = origin
    d = ImageDraw.Draw(img)
    # Size monogram to fit the chip height at ~55% — tuned visually so 'ST'
    # sits comfortably with room around it at every tile size.
    target_h = int(round(chip_size * 0.55))
    size_px = target_h
    while size_px > 6:
        font = _find_font(size_px)
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if th <= target_h and tw <= chip_size * 0.72:
            break
        size_px -= 2
    font = _find_font(size_px)
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x0 + (chip_size - tw) // 2 - bbox[0]
    ty = y0 + (chip_size - th) // 2 - bbox[1]
    d.text((tx, ty), text, font=font, fill=WHITE)


def render_square(side: int, text: str = BRAND) -> Image.Image:
    S = side * SS
    big = Image.new("RGBA", (S, S), TRANSPARENT)
    mask = _rounded_square_mask(S, int(round(CORNER_R_FRAC * S)))
    navy_layer = Image.new("RGBA", (S, S), NAVY)
    big.paste(navy_layer, (0, 0), mask)
    _draw_monogram(big, origin=(0, 0), chip_size=S, text=text)
    return big.resize((side, side), Image.LANCZOS)


def render_wide(width: int, height: int) -> Image.Image:
    W, H = width * SS, height * SS
    img = Image.new("RGBA", (W, H), NAVY)

    # Left chip inside the navy background (chip is just the monogram — no inset rect).
    chip_side = int(round(H * 0.62))
    gap = int(round(W * 0.05))

    # Measure wordmark first to centre the pair.
    d_probe = ImageDraw.Draw(img)
    size_px = int(round(H * 0.32))
    font = _find_font(size_px)
    bbox = d_probe.textbbox((0, 0), WORDMARK, font=font)
    # Shrink if too wide
    side_pad = int(round(W * 0.05))
    max_word_w = W - side_pad - chip_side - gap - side_pad
    while (bbox[2] - bbox[0]) > max_word_w and size_px > 14:
        size_px -= 4
        font = _find_font(size_px)
        bbox = d_probe.textbbox((0, 0), WORDMARK, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    total_w = chip_side + gap + tw
    chip_x = (W - total_w) // 2
    chip_y = (H - chip_side) // 2
    _draw_monogram(img, origin=(chip_x, chip_y), chip_size=chip_side, text=BRAND)

    tx = chip_x + chip_side + gap - bbox[0]
    ty = (H - th) // 2 - bbox[1]
    ImageDraw.Draw(img).text((tx, ty), WORDMARK, font=font, fill=WHITE)

    return img.resize((width, height), Image.LANCZOS)


def render_splash(width: int, height: int) -> Image.Image:
    W, H = width * SS, height * SS
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    chip_side = int(round(H * 0.40))
    chip_x = (W - chip_side) // 2
    chip_y = int(round(H * 0.20))

    mask = _rounded_square_mask(chip_side, int(round(CORNER_R_FRAC * chip_side)))
    navy = Image.new("RGBA", (chip_side, chip_side), NAVY)
    img.paste(navy, (chip_x, chip_y), mask)
    _draw_monogram(img, origin=(chip_x, chip_y), chip_size=chip_side, text=BRAND)

    # Wordmark below
    size_px = int(round(H * 0.11))
    font = _find_font(size_px)
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), WORDMARK, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2 - bbox[0]
    ty = chip_y + chip_side + int(round(H * 0.07))
    d.text((tx, ty), WORDMARK, font=font, fill=NAVY)

    return img.resize((width, height), Image.LANCZOS)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out = repo_root / "msix" / "staging" / "Assets"
    out.mkdir(parents=True, exist_ok=True)
    tiles = {
        "Square44x44Logo.png": render_square(44),
        "Square71x71Logo.png": render_square(71),
        "Square150x150Logo.png": render_square(150),
        "StoreLogo.png": render_square(50),
        "Wide310x150Logo.png": render_wide(310, 150),
        "SplashScreen.png": render_splash(620, 300),
    }
    for name, img in tiles.items():
        img.save(out / name, "PNG", optimize=True)
        print(f"  wrote {name:<24s} {img.size}")


if __name__ == "__main__":
    main()
