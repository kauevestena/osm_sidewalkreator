import json
import tempfile
import pytest
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingException,
)
from qgis import processing

from .utilities import get_qgis_app
from processing.protoblock_provider import ProtoblockProvider


@pytest.fixture(scope="module", autouse=True)
def qgis_env():
    """Initialise QGIS and register provider once for tests."""
    app, _, _, _ = get_qgis_app()
    assert app is not None
    provider = ProtoblockProvider()
    QgsApplication.processingRegistry().addProvider(provider)
    return app


# ---------------------- Protoblock Algorithm Tests ----------------------

def _square_roads_geojson():
    return json.dumps(
        {
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
        }
    )


def _simple_polygon_layer():
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "poly", "memory")
    dp = layer.dataProvider()
    feat = QgsFeature()
    feat.setGeometry(
        QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(-1, -1),
                QgsPointXY(2, -1),
                QgsPointXY(2, 2),
                QgsPointXY(-1, 2),
                QgsPointXY(-1, -1),
            ]]
        )
    )
    dp.addFeatures([feat])
    layer.updateExtents()
    return layer


def test_generateprotoblocks_success(monkeypatch):
    geojson = _square_roads_geojson()
    monkeypatch.setattr(
        "processing.protoblock_algorithm.osm_query_string_by_bbox", lambda *a, **k: "dummy"
    )
    monkeypatch.setattr(
        "processing.protoblock_algorithm.get_osm_data", lambda *a, **k: geojson
    )
    params = {
        "INPUT_POLYGON": _simple_polygon_layer(),
        "TIMEOUT": 30,
        "OUTPUT_PROTOBLOCKS": "memory:protoblocks",
    }
    result = processing.run(
        "sidewalkreator_algorithms_provider:generateprotoblocksfromosm", params
    )
    out_layer = result["OUTPUT_PROTOBLOCKS"]
    assert out_layer.isValid()
    assert out_layer.crs().authid() == "EPSG:4326"
    assert out_layer.featureCount() == 1
    assert out_layer.fields().count() == 0


def test_generateprotoblocks_failure():
    params = {
        "INPUT_POLYGON": QgsVectorLayer("Polygon?crs=EPSG:4326", "empty", "memory"),
        "TIMEOUT": 30,
        "OUTPUT_PROTOBLOCKS": "memory:out",
    }
    with pytest.raises(QgsProcessingException):
        processing.run(
            "sidewalkreator_algorithms_provider:generateprotoblocksfromosm",
            params,
        )


# ---------------------- Full Sidewalkreator BBOX Algorithm Tests ----------------------

def _patch_full_bbox_alg(monkeypatch, raise_in_generation=False):
    geojson = _square_roads_geojson()

    def fake_get_osm_data(**kwargs):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".geojson")
        tmp.write(geojson.encode("utf-8"))
        tmp.flush()
        tmp.close()
        return tmp.name

    def fake_reproject(layer, outputpath=None, layername=None, lgt_0=None):
        from qgis.core import QgsCoordinateReferenceSystem

        return layer, QgsCoordinateReferenceSystem("EPSG:4326")

    def fake_clip(inputlayer, overlay_lyr, outputlayer=None):
        return inputlayer

    def fake_polygonize(inputlines, outputlayer="TEMPORARY_OUTPUT", keepfields=True):
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

    def fake_clean(osm_layer, poly_layer, crs, name, feedback, context):
        return osm_layer

    def fake_generate(*args, **kwargs):
        if raise_in_generation:
            raise QgsProcessingException("forced failure")
        sidewalks = QgsVectorLayer("LineString?crs=EPSG:4326", "sidewalks", "memory")
        dp = sidewalks.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(
            QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)])
        )
        dp.addFeature(feat)
        sidewalks.updateExtents()
        return {
            "sidewalk_lines": sidewalks,
            "exclusion_zones": QgsVectorLayer(
                "Polygon?crs=EPSG:4326", "excl", "memory"
            ),
            "sure_zones": QgsVectorLayer(
                "Polygon?crs=EPSG:4326", "sure", "memory"
            ),
            "width_adjusted_streets": args[0],
        }

    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.get_osm_data", fake_get_osm_data
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.osm_query_string_by_bbox",
        lambda **k: "dummy",
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.reproject_layer_localTM",
        fake_reproject,
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.cliplayer_v2", fake_clip
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.polygonize_lines",
        fake_polygonize,
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.clean_street_network_data",
        fake_clean,
    )
    monkeypatch.setattr(
        "processing.full_sidewalkreator_bbox_algorithm.generate_sidewalk_geometries_and_zones",
        fake_generate,
    )


def test_full_bbox_success(monkeypatch):
    _patch_full_bbox_alg(monkeypatch)
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
        "DEFAULT_WIDTH": 2.0,
        "MIN_WIDTH": 1.0,
        "MAX_WIDTH": 5.0,
        "STREET_CLASSES": [10],
        "OUTPUT_SIDEWALKS": "memory:sidewalks",
    }
    result = processing.run(
        "sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox", params
    )
    layer = result["OUTPUT_SIDEWALKS"]
    assert layer.isValid()
    assert layer.crs().authid() == "EPSG:4326"
    assert layer.featureCount() == 1


def test_full_bbox_failure(monkeypatch):
    _patch_full_bbox_alg(monkeypatch, raise_in_generation=True)
    params = {
        "INPUT_EXTENT": "0,0,1,1 [EPSG:4326]",
        "TIMEOUT": 30,
        "GET_BUILDING_DATA": False,
        "DEFAULT_WIDTH": 2.0,
        "MIN_WIDTH": 1.0,
        "MAX_WIDTH": 5.0,
        "STREET_CLASSES": [10],
        "OUTPUT_SIDEWALKS": "memory:sidewalks",
    }
    with pytest.raises(QgsProcessingException):
        processing.run(
            "sidewalkreator_algorithms_provider:osm_sidewalkreator_full_bbox",
            params,
        )
