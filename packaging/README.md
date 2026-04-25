# PyInstaller Spec — School Tool v2

## Overview

`SchoolTool.spec` is a **onedir** spec: PyInstaller produces a
folder (`dist/School Tool v2.0.0/`) rather than a single EXE.
The MSIX staging step copies this folder's contents into the package.

## Building locally (developer mode)

```powershell
# From the repository root
pyinstaller packaging/SchoolTool.spec --noconfirm --clean
```

The output lands at `dist/School Tool v2.0.0/`.
Run `dist\School Tool v2.0.0\School Tool v2.0.0.exe`
to verify the frozen app starts correctly before packing.

## pywin32 / hiddenimports note

`win32crypt`, `win32api`, and `pythoncom` are listed as hidden imports so
that PyInstaller bundles them even though they are imported conditionally
inside the toolkit (HYIA SIN storage via DPAPI, macro-preserving XLSM
writes). On non-Windows build hosts PyInstaller silently skips DLLs that
do not exist — the spec is safe to parse on Linux/macOS.

`collect_submodules` is called on `openpyxl` and `pdfplumber` to capture
all format plugins and table-detection code that those libraries import
dynamically at runtime.
