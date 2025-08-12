import pytest

pytest.importorskip("qgis")
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY

from processing.sidewalk_generation_logic import (
    filter_polygons_by_area_perimeter_ratio,
)
from parameters import min_area_perimeter_ratio
from .utilities import get_qgis_app

pytestmark = pytest.mark.qgis


@pytest.fixture(scope="module", autouse=True)
def qgis_env():
    app, _, _, _ = get_qgis_app()
    assert app is not None
    return app


def _create_polygon(coords):
    return QgsGeometry.fromPolygonXY([coords + [coords[0]]])


def test_filter_polygons_by_area_perimeter_ratio():
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "polys", "memory")
    dp = layer.dataProvider()

    # Square polygon - ratio 0.25
    square = QgsFeature()
    square.setGeometry(
        _create_polygon(
            [
                QgsPointXY(0, 0),
                QgsPointXY(1, 0),
                QgsPointXY(1, 1),
                QgsPointXY(0, 1),
            ]
        )
    )

    # Very thin rectangle - ratio ~0.005
    thin = QgsFeature()
    thin.setGeometry(
        _create_polygon(
            [
                QgsPointXY(0, 0),
                QgsPointXY(10, 0),
                QgsPointXY(10, 0.01),
                QgsPointXY(0, 0.01),
            ]
        )
    )

    dp.addFeatures([square, thin])
    layer.updateExtents()

    removed = filter_polygons_by_area_perimeter_ratio(
        layer, min_area_perimeter_ratio
    )
    assert removed == 1
    assert layer.featureCount() == 1
