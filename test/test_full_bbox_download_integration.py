import os
import pytest

pytest.importorskip("qgis")
from qgis.core import QgsProject, QgsCoordinateReferenceSystem
from qgis import processing

from osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm import (
    FullSidewalkreatorBboxAlgorithm,
)


pytestmark = pytest.mark.qgis


@pytest.mark.network
def test_full_bbox_download_integration(curitiba_bbox_3857=None):
    """
    Network integration test for the BBOX algorithm using a known area in EPSG:3857.

    Notes
    -----
    - Uses the bounding box reported in GUI logs. This will hit Overpass API.
    - As OSM data evolves, exact counts may vary. We therefore check minimums
      and fundamental relations (e.g., kerbs == crossings * 2).
    - Set the project CRS to 3857 to mirror GUI use.
    """
    project = QgsProject.instance()
    old_crs = project.crs()
    try:
        project.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        params = {
            "INPUT_EXTENT": (
                "-5488863.2429,-5488223.4999,-2939535.8943,-2939128.8694 [EPSG:3857]"
            ),
            "TIMEOUT": 60,
            "GET_BUILDING_DATA": True,
            "DEFAULT_WIDTH": 6.0,
            "MIN_WIDTH": 6.0,
            "MAX_WIDTH": 25.0,
            "STREET_CLASSES": list(range(20)),
            "OUTPUT_SIDEWALKS": "memory:sw",
            "OUTPUT_CROSSINGS": "memory:cr",
            "OUTPUT_KERBS": "memory:kb",
        }
        res = processing.run(FullSidewalkreatorBboxAlgorithm(), params)
        sw = res.get("OUTPUT_SIDEWALKS")
        cr = res.get("OUTPUT_CROSSINGS")
        kb = res.get("OUTPUT_KERBS")

        # Basic expectations: sidewalks present, crossings reasonable, kerbs = crossings * 2
        assert sw and sw.isValid(), "Sidewalks layer missing or invalid"
        assert sw.featureCount() >= 6, "Expected at least 6 sidewalk lines"

        if cr and hasattr(cr, "isValid") and cr.isValid():
            # Target (from GUI expectation) is around 14. Allow a tolerance.
            assert cr.featureCount() >= 10, "Expected at least 10 crossings"
            if kb and kb.isValid():
                assert kb.featureCount() == cr.featureCount() * 2
    finally:
        project.setCrs(old_crs)

