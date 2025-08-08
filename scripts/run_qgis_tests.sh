#!/usr/bin/env bash
set -euo pipefail

# Determine the plugin root directory (one level up from the script location)
PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Run tests inside the official QGIS container image
# Mount the plugin directory into /app and execute pytest after installing deps
exec docker run --rm \
    -v "${PLUGIN_DIR}:/app" \
    -w /app \
    qgis/qgis:latest \
    bash -lc "pip install -r requirements.txt && pytest"
