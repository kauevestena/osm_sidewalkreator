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

## Headless Runs (Processing Algorithms)

The image can also execute the plugin’s Processing algorithms headlessly. Below are copy‑paste ready commands using `qgis/qgis:latest` which:

- Register QGIS + Native Processing
- Register this plugin’s Processing provider
- Run the algorithm with either a polygon OGR file input or a numeric bbox
- Write OGR vector outputs (GeoJSON by default; change the extension to switch drivers)

In all examples below, the repository is mounted at `/repo`, and the sample inputs live under `/repo/assets/test_data/`.

Create an output folder once on the host:

```sh
mkdir -p output
```

General environment used in the snippets:

```sh
RIMAGE=qgis/qgis:latest
RWORK=/repo
``` 

### 1) Polygon‑based algorithms (OGR polygon input)

- Input: any OGR‑readable polygon file (e.g., the sample `assets/test_data/polygon.geojson`).
- Output: GeoJSON by default (change the extension to switch to another OGR driver).

Run “Generate Protoblocks from Polygon” (algorithm id: `sidewalkreator_algorithms_provider:generateprotoblocksfromosm`):

```sh
docker run --rm \
  -v "$(pwd)":/repo \
  -w /repo \
  "$RIMAGE" bash -lc '
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/repo
python3 - <<PY
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from qgis import processing
params = {
  "INPUT_POLYGON": "/repo/assets/test_data/polygon.geojson",
  "INPUT_CRS": "EPSG:4326",  # Optional: specify input CRS, defaults to layer CRS
  "TIMEOUT": 60,
  "OUTPUT_PROTOBLOCKS": "/repo/output/protoblocks_polygon.geojson"
}
print(processing.run("sidewalkreator_algorithms_provider:generateprotoblocksfromosm", params))
PY'
```

**New**: The algorithm now accepts an `INPUT_CRS` parameter to handle polygons in any coordinate reference system (e.g., EPSG:3857, UTM zones, etc.). The algorithm will automatically reproject to EPSG:4326 for OSM data fetching.

Run “Full Sidewalkreator from Polygon” (algorithm id: `sidewalkreator_algorithms_provider:fullsidewalkreatorfrompolygon`):

```sh
docker run --rm \
  -v "$(pwd)":/repo \
  -w /repo \
  "$RIMAGE" bash -lc '
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/repo
python3 - <<PY
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from qgis import processing
params = {
  "INPUT_POLYGON": "/repo/assets/test_data/polygon.geojson",
  "TIMEOUT": 60,
  "FETCH_BUILDINGS_DATA": False,
  "OUTPUT_SIDEWALKS": "/repo/output/sidewalks_polygon.geojson"
}
print(processing.run("sidewalkreator_algorithms_provider:fullsidewalkreatorfrompolygon", params))
PY'
```

### 2) BBox‑based algorithms (4 numeric inputs)

- Input: four values `min_lon min_lat max_lon max_lat` in EPSG:4326.
- Output: GeoJSON by default.

You can source them from the sample bbox file on the host (requires `jq`) and export as env vars:

```sh
export MIN_LON=$(jq -r .min_lon assets/test_data/bbox.json)
export MIN_LAT=$(jq -r .min_lat assets/test_data/bbox.json)
export MAX_LON=$(jq -r .max_lon assets/test_data/bbox.json)
export MAX_LAT=$(jq -r .max_lat assets/test_data/bbox.json)
```

Run “Generate Protoblocks from BBox” (algorithm id: `sidewalkreator_algorithms_provider:generateprotoblocksfrombbox`):

```sh
docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT \
  -v "$(pwd)":/repo \
  -w /repo \
  "$RIMAGE" bash -lc '
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/repo
python3 - <<PY
import os
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from qgis import processing
min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 
extent=f"{min_lon},{min_lat},{max_lon},{max_lat} [EPSG:4326]"
params={
  "EXTENT": extent,
  "TIMEOUT": 60,
  "OUTPUT_PROTOBLOCKS": "/repo/output/protoblocks_bbox.geojson"
}
print(processing.run("sidewalkreator_algorithms_provider:generateprotoblocksfrombbox", params))
PY'
```

Run “Full Sidewalkreator from BBox” (algorithm id: `sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox`):

```sh
docker run --rm \
  -e MIN_LON -e MIN_LAT -e MAX_LON -e MAX_LAT \
  -v "$(pwd)":/repo \
  -w /repo \
  "$RIMAGE" bash -lc '
set -euo pipefail
mkdir -p /tmp/runtime-qgis && chmod 700 /tmp/runtime-qgis
export XDG_RUNTIME_DIR=/tmp/runtime-qgis
export QGIS_PREFIX_PATH=/usr
export QGIS_PLUGINPATH=/usr/lib/qgis/plugins
export PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins:/repo
python3 - <<PY
import os
from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
app=QgsApplication([], False); app.initQgis()
from qgis.analysis import QgsNativeAlgorithms
QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
QgsApplication.processingRegistry().addProvider(ProtoblockProvider())
from qgis import processing
min_lon=float(os.environ["MIN_LON"]); min_lat=float(os.environ["MIN_LAT"]) 
max_lon=float(os.environ["MAX_LON"]); max_lat=float(os.environ["MAX_LAT"]) 
extent=f"{min_lon},{min_lat},{max_lon},{max_lat} [EPSG:4326]"
params={
  "INPUT_EXTENT": extent,
  "TIMEOUT": 60,
  "GET_BUILDING_DATA": False,
  "OUTPUT_SIDEWALKS": "/repo/output/sidewalks_bbox.geojson"
}
print(processing.run("sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox", params))
PY'
```

### Output formats

- GeoJSON is the default output in the examples above (by using a `.geojson` extension).
- To write to other OGR formats, just change the file extension, e.g.:
  - GPKG: `/repo/output/sidewalks.gpkg`
  - Shapefile: `/repo/output/sidewalks.shp`
  - (any other OGR driver supported by the container)

### Testing

The `tests/` directory contains comprehensive test scripts for validating algorithm functionality:

- **test_protoblock_direct.sh**: Basic protoblock algorithm test with polygon input
- **test_protoblock_with_provider.sh**: Tests protoblock algorithm via provider
- **test_protoblock_with_provider_fixed.sh**: Enhanced test with proper CRS handling
- **run_full_protoblock_test.sh**: Complete test suite with coordinate transformation
- **convert_coords.py**: Utility for converting coordinates between EPSG:4326 and EPSG:3857

Run all tests with:
```bash
cd tests && ./run_full_protoblock_test.sh
```

### Troubleshooting

- Make sure the repo is mounted and on `PYTHONPATH` as shown, so the provider module can be imported.
- If you see Processing errors for algorithms like `native:clip`, ensure Native algorithms were registered (the snippets add `QgsNativeAlgorithms`).
- If running on headless servers, keeping `QT_QPA_PLATFORM=offscreen` and a 0700 `XDG_RUNTIME_DIR` is important.
- The algorithms now support CRS parameters - use `INPUT_CRS` to specify coordinate systems other than EPSG:4326.

## Notes

- If you change Python or system dependencies for tests, update the Dockerfile and rebuild.
- GDAL is intentionally excluded from `pip install` to avoid binary mismatches; the image uses `python3-gdal` from the OS.
