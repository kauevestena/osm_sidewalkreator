# Copy and paste this into QGIS Python Console to test the algorithm

# Import the algorithm
import sys
import os

sys.path.append(
    "/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator"
)

from processing.full_sidewalkreator_bbox_algorithm import (
    FullSidewalkreatorBboxAlgorithm,
)
from qgis.core import QgsApplication, QgsProcessingFeedback

# Create algorithm instance
alg = FullSidewalkreatorBboxAlgorithm()

# Test parameters (same extent as before)
params = {
    "INPUT_EXTENT": "-5484359.462000000,-5483281.966900000,-2933609.227400000,-2932923.690600000 [EPSG:3857]",
    "DEFAULT_WIDTH": 6,
    "MAX_WIDTH": 25,
    "MIN_WIDTH": 6,
    "STREET_CLASSES": [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
    ],
    "GET_BUILDING_DATA": True,
    "TIMEOUT": 60,
    "OUTPUT_SIDEWALKS": "TEMPORARY_OUTPUT",
    "OUTPUT_CROSSINGS": "TEMPORARY_OUTPUT",
    "OUTPUT_KERBS": "TEMPORARY_OUTPUT",
    "SAVE_EXCLUSION_ZONES_DEBUG": False,
    "OUTPUT_EXCLUSION_ZONES_DEBUG": "TEMPORARY_OUTPUT",
    "SAVE_SURE_ZONES_DEBUG": False,
    "OUTPUT_SURE_ZONES_DEBUG": "TEMPORARY_OUTPUT",
    "SAVE_PROTOBLOCKS_DEBUG": False,
    "OUTPUT_PROTOBLOCKS_DEBUG": "TEMPORARY_OUTPUT",
    "SAVE_STREETS_WIDTH_ADJUSTED_DEBUG": False,
    "OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG": "TEMPORARY_OUTPUT",
}

# Create context and feedback
context = QgsApplication.instance().processingRegistry().createContext()
feedback = QgsProcessingFeedback()

# Run algorithm
print("Running algorithm...")
results = alg.processAlgorithm(params, context, feedback)
print("Results:", results)

# Check results
if results:
    for key, value in results.items():
        if hasattr(value, "featureCount"):
            print(f"{key}: {value.featureCount()} features")
        else:
            print(f"{key}: {value}")
