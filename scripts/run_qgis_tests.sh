#!/usr/bin/env bash
set -euo pipefail

# Determine the plugin root directory (one level up from the script location)
PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

USE_RELEASE=false
if [[ ${1:-} == "--use-release" ]]; then
    USE_RELEASE=true
fi

if ${USE_RELEASE}; then
    ZIP_OUTPUT="$(python "${PLUGIN_DIR}/release/release_zip.py")"
    ZIP_PATH="$(printf "%s" "$ZIP_OUTPUT" | head -n1)"

    exec docker run --rm \
        -v "${ZIP_PATH}:/tmp/osm_sidewalkreator.zip" \
        -e PYTHONPATH=/tmp/osm_sidewalkreator:/tmp/osm_sidewalkreator/test \
        qgis/qgis:latest \
        bash -lc "unzip /tmp/osm_sidewalkreator.zip -d /tmp && cd /tmp/osm_sidewalkreator && pip install -r requirements.txt && pytest"
else
    exec docker run --rm \
        -v "${PLUGIN_DIR}:/app" \
        -w /app \
        -e PYTHONPATH=/app:/app/test \
        qgis/qgis:latest \
        bash -lc "pip install -r requirements.txt && pytest"
fi
