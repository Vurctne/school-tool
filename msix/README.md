# MSIX Packaging — School Tool v2

## What this produces

Running `build_msix_package.ps1` produces an unsigned MSIX at
`msix/output/SchoolTool_v<version>.msix` and a SHA-256 checksum
file at `dist/SHA256SUMS-v<version>.txt`.

The pipeline has five stages: Clean → PyInstaller onedir build → Stage
(copy frozen app + tile assets, write filled `AppxManifest.xml`) → Pack
(`makeappx.exe`) → Sign (optional).

## Prerequisites

| Requirement | Minimum version |
|---|---|
| Windows | 10 build 19041 (20H1) or Windows 11 |
| Python | 3.12 x64 |
| PyInstaller | 6.x (`pip install pyinstaller`) |
| Windows 10 SDK | Any build ≥ 19041 (provides `makeappx.exe`, `signtool.exe`) |

The script auto-discovers `makeappx.exe` and `signtool.exe` from:
1. `.tools/msixsdk/` (vendored, checked in alongside v1)
2. `PATH`
3. `%ProgramFiles(x86)%\Windows Kits\10\bin\…`

## Running the build

```powershell
# Basic — reads version from app_metadata.py, no signing
.\msix\build_msix_package.ps1

# Override version (useful for alpha/RC tags)
.\msix\build_msix_package.ps1 -Version 2.0.0-alpha

# Skip the PyInstaller step (re-use an existing dist/ folder)
.\msix\build_msix_package.ps1 -SkipPyInstaller

# Custom Partner Center identity
.\msix\build_msix_package.ps1 `
    -IdentityName "Contoso.SchoolTool" `
    -Publisher "CN=Contoso, O=Contoso Pty Ltd, C=AU"
```

## Sideloading (developer testing)

```powershell
# Enable Developer Mode in Windows Settings first, OR use Add-AppxPackage
Add-AppxPackage -Path "msix\output\SchoolTool_v2.0.0.msix"
```

To uninstall: `Get-AppxPackage *SchoolTool* | Remove-AppxPackage`

## Signing with a Partner Center certificate

```powershell
$env:SFT_SIGN_PFX = "C:\certs\ivan-publisher.pfx"
$env:SFT_SIGN_PW  = "your-pfx-password"
.\msix\build_msix_package.ps1
```

The script uses `signtool.exe sign /fd SHA256 /a`. Remove `/a` and add
`/n "CN=…"` if you need to be explicit about which cert store entry to use.

## Tile assets (placeholders)

The six PNG files in `msix/staging/Assets/` are **placeholders inherited
from Master Budget Automation Tool v1.0.2**. They will be replaced once
the School Tool product name and app-icon design are finalised.

| File | Size spec |
|---|---|
| `Square44x44Logo.png` | 44×44 px |
| `Square71x71Logo.png` | 71×71 px |
| `Square150x150Logo.png` | 150×150 px |
| `Wide310x150Logo.png` | 310×150 px |
| `StoreLogo.png` | 50×50 px |
| `SplashScreen.png` | 620×300 px |

Do **not** commit production artwork here until the design is locked.
