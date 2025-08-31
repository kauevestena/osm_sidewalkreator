#!/usr/bin/env bash
set -euo pipefail

# Determine the plugin root directory (one level up from the script location)
PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

USE_RELEASE=0
if [[ "${1:-}" == "--use-release" ]]; then
    USE_RELEASE=1
    shift
fi

if command -v docker >/dev/null 2>&1; then
    if [[ ${USE_RELEASE} -eq 1 ]]; then
        RELEASE_OUTPUT=$(python "${PLUGIN_DIR}/release/release_zip.py")
        ZIP_PATH=$(echo "${RELEASE_OUTPUT}" | sed -n '1p')
        DOCKER_CMD="apt-get update -qq && apt-get install -y unzip >/dev/null && unzip /tmp/plugin.zip -d /tmp/plugin && cd /tmp/plugin/osm_sidewalkreator && export PYTHONPATH=/tmp/plugin/osm_sidewalkreator:/tmp/plugin/osm_sidewalkreator/test && export PIP_BREAK_SYSTEM_PACKAGES=1 && pip install -r docker/requirements.txt && pytest test"
        if ! docker image inspect my-org/qgis-test:latest >/dev/null 2>&1; then
            echo "Docker image my-org/qgis-test:latest not found. Attempting to pull..."
            if ! docker pull my-org/qgis-test:latest >/dev/null 2>&1; then
                echo "Warning: my-org/qgis-test:latest unavailable, running tests without QGIS (pytest -m 'not qgis')."
                cd "${PLUGIN_DIR}"
                export PYTHONPATH="${PLUGIN_DIR}:${PLUGIN_DIR}/test"
                export PIP_BREAK_SYSTEM_PACKAGES=1
                if ! command -v gdal-config >/dev/null 2>&1; then
                    if command -v apt-get >/dev/null 2>&1; then
                        apt-get update -qq
                        apt-get install -y gdal-bin libgdal-dev python3-gdal >/dev/null
                    else
                        echo "gdal-config not found. Please install GDAL development libraries." >&2
                        exit 1
                    fi
                fi
                pip install -r docker/requirements.txt >/dev/null
                pytest -m 'not qgis' "$@" test
                exit 0
            fi
        fi

        exec docker run --rm \
            -v "${ZIP_PATH}:/tmp/plugin.zip" \
            my-org/qgis-test:latest \
            bash -lc "${DOCKER_CMD}"
    else
        exec docker run --rm \
            -v "${PLUGIN_DIR}:/app" \
            -w /app \
            -e PYTHONPATH=/app:/app/test \
            qgis/qgis:latest \
            bash -lc "export PIP_BREAK_SYSTEM_PACKAGES=1 && apt-get update -qq && apt-get install -y python3-gdal unzip >/dev/null && pip install -r docker/requirements.txt && pytest test"
    fi
else
    echo "Docker not available, running tests without QGIS (pytest -m 'not qgis')."
    cd "${PLUGIN_DIR}"
    export PYTHONPATH="${PLUGIN_DIR}:${PLUGIN_DIR}/test"
    export PIP_BREAK_SYSTEM_PACKAGES=1
    if ! command -v gdal-config >/dev/null 2>&1; then
        if command -v apt-get >/dev/null 2>&1; then
            apt-get update -qq
            apt-get install -y gdal-bin libgdal-dev python3-gdal >/dev/null
        else
            echo "gdal-config not found. Please install GDAL development libraries." >&2
            exit 1
        fi
    fi
    pip install -r docker/requirements.txt >/dev/null
    pytest -m 'not qgis' "$@" test
fi
