## Headless Runs (Convenience Scripts)

This folder provides one‑liners to run the plugin’s Processing algorithms headlessly in Docker. The scripts mount the repo into `qgis/qgis:latest` and write results to `assets/test_outputs/`.

- Requirements: Docker and an internet connection (for OSM fetches).
- Inputs: sample polygon and bbox in `assets/test_data/`.
- Outputs: GeoJSON files in `assets/test_outputs/`.

### Quick Start

Run from the repo root (paths are resolved automatically):

```bash
# Full pipeline from bbox (uses assets/test_data/bbox.json)
./docker/run_full_bbox.sh

# Full pipeline from bbox with custom bbox and options
./docker/run_full_bbox.sh --bbox=-49.3,-25.5,-49.29,-25.45 --classes=10,11 --no-buildings -o outputs/sidewalks_bbox.gpkg

# Full pipeline from polygon (uses assets/test_data/polygon.geojson)
./docker/run_full_polygon.sh -i assets/test_data/polygon.geojson -o outputs/sidewalks_polygon.geojson --no-buildings --no-addresses

# Protoblocks only from bbox (default EPSG:4326) or explicit CRS
./docker/run_protoblocks_bbox.sh -o outputs/protoblocks_bbox.geojson
./docker/run_protoblocks_bbox.sh --min_lon=-49.3 --min_lat=-25.5 --max_lon=-49.29 --max_lat=-25.45 --crs=EPSG:4326 -o outputs/proto_bbox.gpkg

# Protoblocks only from polygon (default EPSG:4326) or explicit CRS
./docker/run_protoblocks_polygon.sh -i assets/test_data/polygon.geojson -o outputs/protoblocks_polygon.geojson
./docker/run_protoblocks_polygon.sh -i assets/test_data/polygon_3857.geojson --crs=EPSG:3857 -o outputs/proto_poly.gpkg
```

### Script Reference

- `docker/run_full_bbox.sh`:
  - Coordinate sources (priority): `--min_lon/--min_lat/--max_lon/--max_lat`, then `--bbox=lon,lat,lon,lat`, then `assets/test_data/bbox.json`.
  - Options: `--classes=10,11,...`, `--buildings`/`--no-buildings`, `-o|--output=FILE`.
  - Help: `./docker/run_full_bbox.sh --help`.

- `docker/run_full_polygon.sh`:
  - Input: `-i|--input=FILE` (OGR polygon; multiple features are unary-unioned).
  - Options: `--classes=...`, `--buildings`/`--no-buildings`, `--addresses`/`--no-addresses`, `-o|--output=FILE` (sidewalks), `--crossings-output=FILE`, `--kerbs-output=FILE`.

- `docker/run_protoblocks_bbox.sh`:
  - BBox from flags or `assets/test_data/bbox.json`.
  - Options: `--min_lon/--min_lat/--max_lon/--max_lat`, `--bbox=...`, `--crs=EPSG:code`, `-o|--output=FILE`.

- `docker/run_protoblocks_polygon.sh`:
  - Input: `-i|--input=FILE` (OGR polygon; multiple features are unary-unioned). Optional `--crs=EPSG:code` (default `EPSG:4326`).
  - Output: `-o|--output=FILE`.

### Outputs

- Full bbox: `assets/test_outputs/sidewalks_bbox.geojson`.
- Full polygon: `assets/test_outputs/sidewalks_polygon.geojson`, `assets/test_outputs/crossings_polygon.geojson`, `assets/test_outputs/kerbs_polygon.geojson`.
- Protoblocks: `assets/test_outputs/protoblocks_bbox.geojson`, `assets/test_outputs/protoblocks_polygon.geojson`.

### Notes

- No local QGIS install required; scripts use `qgis/qgis:latest`.
- To change inputs, edit files under `assets/test_data/` or pass the supported flags shown above.
- For lower‑level/docker testing examples, see `docker/tests/`.

### Optional: Build a custom base image

The scripts run against the upstream image. If you need a custom image for CI or pinned QGIS versions, build `docker/Dockerfile`:

```bash
docker build -f docker/Dockerfile -t my-org/qgis-test:latest .
# Or pin an upstream tag
docker build --build-arg QGIS_TAG=release-3_34 -f docker/Dockerfile -t my-org/qgis-test:3.34 .
```
