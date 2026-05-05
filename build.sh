#!/bin/bash
set -e

echo "Building Specless with PyInstaller..."

# Clean previous builds
rm -rf build dist specless.spec

# PyInstaller command
# - --onefile creates a single executable
# - --noconfirm overwrites the output directory without asking
# - --hidden-import ensures pynput macos bindings are included
uv run pyinstaller --name specless \
                   --onefile \
                   --noconfirm \
                   --hidden-import="pynput.keyboard._darwin" \
                   --hidden-import="pynput.mouse._darwin" \
                   main.py

echo "Build complete! Binary located at dist/specless"
