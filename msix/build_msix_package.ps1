<#
.SYNOPSIS
    Builds an unsigned (or optionally signed) MSIX package for School Tool v2.

.DESCRIPTION
    Pipeline stages
      1. Clean   — removes build/, dist/, msix/staging/, msix/output/
      2. Build   — PyInstaller onedir via packaging/SchoolTool.spec
      3. Stage   — copies frozen app + Assets, writes filled AppxManifest.xml
      4. Package — makeappx.exe pack
      5. Sign    — signtool.exe (only when $env:SFT_SIGN_PFX is set, unless -NoSign)

.PARAMETER Version
    Override the version string (e.g. "2.0.0-alpha" → padded to "2.0.0.0" in manifest).
    Defaults to the value of APP_VERSION from app_metadata.py.

.PARAMETER SkipPyInstaller
    Skip the PyInstaller build step (use an existing dist/ folder).

.PARAMETER NoSign
    Force-skip the signing step even if $env:SFT_SIGN_PFX is set.

.PARAMETER IdentityName
    MSIX Identity/@Name — the Partner Center-assigned identity string.
    Default: Vurctne.SchoolTool

.PARAMETER Publisher
    Certificate CN used as the Identity/@Publisher value.
    Default: CN=Vurctne

.PARAMETER PublisherDisplayName
    Human-readable publisher name written into Properties.
    Default: Vurctne

.EXAMPLE
    .\msix\build_msix_package.ps1
    .\msix\build_msix_package.ps1 -Version 2.0.0-alpha
    .\msix\build_msix_package.ps1 -SkipPyInstaller -NoSign
    .\msix\build_msix_package.ps1 -IdentityName "Contoso.SFT" -Publisher "CN=Contoso"
#>

[CmdletBinding()]
param(
    [string]$Version            = '',
    [switch]$SkipPyInstaller,
    [switch]$NoSign,
    [string]$IdentityName       = 'Vurctne.SchoolTool',
    [string]$Publisher          = 'CN=Vurctne',
    [string]$PublisherDisplayName = 'Vurctne'
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths — all repo-relative; $Root is the repository root.
# ---------------------------------------------------------------------------
$Root           = Split-Path -Parent $PSScriptRoot
$AppName        = 'School Tool'
$DistDir        = Join-Path $Root 'dist'
$BuildDir       = Join-Path $Root 'build'
$MsixStagingDir = Join-Path $Root 'msix\staging'
$MsixOutputDir  = Join-Path $Root 'msix\output'
$AssetsDir      = Join-Path $MsixStagingDir 'Assets'
$SpecFile       = Join-Path $Root 'packaging\SchoolTool.spec'
$ManifestTemplate = Join-Path $Root 'msix\AppxManifest.template.xml'

# ---------------------------------------------------------------------------
# Resolve Python command
# ---------------------------------------------------------------------------
function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) { return 'py -3' }
    if (Get-Command python -ErrorAction SilentlyContinue) { return 'python' }
    throw 'Python 3 was not found. Install Python 3.12 and ensure it is on PATH.'
}

function Invoke-Python {
    param([string]$Arguments)
    $cmd = "$(Get-PythonCommand) $Arguments"
    Write-Host "  > $cmd"
    cmd /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE): $cmd" }
}

# ---------------------------------------------------------------------------
# Resolve makeappx / signtool — prefer vendored .tools/msixsdk/, then PATH,
# then Windows SDK installations.
# ---------------------------------------------------------------------------
function Resolve-SdkTool {
    param([string]$ExeName)

    $local = Join-Path $Root ".tools\msixsdk\$ExeName"
    if (Test-Path $local) { return (Resolve-Path $local).Path }

    $onPath = Get-Command $ExeName -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $sdkRoots = @(
        "$env:ProgramFiles(x86)\Windows Kits\10\bin",
        "$env:ProgramFiles\Windows Kits\10\bin"
    )
    foreach ($sdkRoot in $sdkRoots) {
        if (Test-Path $sdkRoot) {
            $found = Get-ChildItem $sdkRoot -Recurse -Filter $ExeName -ErrorAction SilentlyContinue |
                     Sort-Object FullName -Descending |
                     Select-Object -First 1 -ExpandProperty FullName
            if ($found) { return $found }
        }
    }

    throw "$ExeName was not found. Install the Windows 10 SDK or place it in .tools\msixsdk\."
}

