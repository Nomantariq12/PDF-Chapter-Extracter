"""
Build script — freeze PDF Chapter Splitter into a single EXE.
Run:  python build.py
"""

import subprocess
import sys
import os

APP_NAME = "PDFChapterSplitter"

# Determine the correct path separator for --add-data
SEP = ";" if sys.platform == "win32" else ":"

cmd = [
    sys.executable, "-m", "PyInstaller",

    # ── Output settings ────────────────────────────────────────────────
    "--onefile",                         # single EXE
    "--windowed",                        # no console window
    f"--name={APP_NAME}",

    # ── Bundle the Streamlit app script ────────────────────────────────
    f"--add-data=app.py{SEP}.",

    # ── Collect all Streamlit data (static assets, metadata, etc.) ────
    "--collect-all=streamlit",

    # ── Hidden imports that PyInstaller can't auto-discover ───────────
    "--hidden-import=pypdf",
    "--hidden-import=fitz",
    "--hidden-import=pymupdf",
    "--hidden-import=pandas",
    "--hidden-import=webview",
    "--hidden-import=streamlit",
    "--hidden-import=streamlit.runtime.scriptrunner",
    "--hidden-import=streamlit.web.cli",

    # ── Copy PyMuPDF metadata (needed at runtime) ─────────────────────
    "--copy-metadata=pymupdf",
    "--copy-metadata=streamlit",

    # ── Overwrite without asking ──────────────────────────────────────
    "--noconfirm",

    # ── Entry point ───────────────────────────────────────────────────
    "launcher.py",
]

print("=" * 60)
print(f"  Building {APP_NAME}.exe")
print("=" * 60)
print()
print("Command:")
print("  " + " ".join(cmd))
print()

subprocess.run(cmd, check=True)

print()
print("=" * 60)
print(f"  ✅  Build complete!")
print(f"  EXE → dist/{APP_NAME}.exe")
print("=" * 60)
