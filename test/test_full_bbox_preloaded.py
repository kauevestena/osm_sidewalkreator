import json
import os
import pytest

pytest.importorskip("qgis")
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsApplication,
)
from qgis import processing

from osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm import (
    FullSidewalkreatorBboxAlgorithm,
)


pytestmark = pytest.mark.qgis


@pytest.fixture(scope="module", autouse=True)
def ensure_processing_native():
    try:
        from processing.core.Processing import Processing
        Processing.initialize()
    except Exception:
        pass
    try:
        from qgis.analysis import QgsNativeAlgorithms
        QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
    except Exception:
        pass


def test_full_bbox_preloaded_sample(monkeypatch):
    """
    Runs the BBOX algorithm headlessly using a pre-shipped OSM roads sample,
    bypassing the network via monkeypatching `get_osm_data`.

    - Uses EPSG:4326 extent that covers the sample file for simplicity.
    - Asserts sidewalks are generated and kerbs are consistent with crossings.
    """
    project = QgsProject.instance()
    old_crs = project.crs()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets",
        "test_data",
        "osm_roads_sample_bbox.geojson",
    )

    def fake_get_osm_data(**kwargs):
        # Return the on-disk sample file path
        return sample_path

    # Patch the bbox algorithm to use the local file
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.full_sidewalkreator_bbox_algorithm.get_osm_data",
        fake_get_osm_data,
    )

    params = {
        # Extent covering the sample coordinates
        "INPUT_EXTENT": "-49.3050,-25.5185,-49.3020,-25.5156 [EPSG:4326]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
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

    assert sw and sw.isValid(), "Sidewalks layer missing or invalid"
    # Unsplitted sidewalks count should be exactly 6 for the sample
    assert sw.featureCount() == 6, f"Expected 6 sidewalks, got {sw.featureCount()}"

    # Crossings may vary with geometry; just check relationship if present
    assert cr and hasattr(cr, "isValid") and cr.isValid(), "Crossings layer missing or invalid"
    assert kb and kb.isValid(), "Kerbs layer missing or invalid"
    # For the sample, we expect exactly 14 crossings and 28 kerbs
    assert cr.featureCount() == 14, f"Expected 14 crossings, got {cr.featureCount()}"
    assert kb.featureCount() == 28, f"Expected 28 kerbs, got {kb.featureCount()}"

    project.setCrs(old_crs)
