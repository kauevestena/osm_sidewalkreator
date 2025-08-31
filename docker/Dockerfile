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
  PIP_BREAK_SYSTEM_PACKAGES=1

# Install minimal system packages needed for tests and Python GDAL bindings
RUN apt-get update -qq \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       unzip \
       python3-gdal \
  && rm -rf /var/lib/apt/lists/*

# Pre-install Python requirements for tests (GDAL provided by python3-gdal)
COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
  && rm -f /tmp/requirements.txt

WORKDIR /workspace

# Default to an interactive shell; tests provide their own commands
CMD ["bash"]
