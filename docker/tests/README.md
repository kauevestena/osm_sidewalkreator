# Docker Tests

This folder contains various test scripts for the OSM SidewalKreator Docker functionality.

## Test Scripts

### Core Algorithm Tests

- **`test_protoblock_direct.sh`** - Tests the protoblock algorithm creation and initialization without using the processing framework
- **`test_protoblock_with_provider.sh`** - Tests the algorithm with provider registration (has a bug with algorithmIds method)
- **`test_protoblock_with_provider_fixed.sh`** - Fixed version of the provider registration test
- **`run_full_protoblock_test.sh`** - Comprehensive test that runs the full protoblock algorithm with CRS support

### Utility Scripts

- **`convert_coords.py`** - Python script to convert coordinates between EPSG:4326 and EPSG:3857 using GDAL
- **`test_protoblock_crs.py`** - Example Python script showing how to use the ProtoblockAlgorithm with different CRS parameters

## Usage

All test scripts should be run from the `docker/` directory:

```bash
cd docker/
./tests/test_protoblock_direct.sh
./tests/test_protoblock_with_provider_fixed.sh
./tests/run_full_protoblock_test.sh
```

The `run_full_protoblock_test.sh` script is the most comprehensive and tests:
- Algorithm registration
- Parameter initialization  
- CRS handling and reprojection
- Full algorithm execution with real OSM data
- Output generation

## Test Data

Test data files are located in `../assets/test_data/`:
- `polygon_4326_from_log.geojson` - Test polygon in EPSG:4326
- `polygon_3857_proper.geojson` - Test polygon in EPSG:3857 (Web Mercator)
- `polygon_3857.geojson` - Original test polygon (has coordinate issues)

## Notes

- All tests run in Docker containers using the `qgis/qgis:latest` image
- Tests create output files in `../assets/test_outputs/`
- The comprehensive test validates the new CRS input parameter functionality
- Tests include extensive logging to help debug any issues
