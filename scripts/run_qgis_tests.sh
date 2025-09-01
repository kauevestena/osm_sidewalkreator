#!/usr/bin/env bash
set -euo pipefail

# Determine the plugin root directory (one level up from the script location)
PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

USE_RELEASE=0
if [[ "${1:-}" == "--use-release" ]]; then
    USE_RELEASE=1
    shift
fi

docker_usable() {
    command -v docker >/dev/null 2>&1 || return 1
    # Check daemon accessibility; avoid noisy output
    docker info >/dev/null 2>&1 || return 1
    return 0
}

ensure_local_pytest() {
    # Ensure we can run pytest without relying on system pip
    if command -v pytest >/dev/null 2>&1; then
        return 0
    fi
    if [[ ! -d "${PLUGIN_DIR}/.venv_ci" ]]; then
        python3 -m venv "${PLUGIN_DIR}/.venv_ci"
    fi
    # shellcheck disable=SC1091
    source "${PLUGIN_DIR}/.venv_ci/bin/activate"
    python -m pip install --upgrade pip >/dev/null
    pip install -r "${PLUGIN_DIR}/docker/requirements.txt" >/dev/null
}

if docker_usable; then
    if [[ ${USE_RELEASE} -eq 1 ]]; then
        PYTHON_BIN="python"
        if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
            if command -v python3 >/dev/null 2>&1; then
                PYTHON_BIN="python3"
            else
                echo "Python interpreter not found (tried 'python' and 'python3')." >&2
                exit 1
            fi
        fi
        RELEASE_OUTPUT=$("${PYTHON_BIN}" "${PLUGIN_DIR}/release/release_zip.py")
        ZIP_PATH=$(echo "${RELEASE_OUTPUT}" | sed -n '1p')
        DOCKER_CMD="apt-get update -qq && apt-get install -y unzip >/dev/null && unzip /tmp/plugin.zip -d /tmp/plugin && mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis && export XDG_RUNTIME_DIR=/tmp/runtime-qgis && export QGIS_PREFIX_PATH=/usr && export QGIS_PLUGINPATH=/usr/lib/qgis/plugins && export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/tmp/plugin:/tmp/plugin/osm_sidewalkreator/test:\${PYTHONPATH} && export PIP_BREAK_SYSTEM_PACKAGES=1 && export QT_QPA_PLATFORM=offscreen && pip install -r /tmp/plugin/osm_sidewalkreator/docker/requirements.txt && pytest -ra /tmp/plugin/osm_sidewalkreator/test"
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
            -v "${PLUGIN_DIR}:/plugins/osm_sidewalkreator" \
            -w / \
            qgis/qgis:latest \
            bash -lc "mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis && export XDG_RUNTIME_DIR=/tmp/runtime-qgis && export QGIS_PREFIX_PATH=/usr && export QGIS_PLUGINPATH=/usr/lib/qgis/plugins && export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/plugins:/plugins/osm_sidewalkreator/test:\${PYTHONPATH} && export PIP_BREAK_SYSTEM_PACKAGES=1 && export QT_QPA_PLATFORM=offscreen && apt-get update -qq && apt-get install -y python3-gdal unzip >/dev/null && pip install -r /plugins/osm_sidewalkreator/docker/requirements.txt && pytest -ra /plugins/osm_sidewalkreator/test"
    fi
else
    echo "Docker unavailable or not accessible, running tests without QGIS (pytest -m 'not qgis')."
    cd "${PLUGIN_DIR}"
    export PYTHONPATH="${PLUGIN_DIR}:${PLUGIN_DIR}/test"
    export PIP_BREAK_SYSTEM_PACKAGES=1
    ensure_local_pytest
    pytest -m 'not qgis' "$@" test
fi
