#!/usr/bin/env python3
"""
Quick test script to run the updated Full Sidewalk Creator algorithm
and verify that it generates sidewalks, crossings, and kerbs layers.
"""

import processing
from qgis.core import QgsProject


def test_full_sidewalk_algorithm():
    """Test the Full Sidewalk Creator algorithm with crossings and kerbs generation."""

    # Define test parameters
    # Small area in Porto Alegre for quick testing
    params = {
        "BBOX": "-51.234,-30.044,-51.224,-30.034",  # Small bbox around Porto Alegre
        "OUTPUT_SIDEWALKS": "/tmp/test_sidewalks.geojson",
        "OUTPUT_CROSSINGS": "/tmp/test_crossings.geojson",
        "OUTPUT_KERBS": "/tmp/test_kerbs.geojson",
    }

    print("Running Full Sidewalk Creator Bbox Algorithm...")
    print(f"Input bbox: {params['BBOX']}")

    try:
        # Run the algorithm
        result = processing.run("osm_sidewalkreator:full_sidewalkreator_bbox", params)

        print("\nAlgorithm completed successfully!")
        print("Results:")
        for key, value in result.items():
            print(f"  {key}: {value}")

        # Check if layers were created and have features
        for layer_type in ["sidewalks", "crossings", "kerbs"]:
            output_key = f"OUTPUT_{layer_type.upper()}"
            if output_key in result:
                layer = result[output_key]
                if hasattr(layer, "featureCount"):
                    count = layer.featureCount()
                    print(f"  {layer_type.title()}: {count} features generated")
                else:
                    print(f"  {layer_type.title()}: Output created (path: {layer})")

        return True

    except Exception as e:
        print(f"Algorithm failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # This script should be run from the QGIS Python console
    print("Please run this script from the QGIS Python console:")
    print(
        "exec(open('/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator/test_algorithm.py').read())"
    )
    print("test_full_sidewalk_algorithm()")
