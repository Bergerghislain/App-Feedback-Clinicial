#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --onefile --windowed --name plateforme-evaluation-clinique app.py

echo "Executable généré dans ./dist"
