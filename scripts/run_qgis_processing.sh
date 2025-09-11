#!/usr/bin/env bash
set -euo pipefail

USE_RELEASE=0
if [[ "${1:-}" == "--use-release" ]]; then
    USE_RELEASE=1
    shift
fi

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 [--use-release] <algorithm_id> [qgis_process parameters...]" >&2
    exit 1
fi

ALGO_ID="$1"
shift
PARAMS="$*"

PLUGIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

if [[ ${USE_RELEASE} -eq 1 ]]; then
    RELEASE_OUTPUT=$(python "${PLUGIN_DIR}/release/release_zip.py")
    ZIP_PATH=$(echo "${RELEASE_OUTPUT}" | sed -n '1p')
    DOCKER_CMD="apt-get update -qq && apt-get install -y unzip >/dev/null && unzip /tmp/plugin.zip -d /tmp/plugin && export PYTHONPATH=/tmp/plugin/osm_sidewalkreator && qgis_process run sidewalkreator_algorithms_provider:${ALGO_ID} ${PARAMS}"
    exec docker run --rm \
        -v "${ZIP_PATH}:/tmp/plugin.zip" \
        qgis/qgis:latest \
        bash -lc "${DOCKER_CMD}"
else
    DOCKER_CMD="export PYTHONPATH=/app && qgis_process run sidewalkreator_algorithms_provider:${ALGO_ID} ${PARAMS}"
    exec docker run --rm \
        -v "${PLUGIN_DIR}:/app" \
        qgis/qgis:latest \
        bash -lc "${DOCKER_CMD}"
fi

