from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

"""Generate the MSIX tile + Store icon set for School Tool.

Delegates to ``assets/brand/render_app_tiles.py`` for the six tiles already
defined there, then adds the ``Square310x310Logo.png`` large-tile variant that
the Store manifest now references, plus the ``app.ico`` EXE icon for
PyInstaller.

Run:
    python3 scripts/generate_store_icons.py

Output (PNGs in ``msix/staging/Assets/``, ICO in ``assets/brand/``):
    Square44x44Logo.png       44 x 44   app-list icon, taskbar
    Square71x71Logo.png       71 x 71   small tile
    Square150x150Logo.png    150 x 150  medium tile
    Square310x310Logo.png    310 x 310  large tile
    Wide310x150Logo.png      310 x 150  wide tile
    StoreLogo.png             50 x 50   Store listing thumbnail
    SplashScreen.png         620 x 300  splash on app launch
    app.ico                   16/32/48/64/128/256  PyInstaller EXE icon

Pillow is a dev-only dependency and is NOT listed in project requirements.txt.
Install with:  pip install Pillow
"""

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_BRAND_DIR = _REPO_ROOT / "assets" / "brand"
_OUT_DIR = _REPO_ROOT / "msix" / "staging" / "Assets"

# EXE icon (.ico) for PyInstaller — separate from the MSIX tile PNGs.
# Lives at a stable path under assets/brand/ so the .spec file can reference
# it without depending on the staging directory existing yet.
_ICO_OUT = _BRAND_DIR / "app.ico"

sys.path.insert(0, str(_BRAND_DIR))
try:
    import render_app_tiles as _tiles  # type: ignore[import-not-found]
finally:
    sys.path.pop(0)


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    base_tiles: dict[str, Any] = {
        "Square44x44Logo.png": _tiles.render_square(44),
        "Square71x71Logo.png": _tiles.render_square(71),
        "Square150x150Logo.png": _tiles.render_square(150),
        "StoreLogo.png": _tiles.render_square(50),
        "Wide310x150Logo.png": _tiles.render_wide(310, 150),
        "SplashScreen.png": _tiles.render_splash(620, 300),
    }
    base_tiles["Square310x310Logo.png"] = _tiles.render_square(310)

    for name, img in base_tiles.items():
        dest = _OUT_DIR / name
        img.save(dest, "PNG", optimize=True)
        print(f"  wrote {name:<28s} {img.size}")

    # app.ico — Windows EXE icon, embedded by PyInstaller. ICO is a
    # multi-resolution container; include the canonical Windows icon
    # sizes 16/32/48/64/128/256.
    _BRAND_DIR.mkdir(parents=True, exist_ok=True)
    ico_master = _tiles.render_square(256)
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_master.save(_ICO_OUT, format="ICO", sizes=ico_sizes)
    print(f"  wrote {'app.ico':<28s} {ico_sizes}")

    print(f"\nAll icons written to {_OUT_DIR}")
    print(f"EXE icon at        {_ICO_OUT}")


if __name__ == "__main__":
    main()
