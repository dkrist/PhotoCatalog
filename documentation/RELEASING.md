# Releasing PhotoCatalog

This document describes how to cut a new PhotoCatalog release for friends and
family. The end goal is a single `PhotoCatalog-Setup-<version>.exe` that users
download from GitHub Releases and double-click to install.

---

## Toolchain (one-time setup)

Install these on the machine you build from:

1. **Python 3.10+** with PhotoCatalog's dependencies installed
   (`pip install -r requirements.txt`).
2. **PyInstaller**
   ```powershell
   pip install pyinstaller
   ```
3. **Inno Setup 6** — download from <https://jrsoftware.org/isinfo.php> and
   install with defaults. The build script locates `iscc.exe` automatically.

You don't need any special GitHub tooling beyond what you already use.

---

## Build a release locally

From the **project root** (`C:\GitHub\PhotoCatalog`), run:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The script runs in three phases:

1. Verifies PyInstaller is installed.
2. Runs PyInstaller against `packaging\PhotoCatalog.spec` to produce
   `dist\PhotoCatalog\PhotoCatalog.exe` plus its supporting DLLs and
   resource files (the `--onedir` layout).
3. Runs Inno Setup against `packaging\PhotoCatalog.iss` to produce
   `release\PhotoCatalog-Setup-<version>.exe`.

Useful flags:

| Flag | Purpose |
|------|---------|
| `-Clean` | Delete `build\`, `dist\`, `release\` before building for a fresh run |
| `-SkipInstaller` | Build the PyInstaller output only; skip Inno Setup |

---

## Smoke-test the build

Before publishing:

1. Double-click `dist\PhotoCatalog\PhotoCatalog.exe` directly and confirm the
   UI launches, the banner renders the camera + Claude icons, and a small
   test folder catalogs correctly.
2. Then install the setup installer on a clean-ish machine (or at least a
   clean folder) and confirm:
   - Start Menu shortcut appears under "PhotoCatalog"
   - App launches from the shortcut
   - "Open Catalog Report" and "Open Process Log" work
   - Uninstall from *Add or Remove Programs* cleans up without errors

---

## Bump the version number

Two places to update for each release:

1. **`packaging\PhotoCatalog.iss`** — edit the `MyAppVersion` define near
   the top. This drives the setup filename and the "Programs and Features"
   entry.
2. **Tag** the git commit with a matching `v<version>` tag (see next step).

> Note: the version label shown in the app header (`V2 – M/D/YYYY`) is
> driven by the mtime of `scripts\gui_main.py` and updates automatically
> whenever that file changes. No manual edit needed there.

---

## Publish on GitHub Releases

1. Commit and push any code changes and an updated `CHANGELOG.md`.
2. Create a git tag:
   ```powershell
   git tag v2.0.0 -m "PhotoCatalog v2.0.0"
   git push origin v2.0.0
   ```
3. Go to <https://github.com/dkrist/PhotoCatalog/releases> and click
   **Draft a new release**.
4. Choose the tag you just pushed.
5. Title: `PhotoCatalog v2.0.0`
6. Body: paste the `[Unreleased]` section from `CHANGELOG.md`, plus a short
   "Install" section pointing non-technical users at the setup .exe. For
   example:

   ```markdown
   ## Install (Windows 10 / 11)

   1. Download **PhotoCatalog-Setup-2.0.0.exe** from the Assets below.
   2. Double-click it. If Windows SmartScreen warns you, click
      "More info" → "Run anyway" — this is normal for apps without a
      (paid) code signing certificate.
   3. Follow the installer prompts. The app will appear in your Start Menu.

   ## What's new

   <paste CHANGELOG entries here>
   ```

7. Attach `release\PhotoCatalog-Setup-<version>.exe` as a release asset.
8. Publish.
9. Share the URL: `https://github.com/dkrist/PhotoCatalog/releases/latest`

---

## A note on Windows SmartScreen

Unsigned Windows executables trigger the *"Windows protected your PC"*
warning on first launch. Users can click **More info → Run anyway** to
continue. The warning fades after enough people install the app, as
Microsoft's reputation service learns to trust it.

To eliminate the warning entirely, you'd need a code signing certificate
(roughly \$75–\$400/year depending on the CA). That's overkill for
personal distribution — a one-liner in the release notes explaining the
warning is plenty.

---

## Troubleshooting

**PyInstaller build fails with missing module**
Add the module to `hiddenimports=[...]` in `packaging\PhotoCatalog.spec`.

**Installer builds but app won't launch**
The `--onedir` layout means the `.exe` must stay next to its DLL
neighbors. If you move just the `.exe` somewhere, it will fail. Always
install via the setup installer, or copy the entire `dist\PhotoCatalog\`
folder.

**Setup flagged by antivirus**
This is a reputation issue with unsigned installers. Re-scan after a few
days, or sign the setup with a code signing certificate.

**Build is huge (\>300 MB)**
Inspect `dist\PhotoCatalog\PyQt6\Qt6\bin\` for unexpected Qt modules and
add them to `excludes=[]` in the `.spec` file.
