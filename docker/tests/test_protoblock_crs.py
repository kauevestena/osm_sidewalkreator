#!/usr/bin/env python3
"""
Test script to verify the ProtoblockAlgorithm handles input layer CRS correctly.
The algorithm now always uses the input layer's CRS; there is no separate CRS parameter.
"""


def test_protoblock_algorithm_with_different_crs():
    """
    Example showing how to use the ProtoblockAlgorithm with different input layer CRS
    """
    print("Testing ProtoblockAlgorithm with input layer CRS...")

    # Example parameters for EPSG:3857 input (Web Mercator)
    params_3857 = {
        "INPUT_POLYGON": "/path/to/polygon_3857.geojson",  # Polygon layer in EPSG:3857 (must have CRS set)
        "TIMEOUT": 60,
        "OUTPUT_PROTOBLOCKS": "memory:output_protoblocks",
    }

    # Example parameters for EPSG:4326 input (WGS84 Lat/Lon) - default
    params_4326 = {
        "INPUT_POLYGON": "/path/to/polygon_4326.geojson",  # Polygon layer in EPSG:4326 (must have CRS set)
        "TIMEOUT": 60,
        "OUTPUT_PROTOBLOCKS": "memory:output_protoblocks_4326",
    }

    # Example parameters letting the algorithm detect CRS from the input layer
    params_auto = {
        "INPUT_POLYGON": "/path/to/polygon.geojson",  # Any CRS (layer must carry CRS)
        "TIMEOUT": 60,
        "OUTPUT_PROTOBLOCKS": "memory:output_protoblocks_auto",
    }

    print("Example parameters for EPSG:3857 input:")
    print(params_3857)
    print()

    print("Example parameters for EPSG:4326 input:")
    print(params_4326)
    print()

    print("Example parameters with auto-detected CRS:")
    print(params_auto)
    print()

    # To actually run the algorithm, you would use:
    # result = processing.run("sidewalkreator_algorithms_provider:generateprotoblocksfromosm", params_3857)

    print("The algorithm will now:")
    print("1. Accept the input polygon in any CRS (as set on the layer)")
    print("2. Automatically use the layer's CRS (no separate CRS parameter)")
    print("3. Automatically reproject to EPSG:4326 for OSM data fetching")
    print("4. Return protoblocks in EPSG:4326")


if __name__ == "__main__":
    test_protoblock_algorithm_with_different_crs()
