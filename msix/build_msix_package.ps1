<#
.SYNOPSIS
    Builds an unsigned (or Store-upload) MSIX package for School Tool v2.

.DESCRIPTION
    Pipeline stages
      1. Clean   — removes build/, dist/, msix/staging/, msix/output/
      2. Build   — PyInstaller onedir via packaging/SchoolTool.spec
      3. Stage   — copies frozen app + Assets, writes filled AppxManifest.xml
      4. Package — makeappx.exe pack
      5. Sign    — signtool.exe (only when $env:SFT_SIGN_PFX is set, unless -NoSign
                   or -StoreUpload; Store signs after upload)
      6. Bundle  — wraps .msix into .msixupload when -StoreUpload is set

.PARAMETER Version
    Override the version string (e.g. "2.0.0-alpha" → padded to "2.0.0.0" in manifest).
    Defaults to the value of APP_VERSION from app_metadata.py.

.PARAMETER SkipPyInstaller
    Skip the PyInstaller build step (use an existing dist/ folder).

.PARAMETER NoSign
    Force-skip the signing step even if $env:SFT_SIGN_PFX is set.

.PARAMETER StoreUpload
    Produce a .msixupload bundle for Partner Center instead of a signed .msix.
    Skips local signing (the Store signs after upload). Verifies that the manifest
    Identity/Name and Identity/Publisher match the Partner Center values.

.PARAMETER IdentityName
    MSIX Identity/@Name — the Partner Center-assigned identity string.
    Default: Vurctne.VicSchoolFinanceTools

.PARAMETER Publisher
    Certificate CN used as the Identity/@Publisher value.
    Default: CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0

.PARAMETER PublisherDisplayName
    Human-readable publisher name written into Properties.
    Default: Vurctne

.EXAMPLE
    .\msix\build_msix_package.ps1
    .\msix\build_msix_package.ps1 -StoreUpload
    .\msix\build_msix_package.ps1 -Version 2.0.0-alpha
    .\msix\build_msix_package.ps1 -SkipPyInstaller -NoSign
    .\msix\build_msix_package.ps1 -IdentityName "Contoso.SFT" -Publisher "CN=Contoso"
#>

