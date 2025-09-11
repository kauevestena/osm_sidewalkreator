# syntax=docker/dockerfile:1.6

ARG QGIS_TAG=latest
FROM qgis/qgis:${QGIS_TAG}

LABEL org.opencontainers.image.title="QGIS Test Image for osm_sidewalkreator"
LABEL org.opencontainers.image.description="Preconfigured image to run plugin tests with QGIS"
LABEL org.opencontainers.image.source="https://example.local/osm_sidewalkreator"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_BREAK_SYSTEM_PACKAGES=1 \
  QGIS_PREFIX_PATH=/usr \
  QGIS_PLUGINPATH=/usr/lib/qgis/plugins \
  QT_QPA_PLATFORM=offscreen \
  XDG_RUNTIME_DIR=/tmp/runtime-qgis

# Install minimal system packages needed for tests and Python GDAL bindings
RUN apt-get update -qq \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       unzip \
       python3-gdal \
       libpq5 \
       qgis-providers \
       qgis-common \
  && rm -rf /var/lib/apt/lists/*

# Pre-install Python requirements for tests (GDAL provided by python3-gdal)
COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
  && rm -f /tmp/requirements.txt

WORKDIR /workspace

# Ensure runtime dir exists for offscreen Qt runs
RUN mkdir -p /tmp/runtime-qgis && chmod 1777 /tmp/runtime-qgis

# Default to an interactive shell; tests provide their own commands
CMD ["bash"]
