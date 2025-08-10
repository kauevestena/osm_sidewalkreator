#!/usr/bin/env bash
set -euo pipefail

# Ensure Docker is installed and the daemon is accessible
command -v docker >/dev/null 2>&1 || {
    echo "Error: Docker is not installed or not in PATH." >&2
    exit 1
}

docker info >/dev/null 2>&1 || {
    echo "Error: Docker daemon is not running or not reachable." >&2
    exit 1
}

# Determine the plugin root directory (one level up from the script location)
PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

USE_RELEASE=0
if [[ "${1:-}" == "--use-release" ]]; then
    USE_RELEASE=1
    shift
fi

if [[ ${USE_RELEASE} -eq 1 ]]; then
    RELEASE_OUTPUT=$(python "${PLUGIN_DIR}/release/release_zip.py")
    ZIP_PATH=$(echo "${RELEASE_OUTPUT}" | sed -n '1p')
    DOCKER_CMD="apt-get update -qq && apt-get install -y unzip >/dev/null && unzip /tmp/plugin.zip -d /tmp/plugin && cd /tmp/plugin/osm_sidewalkreator && export PYTHONPATH=/tmp/plugin/osm_sidewalkreator:/tmp/plugin/osm_sidewalkreator/test && export PIP_BREAK_SYSTEM_PACKAGES=1 && pip install -r requirements.txt && pytest"

    exec docker run --rm \
        -v "${ZIP_PATH}:/tmp/plugin.zip" \
        my-org/qgis-test:latest \
        bash -lc "${DOCKER_CMD}"
else
    # Run tests inside the official QGIS container image
    # Mount the plugin directory into /app and execute pytest after installing deps

    exec docker run --rm \
        -v "${PLUGIN_DIR}:/app" \
        -w /app \
        -e PYTHONPATH=/app:/app/test \
        qgis/qgis:latest \
        bash -lc "export PIP_BREAK_SYSTEM_PACKAGES=1 && pip install -r requirements.txt && pytest"

fi
