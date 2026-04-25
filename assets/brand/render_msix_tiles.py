"""Render the MSIX tile PNG set from the Vurctne brand spec.

Run:  python3 render_msix_tiles.py

Outputs in the current folder:
  Square44x44Logo.png       44 x 44   — app-list icon, taskbar
  Square71x71Logo.png       71 x 71   — small tile
  Square150x150Logo.png     150 x 150 — medium tile (default)
  Wide310x150Logo.png       310 x 150 — wide tile
  StoreLogo.png             50 x 50   — MS Store listing thumbnail
  SplashScreen.png          620 x 300 — splash on app launch

Design:
  * Navy #185787 rounded-square chip
  * White V monogram, two strokes meeting at a single point
  * Corner radius ≈ 15.7 % of chip side (matches vurctne_mark.svg)
  * Supersampled 4x then downscaled with LANCZOS for crisp edges
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

NAVY = (24, 87, 135, 255)          # #185787
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

# Normalised geometry (0-1 inside the chip):
#   chip corner radius = 0.157
#   V left apex       = (0.260, 0.243)
#   V bottom apex     = (0.500, 0.800)
#   V right apex      = (0.740, 0.243)
#   V stroke width    = 0.100
V_LEFT    = (0.260, 0.243)
V_BOTTOM  = (0.500, 0.800)
V_RIGHT   = (0.740, 0.243)
V_STROKE  = 0.100
CORNER_R  = 0.157

SS = 4   # 4x supersampling


def _rounded_square_mask(size: int, radius: int) -> Image.Image:
    """Alpha mask for a rounded square."""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _draw_v_on(img: Image.Image, *, chip_origin: tuple[int, int], chip_size: int) -> None:
    """Rasterise the V monogram onto ``img`` inside the given chip area."""
    x0, y0 = chip_origin
    # Stroke caps are round; draw as two fat lines then add round end-caps via filled circles.
    w = int(round(V_STROKE * chip_size))
    left   = (int(round(x0 + V_LEFT[0]   * chip_size)), int(round(y0 + V_LEFT[1]   * chip_size)))
    bottom = (int(round(x0 + V_BOTTOM[0] * chip_size)), int(round(y0 + V_BOTTOM[1] * chip_size)))
    right  = (int(round(x0 + V_RIGHT[0]  * chip_size)), int(round(y0 + V_RIGHT[1]  * chip_size)))
    d = ImageDraw.Draw(img)
    d.line([left, bottom], fill=WHITE, width=w)
    d.line([bottom, right], fill=WHITE, width=w)
    r = w // 2
    for cx, cy in (left, bottom, right):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)


def render_square(side: int) -> Image.Image:
    """Return an RGBA PNG of the navy chip + white V at the given side length."""
    S = side * SS
    big = Image.new("RGBA", (S, S), TRANSPARENT)
    mask = _rounded_square_mask(S, int(round(CORNER_R * S)))
    navy_layer = Image.new("RGBA", (S, S), NAVY)
    big.paste(navy_layer, (0, 0), mask)
    _draw_v_on(big, chip_origin=(0, 0), chip_size=S)
    return big.resize((side, side), Image.LANCZOS)


def render_wide(width: int, height: int, *, chip_frac: float = 0.62,
                wordmark: str = "Vurctne", pad_left_frac: float = 0.05) -> Image.Image:
    """Return an RGBA PNG with the navy background, V chip, and wordmark.

    Auto-sizes the wordmark so it fits the available horizontal space, then
    nudges chip and wordmark so the pair is horizontally centred in the tile.
    """
    W, H = width * SS, height * SS
    img = Image.new("RGBA", (W, H), NAVY)

    chip_side = int(round(H * chip_frac))

    # Pick a font size that keeps the wordmark inside the tile.
    try:
        from PIL import ImageFont
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
        ]
        font_path = next((p for p in font_candidates if Path(p).exists()), None)
        if font_path is None:
            from PIL import ImageFont as _IF
            font = _IF.load_default()
            tw = th = 0
            bbox = (0, 0, 0, 0)
        else:
            d_probe = ImageDraw.Draw(img)
            gap = int(round(W * 0.05))
            side_pad = int(round(W * pad_left_frac))
            target_max_w = W - side_pad - chip_side - gap - side_pad
            size_px = int(round(H * 0.34))
            font = ImageFont.truetype(font_path, size_px)
            bbox = d_probe.textbbox((0, 0), wordmark, font=font)
            while (bbox[2] - bbox[0]) > target_max_w and size_px > 12:
                size_px -= 4
                font = ImageFont.truetype(font_path, size_px)
                bbox = d_probe.textbbox((0, 0), wordmark, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        from PIL import ImageFont as _IF
        font = _IF.load_default()
        tw = th = 0
        bbox = (0, 0, 0, 0)

    # Centre the chip+wordmark pair horizontally.
    gap = int(round(W * 0.05))
    total_w = chip_side + gap + tw
    chip_x = (W - total_w) // 2
    chip_y = (H - chip_side) // 2
    _draw_v_on(img, chip_origin=(chip_x, chip_y), chip_size=chip_side)

    if tw:
        d = ImageDraw.Draw(img)
        tx = chip_x + chip_side + gap - bbox[0]
        ty = (H - th) // 2 - bbox[1]
        d.text((tx, ty), wordmark, font=font, fill=WHITE)

    return img.resize((width, height), Image.LANCZOS)


def render_splash(width: int, height: int) -> Image.Image:
    """Splash screen — white background, centred chip + wordmark below."""
    W, H = width * SS, height * SS
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    chip_side = int(round(H * 0.40))
    chip_x = (W - chip_side) // 2
    chip_y = int(round(H * 0.22))

    mask = _rounded_square_mask(chip_side, int(round(CORNER_R * chip_side)))
    navy = Image.new("RGBA", (chip_side, chip_side), NAVY)
    img.paste(navy, (chip_x, chip_y), mask)
    _draw_v_on(img, chip_origin=(chip_x, chip_y), chip_size=chip_side)

    try:
        from PIL import ImageFont
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
        size_px = int(round(H * 0.12))
        font = None
        for p in font_candidates:
            if Path(p).exists():
                font = ImageFont.truetype(p, size_px)
                break
        if font is None:
            font = ImageFont.load_default()
        d = ImageDraw.Draw(img)
        word = "Vurctne"
        bbox = d.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (W - tw) // 2 - bbox[0]
        ty = chip_y + chip_side + int(round(H * 0.06))
        d.text((tx, ty), word, font=font, fill=NAVY)
    except Exception:
        pass

    return img.resize((width, height), Image.LANCZOS)


def main() -> None:
    out = Path(__file__).parent
    tiles = {
        "Square44x44Logo.png":    render_square(44),
        "Square71x71Logo.png":    render_square(71),
        "Square150x150Logo.png":  render_square(150),
        "StoreLogo.png":          render_square(50),
        "Wide310x150Logo.png":    render_wide(310, 150),
        "SplashScreen.png":       render_splash(620, 300),
    }
    for name, img in tiles.items():
        img.save(out / name, "PNG", optimize=True)
        print(f"  wrote {name:<24s} {img.size}")


if __name__ == "__main__":
    main()