[CmdletBinding()]
param(
    [string]$Version              = '',
    [switch]$SkipPyInstaller,
    [switch]$NoSign,
    [switch]$StoreUpload,
    [switch]$NoVersionBump,
    [string]$IdentityName         = 'Vurctne.VicSchoolFinanceTools',
    [string]$Publisher            = 'CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0',
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
    #
    # APP_VERSION in app_metadata.py is now a 4-part string (M.N.B.R) that auto-
    # increments REVISION on every build via scripts/bump_version.py. The Store
    # rejects re-uploads with the same version, so monotonic auto-bumping makes
    # iteration cheap. Use -NoVersionBump to skip (e.g. building twice for the
    # same submission to test something locally without burning version numbers).
    # Use -Version to override entirely (e.g. -Version "2.5.0.0" before a
    # major/minor bump; bump_version is skipped when an explicit version is given).
    # -----------------------------------------------------------------------
    if (-not $Version) {
        if (-not $NoVersionBump) {
            Write-Host 'Auto-incrementing REVISION via scripts/bump_version.py...'
            $BumpScript = Join-Path $Root 'scripts\bump_version.py'
            $AppVersion = (Invoke-Expression "$(Get-PythonCommand) `"$BumpScript`"").Trim()
            if ($LASTEXITCODE -ne 0) { throw 'bump_version.py failed' }
            Write-Host "  Bumped to $AppVersion (written back to app_metadata.py)"
        } else {
            Write-Host '-NoVersionBump set — reading APP_VERSION from app_metadata.py without bumping...'
            $AppVersion = (Invoke-Expression "$(Get-PythonCommand) -c `"from app_metadata import APP_VERSION; print(APP_VERSION)`"").Trim()
            if ($LASTEXITCODE -ne 0) { throw 'Failed to read APP_VERSION from app_metadata.py' }
        }
    } else {
        # Strip pre-release suffix (e.g. "2.0.0-alpha" → "2.0.0") then pad to 4 parts.
        $AppVersion = ($Version -replace '-.*$', '')
        $segments = $AppVersion.Split('.').Count
        while ($segments -lt 4) {
            $AppVersion = "$AppVersion.0"
            $segments += 1
        }
        Write-Host "Explicit -Version supplied: $AppVersion (no auto-bump)"
    }

    # MSIX wants a 4-part version. APP_VERSION is now 4-part natively, but if a
    # legacy 3-part string slipped through, pad with .0.
    $segments = $AppVersion.Split('.').Count
    if ($segments -eq 3) {
        $MsixVersion = "$AppVersion.0"
    } else {
        $MsixVersion = $AppVersion
    }

    Write-Host "App version  : $AppVersion"
    Write-Host "MSIX version : $MsixVersion"

    # -----------------------------------------------------------------------
    # Stage 1 — Clean + generate icons
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 1 of 6 — Clean + generate icons'

    foreach ($dir in @($BuildDir, $DistDir, $MsixStagingDir, $MsixOutputDir)) {
        if (Test-Path $dir) {
            Write-Host "  Removing $dir"
            Remove-Item $dir -Recurse -Force
        }
    }

    # Icons must be generated BEFORE PyInstaller because the .spec file
    # embeds assets/brand/app.ico into the EXE. The same script also writes
    # the MSIX tile PNGs into msix/staging/Assets/ — Stage 3 verifies them.
    Write-Host '  Generating EXE icon + tile assets (scripts/generate_store_icons.py)...'
    $IconScript = Join-Path $Root 'scripts\generate_store_icons.py'
    if (Test-Path $IconScript) {
        Invoke-Python "`"$IconScript`""
    } else {
        throw "Icon generator not found at $IconScript — required for PyInstaller .ico"
    }
    $AppIco = Join-Path $Root 'assets\brand\app.ico'
    if (-not (Test-Path $AppIco)) {
        throw "EXE icon not produced at $AppIco — generate_store_icons.py failed silently?"
    }

    # -----------------------------------------------------------------------
    # Stage 2 — PyInstaller
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 2 of 6 — PyInstaller build'

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
    Write-Banner 'Stage 3 of 6 — Stage MSIX contents'

    # -Force is idempotent: doesn't error if the dir already exists.
    # Stage 1's icon generation creates msix/staging/Assets/ as a side
    # effect, so these dirs already exist by the time we get here.
    New-Item -ItemType Directory -Path $MsixStagingDir -Force | Out-Null
    New-Item -ItemType Directory -Path $AssetsDir      -Force | Out-Null
    New-Item -ItemType Directory -Path $MsixOutputDir  -Force | Out-Null

    Write-Host '  Copying frozen application...'
    Copy-Item (Join-Path $FrozenDir '*') -Destination $MsixStagingDir -Recurse -Force

    # Tile assets were generated in Stage 1 BEFORE PyInstaller (so the .ico
    # exists when the .spec runs). Stage 1 cleans msix/staging/, so we need
    # to regenerate the PNGs here AFTER the staging directory is recreated
    # above (the .ico in assets/brand/ persists across the clean).
    Write-Host '  Re-generating tile assets after staging clean...'
    $IconScript = Join-Path $Root 'scripts\generate_store_icons.py'
    if (Test-Path $IconScript) {
        Invoke-Python "`"$IconScript`""
    } else {
        Write-Warning "  Icon generator not found at $IconScript — falling back to committed PNGs."
    }

    # Verify every required PNG is present.
    $pngFiles = @(
        'Square44x44Logo.png',
        'Square71x71Logo.png',
        'Square150x150Logo.png',
        'Square310x310Logo.png',
        'Wide310x150Logo.png',
        'StoreLogo.png',
        'SplashScreen.png'
    )
    $MissingAssets = @()
    foreach ($png in $pngFiles) {
        $target = Join-Path $AssetsDir $png
        if (-not (Test-Path $target)) {
            $MissingAssets += $png
        }
    }
    if ($MissingAssets.Count -gt 0) {
        throw "Required tile assets are missing from $AssetsDir :`n  $($MissingAssets -join ', ')`nRun: python3 scripts/generate_store_icons.py"
    }
    Write-Host "  All $($pngFiles.Count) tile assets present."

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
    # Identity guard — catch manifest/cert mismatches before wasting a pack run.
    # When -StoreUpload is set the values MUST match the Partner Center identity
    # exactly; for sideload builds this is advisory only (warn, don't fail).
    # -----------------------------------------------------------------------
    $ExpectedName      = 'Vurctne.VicSchoolFinanceTools'
    $ExpectedPublisher = 'CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0'
    if ($IdentityName -ne $ExpectedName -or $Publisher -ne $ExpectedPublisher) {
        $msg = @(
            "Identity mismatch detected:",
            "  Identity/Name      : '$IdentityName'  (expected '$ExpectedName')",
            "  Identity/Publisher : '$Publisher'  (expected '$ExpectedPublisher')",
            "  The Store will reject a package whose Identity does not match the Partner Center account."
        ) -join "`n"
        if ($StoreUpload) {
            throw $msg
        } else {
            Write-Warning $msg
        }
    }

    # -----------------------------------------------------------------------
    # Stage 4 — Package
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 4 of 6 — Pack MSIX'

    $MakeAppx  = Resolve-SdkTool 'makeappx.exe'
    $MsixFile  = Join-Path $MsixOutputDir "School_Tool_${MsixVersion}_x64.msix"

    Write-Host "  makeappx: $MakeAppx"
    Write-Host "  Output  : $MsixFile"

    & $MakeAppx pack /d $MsixStagingDir /p $MsixFile /o
    if ($LASTEXITCODE -ne 0) { throw 'makeappx.exe failed to create the MSIX package.' }

    # -----------------------------------------------------------------------
    # Stage 5 — Sign (skipped for Store uploads; Store signs after ingestion)
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 5 of 6 — Sign'

    if ($StoreUpload) {
        Write-Host '  -StoreUpload set — skipping local signing (Store signs after upload).'
    } elseif ($NoSign) {
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
        Write-Host '  For Store submission, use -StoreUpload instead.'
    }

    # -----------------------------------------------------------------------
    # Stage 6 — Bundle as .msixupload (Store submission only)
    # A .msixupload is a ZIP renamed with the .msixupload extension containing
    # the .msix file (and optionally symbol packages). Partner Center requires
    # this format for automated ingestion.
    # -----------------------------------------------------------------------
    Write-Banner 'Stage 6 of 6 — Store upload bundle'

    $ArtifactFile = $null

    if ($StoreUpload) {
        $MsixUploadFile = Join-Path $MsixOutputDir "School_Tool_${MsixVersion}_x64.msixupload"
        Write-Host "  Bundling: $MsixUploadFile"

        $TempZip = $MsixUploadFile -replace '\.msixupload$', '.zip'
        if (Test-Path $TempZip)       { Remove-Item $TempZip -Force }
        if (Test-Path $MsixUploadFile) { Remove-Item $MsixUploadFile -Force }

        Compress-Archive -Path $MsixFile -DestinationPath $TempZip -Force
        Rename-Item -Path $TempZip -NewName (Split-Path $MsixUploadFile -Leaf)

        Write-Host "  Created : $MsixUploadFile"
        $ArtifactFile = $MsixUploadFile
    } else {
        Write-Host '  -StoreUpload not set — skipping .msixupload bundle.'
        Write-Host '  Use -StoreUpload to produce a Partner Center upload artifact.'
        $ArtifactFile = $MsixFile
    }

    Write-Host ''
    Write-Host 'Computing SHA-256 checksums...'

    $sumsFile = Join-Path $DistDir "SHA256SUMS-v$AppVersion.txt"
    $hash     = (Get-FileHash $ArtifactFile -Algorithm SHA256).Hash.ToLower()
    $artifactLeaf = Split-Path $ArtifactFile -Leaf
    $line     = "$hash  $artifactLeaf"
    Set-Content -Path $sumsFile -Value $line -Encoding UTF8
    Write-Host "  $line"
    Write-Host "  Written: $sumsFile"

    Write-Banner 'Build complete'
    Write-Host "  Artifact : $ArtifactFile"
    Write-Host "  SHA256   : $sumsFile"
    Write-Host ''
    if ($StoreUpload) {
        Write-Host 'Next steps (Store upload):'
        Write-Host "  1. Log in to Partner Center: https://partner.microsoft.com/dashboard"
        Write-Host "  2. Open School Tool > Submissions > New submission."
        Write-Host "  3. Upload: $ArtifactFile"
        Write-Host '  4. Complete Store listing, pricing, and submit for certification.'
        Write-Host '  See docs/store_publish.md for the full checklist.'
    } else {
        Write-Host 'Next steps (sideload):'
        Write-Host "  * Add-AppxPackage -Path `"$ArtifactFile`""
        Write-Host '  * For Store submission, rerun with -StoreUpload.'
    }

}
finally {
    Pop-Location
}
