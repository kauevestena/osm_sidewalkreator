import json
import tempfile
import pytest

pytest.importorskip("qgis")
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingException,
    QgsProject,
    QgsCoordinateReferenceSystem,
)
from qgis import processing

from ..utilities import get_qgis_app
from osm_sidewalkreator.processing.protoblock_provider import ProtoblockProvider
from osm_sidewalkreator.processing.draw_missing_crossings_bbox_algorithm import (
    DrawMissingCrossingsBBoxAlgorithm,
)

pytestmark = pytest.mark.qgis


@pytest.fixture(scope="module", autouse=True)
def qgis_env():
    """Initialise QGIS and register provider once for tests."""
    app, _, _, _ = get_qgis_app()
    assert app is not None
    # Ensure QGIS Processing framework is initialized in headless tests
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
    provider = ProtoblockProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    return app


def _mock_osm_data(monkeypatch):
    """Mock OSM data fetching for tests."""
    
    def fake_osm_query(*args, **kwargs):
        return "dummy_query"
    
    def fake_get_osm_data(**kwargs):
        geomtype = kwargs.get("geomtype", "LineString")
        tempfilesname = kwargs.get("tempfilesname", "test")
        
        if "sidewalk" in tempfilesname:
            # Mock sidewalk data
            geojson = json.dumps({
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"highway": "footway"},
                        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                    }
                ],
            })
        elif "crossing" in tempfilesname:
            # Mock crossing data (empty - no existing crossings)
            geojson = json.dumps({
                "type": "FeatureCollection",
                "features": [],
            })
        else:
            # Mock street data
            geojson = json.dumps({
                "type": "FeatureCollection", 
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"highway": "residential"},
                        "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"highway": "residential"},
                        "geometry": {"type": "LineString", "coordinates": [[1, 0], [1, 1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"highway": "residential"},
                        "geometry": {"type": "LineString", "coordinates": [[1, 1], [0, 1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"highway": "residential"},
                        "geometry": {"type": "LineString", "coordinates": [[0, 1], [0, 0]]},
                    },
                ],
            })
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson")
        tmp.write(geojson.encode("utf-8"))
        tmp.flush()
        tmp.close()
        return tmp.name

    def fake_remove_unconnected(layer):
        return layer
        
    def fake_polygonize(layer, **kwargs):
        poly = QgsVectorLayer("Polygon?crs=EPSG:4326", "protob", "memory")
        dp = poly.dataProvider()
        f = QgsFeature()
        f.setGeometry(
            QgsGeometry.fromPolygonXY(
                [[
                    QgsPointXY(0, 0),
                    QgsPointXY(1, 0),
                    QgsPointXY(1, 1),
                    QgsPointXY(0, 1),
                    QgsPointXY(0, 0),
                ]]
            )
        )
        dp.addFeatures([f])
        poly.updateExtents()
        return poly

    monkeypatch.setattr(
        "osm_sidewalkreator.processing.draw_missing_crossings_bbox_algorithm.osm_query_string_by_bbox",
        fake_osm_query,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.draw_missing_crossings_bbox_algorithm.get_osm_data",
        fake_get_osm_data,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.draw_missing_crossings_bbox_algorithm.remove_unconnected_lines_v2",
        fake_remove_unconnected,
    )
    monkeypatch.setattr(
        "osm_sidewalkreator.processing.draw_missing_crossings_bbox_algorithm.polygonize_lines",
        fake_polygonize,
    )


def test_draw_missing_crossings_success(monkeypatch):
    """Test successful execution of draw missing crossings algorithm."""
    _mock_osm_data(monkeypatch)
    
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "SEARCH_RADIUS_FACTOR": 0.5,
        "OUTPUT_CROSSINGS": "memory:crossings",
        "OUTPUT_KERBS": "memory:kerbs",
    }
    
    # Run using an instance to avoid registry issues in CI
    result = processing.run(DrawMissingCrossingsBBoxAlgorithm(), params)
    
    # Check outputs exist
    assert "OUTPUT_CROSSINGS" in result
    assert "OUTPUT_KERBS" in result
    
    crossings_layer = result["OUTPUT_CROSSINGS"]
    kerbs_layer = result["OUTPUT_KERBS"]
    
    # Verify layers are valid
    assert crossings_layer.isValid()
    assert kerbs_layer.isValid()
    
    # Check CRS
    assert crossings_layer.crs().authid() == "EPSG:4326"
    assert kerbs_layer.crs().authid() == "EPSG:4326"
    
    # Check fields exist
    crossing_fields = [field.name() for field in crossings_layer.fields()]
    assert "crossing_id" in crossing_fields
    assert "length" in crossing_fields
    assert "type" in crossing_fields
    
    kerb_fields = [field.name() for field in kerbs_layer.fields()]
    assert "kerb_id" in kerb_fields
    assert "crossing_id" in kerb_fields
    assert "kerb_type" in kerb_fields


def test_draw_missing_crossings_invalid_extent():
    """Test algorithm with invalid extent."""
    params = {
        "INPUT_EXTENT": "invalid_extent",
        "TIMEOUT": 30,
        "SEARCH_RADIUS_FACTOR": 0.5,
        "OUTPUT_CROSSINGS": "memory:crossings",
        "OUTPUT_KERBS": "memory:kerbs",
    }
    
    with pytest.raises(QgsProcessingException):
        processing.run(DrawMissingCrossingsBBoxAlgorithm(), params)


def test_draw_missing_crossings_with_debug_output(monkeypatch):
    """Test algorithm with optional debug output."""
    _mock_osm_data(monkeypatch)
    
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "SEARCH_RADIUS_FACTOR": 0.5,
        "OUTPUT_CROSSINGS": "memory:crossings",
        "OUTPUT_KERBS": "memory:kerbs",
        "OUTPUT_PROTOBLOCKS_DEBUG": "memory:protoblocks",
    }
    
    result = processing.run(DrawMissingCrossingsBBoxAlgorithm(), params)
    
    # Check debug output is included
    assert "OUTPUT_PROTOBLOCKS_DEBUG" in result
    protoblocks_layer = result["OUTPUT_PROTOBLOCKS_DEBUG"]
    assert protoblocks_layer.isValid()
    assert protoblocks_layer.crs().authid() == "EPSG:4326"