#!/usr/bin/env python3

import sys
import os

sys.path.append("/usr/lib/python3/dist-packages")
sys.path.append("/usr/share/qgis/python")
sys.path.append("/usr/share/qgis/python/plugins")

# Add the plugin directory to path
plugin_dir = "/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator"
sys.path.insert(0, plugin_dir)

os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from qgis.core import QgsApplication

    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()

    from processing.full_sidewalkreator_bbox_algorithm import (
        FullSidewalkreatorBboxAlgorithm,
    )
    from qgis.core import QgsProcessingContext, QgsProcessingFeedback

    alg = FullSidewalkreatorBboxAlgorithm()

    # Test parameters - smaller bbox for testing
    params = {
        "INPUT_EXTENT": "-46.7091034,-23.5649985,-46.7035801,-23.5609541",  # São Paulo area
        "DEFAULT_WIDTH": 6,
        "MIN_WIDTH": 6,
        "MAX_WIDTH": 25,
        "GET_BUILDING_DATA": True,
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
        "TIMEOUT": 60,
        "OUTPUT_SIDEWALKS": "/tmp/test_sidewalks_debug.geojson",
    }

    context = QgsProcessingContext()
    feedback = QgsProcessingFeedback()

    print("Starting algorithm...")
    result = alg.processAlgorithm(params, context, feedback)
    print("Algorithm completed!")
    print("Result:", result)

    app.exitQgis()

except Exception as e:
    import traceback

    print(f"Error: {e}")
    traceback.print_exc()