# ---------------------------------------------------------------------------
# Helper: banner
# ---------------------------------------------------------------------------
function Write-Banner {
    param([string]$Text)
    $line = '=' * 72
    Write-Host ''
    Write-Host $line
    Write-Host "  $Text"
    Write-Host $line
}

# ===========================================================================
# MAIN
# ===========================================================================
Push-Location $Root
try {

    # -----------------------------------------------------------------------
    # Resolve version
    # -----------------------------------------------------------------------
    if (-not $Version) {
        Write-Host 'Reading APP_VERSION from app_metadata.py...'
        $AppVersion = (Invoke-Expression "$(Get-PythonCommand) -c `"from app_metadata import APP_VERSION; print(APP_VERSION)`"").Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Failed to read APP_VERSION from app_metadata.py' }
    } else {
        # Strip pre-release suffix (e.g. "2.0.0-alpha" → "2.0.0") before padding.
        $AppVersion = ($Version -replace '-.*$', '')
    }

    # MSIX requires a four-part version (X.Y.Z.0).
    $MsixVersion = "$AppVersion.0"

    Write-Host "App version  : $AppVersion"
    Write-Host "MSIX version : $MsixVersion"

    # -----------------------------------------------------------------------
    # Stage 1 — Clean
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 1 of 5 — Clean'

    foreach ($dir in @($BuildDir, $DistDir, $MsixStagingDir, $MsixOutputDir)) {
        if (Test-Path $dir) {
            Write-Host "  Removing $dir"
            Remove-Item $dir -Recurse -Force
        }
    }

    # -----------------------------------------------------------------------
    # Stage 2 — PyInstaller
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 2 of 5 — PyInstaller build'

    if ($SkipPyInstaller) {
        Write-Host '  -SkipPyInstaller set — skipping build step.'
    } else {
        Invoke-Python "-m PyInstaller `"$SpecFile`" --noconfirm --clean"
    }

    $FrozenDir = Join-Path $DistDir "$AppName v$AppVersion"
    if (-not (Test-Path $FrozenDir)) {
        throw "Expected PyInstaller output not found: $FrozenDir"
    }

    # -----------------------------------------------------------------------
    # Stage 3 — Stage
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 3 of 5 — Stage MSIX contents'

    New-Item -ItemType Directory -Path $MsixStagingDir | Out-Null
    New-Item -ItemType Directory -Path $AssetsDir      | Out-Null
    New-Item -ItemType Directory -Path $MsixOutputDir  | Out-Null

    Write-Host '  Copying frozen application...'
    Copy-Item (Join-Path $FrozenDir '*') -Destination $MsixStagingDir -Recurse -Force

    Write-Host '  Copying tile assets...'
    $SourceAssetsDir = Join-Path $Root 'msix\staging\Assets'
    # The Assets folder was pre-populated; if staging was just cleaned we need
    # to restore it from the committed sources in the repo's msix/staging/Assets.
    # Because we cleaned msix/staging/ above we copy from git-tracked path.
    # At build time these are the placeholder PNGs checked into the repo.
    # Ivan replaces them before a Store submission.
    $CommittedAssets = Join-Path $Root 'msix\staging\Assets'
    # Re-create after copy (Copy-Item above may have staged them already if
    # FrozenDir contained an Assets subfolder; be explicit).
    $pngFiles = @(
        'Square44x44Logo.png',
        'Square71x71Logo.png',
        'Square150x150Logo.png',
        'Wide310x150Logo.png',
        'StoreLogo.png',
        'SplashScreen.png'
    )
    # Assets were deleted by the clean step — restore from the repo's committed
    # msix/staging/Assets/ originals which we keep in version control.
    # NOTE: At this point $AssetsDir was just created (empty). The PNG files
    # live in the git-tracked path; because we wiped msix/staging/ we restore
    # them from the assets/brand/ fallback that ships with the repo.
    $AssetFallback = Join-Path $Root 'assets\brand'
    foreach ($png in $pngFiles) {
        $target = Join-Path $AssetsDir $png
        if (-not (Test-Path $target)) {
            $fallback = Join-Path $AssetFallback $png
            if (Test-Path $fallback) {
                Copy-Item $fallback -Destination $target -Force
                Write-Host "    Restored from assets/brand/: $png"
            } else {
                throw "Asset not found and no fallback available: $png"
            }
        }
    }

    Write-Host '  Writing AppxManifest.xml...'
    $manifestContent = Get-Content $ManifestTemplate -Raw -Encoding UTF8
    $ExeName     = "$AppName v$AppVersion.exe"
    $Description = 'Finance automation tools for Victorian Government school business managers. Starts with the HYIA transfer-code generator; more tools arriving through 2026.'

    $manifestContent = $manifestContent.Replace('__IDENTITY_NAME__', $IdentityName)
    $manifestContent = $manifestContent.Replace('__PUBLISHER__',     $Publisher)
    $manifestContent = $manifestContent.Replace('__VERSION__',       $MsixVersion)
    $manifestContent = $manifestContent.Replace('__EXE_NAME__',      $ExeName)
    $manifestContent = $manifestContent.Replace('__DESCRIPTION__',   $Description)
    Set-Content -Path (Join-Path $MsixStagingDir 'AppxManifest.xml') `
                -Value $manifestContent `
                -Encoding UTF8

    # -----------------------------------------------------------------------
    # Stage 4 — Package
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 4 of 5 — Pack MSIX'

    $MakeAppx  = Resolve-SdkTool 'makeappx.exe'
    $MsixFile  = Join-Path $MsixOutputDir "SchoolTool_v$AppVersion.msix"

    Write-Host "  makeappx: $MakeAppx"
    Write-Host "  Output  : $MsixFile"

    & $MakeAppx pack /d $MsixStagingDir /p $MsixFile /o
    if ($LASTEXITCODE -ne 0) { throw 'makeappx.exe failed to create the MSIX package.' }

    # -----------------------------------------------------------------------
    # Stage 5 — Sign (optional)
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 5 of 5 — Sign'

    if ($NoSign) {
        Write-Host '  -NoSign set — skipping signing step.'
    } elseif ($env:SFT_SIGN_PFX) {
        $SignTool = Resolve-SdkTool 'signtool.exe'
        Write-Host "  signtool: $SignTool"
        Write-Host "  PFX     : $env:SFT_SIGN_PFX"

        & $SignTool sign /fd SHA256 /a /f $env:SFT_SIGN_PFX /p $env:SFT_SIGN_PW $MsixFile
        if ($LASTEXITCODE -ne 0) { throw 'signtool.exe failed to sign the MSIX package.' }
        Write-Host '  Package signed successfully.'
    } else {
        Write-Host '  $env:SFT_SIGN_PFX not set — producing unsigned MSIX.'
        Write-Host '  To sign: set $env:SFT_SIGN_PFX and $env:SFT_SIGN_PW, then rerun.'
    }

    # -----------------------------------------------------------------------
    # SHA256SUMS manifest
    # -----------------------------------------------------------------------
    Write-Host ''
    Write-Host 'Computing SHA-256 checksums...'

    $sumsFile = Join-Path $DistDir "SHA256SUMS-v$AppVersion.txt"
    $hash     = (Get-FileHash $MsixFile -Algorithm SHA256).Hash.ToLower()
    $line     = "$hash  SchoolTool_v$AppVersion.msix"
    Set-Content -Path $sumsFile -Value $line -Encoding UTF8
    Write-Host "  $line"
    Write-Host "  Written: $sumsFile"

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    Write-Banner 'Build complete'
    Write-Host "  MSIX   : $MsixFile"
    Write-Host "  SHA256 : $sumsFile"
    Write-Host ''
    Write-Host 'Next steps:'
    Write-Host '  * To sideload: Add-AppxPackage -Path "' + $MsixFile + '"'
    Write-Host '  * To publish : submit msix/output/*.msix to Partner Center.'
    Write-Host '  * Replace placeholder tiles in msix/staging/Assets/ before Store submission.'

}
finally {
    Pop-Location
}
