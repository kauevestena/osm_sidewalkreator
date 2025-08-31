## QGIS Test Image

This folder contains the Dockerfile used to build a minimal image for running tests for the `osm_sidewalkreator` QGIS plugin. It is based on `qgis/qgis` and includes the utilities required by the test harness.

## Build

- Basic build (latest QGIS tag):
  
  ```sh
  docker build -f docker/Dockerfile -t my-org/qgis-test:latest .
  ```

- Build against a specific upstream QGIS tag (e.g., `release-3_34`):
  
  ```sh
  docker build \
    --build-arg QGIS_TAG=release-3_34 \
    -f docker/Dockerfile \
    -t my-org/qgis-test:3.34 .
  ```

## What’s included

- Base image: `qgis/qgis:${QGIS_TAG}`
- System deps: `unzip`, `python3-gdal` (provides the `osgeo` Python bindings)
- Python deps: everything from `docker/requirements.txt`; GDAL bindings come from the system package (`python3-gdal`)

## Usage

- Run release tests using the image (the repo script handles this automatically):
  
  ```sh
  ./scripts/run_qgis_tests.sh --use-release
  ```

  The script will use `my-org/qgis-test:latest` if available. If not present, it will attempt to pull it.

- Run a one-off container:
  
  ```sh
  docker run --rm -it my-org/qgis-test:latest bash
  ```

## Notes

- If you change Python or system dependencies for tests, update the Dockerfile and rebuild.
- GDAL is intentionally excluded from `pip install` to avoid binary mismatches; the image uses `python3-gdal` from the OS.
