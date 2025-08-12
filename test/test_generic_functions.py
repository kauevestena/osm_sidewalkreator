import importlib
import importlib.util
import os
import sys
import types

# Ensure project root on path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)


def _load_generic_functions():
    """Import generic_functions without requiring QGIS."""
    try:  # Attempt to import real qgis
        import qgis  # type: ignore  # noqa: F401
    except ImportError:
        qgis = types.ModuleType("qgis")
        sys.modules["qgis"] = qgis

    if "qgis.processing" not in sys.modules:
        processing = types.ModuleType("processing")
        processing.run = lambda *args, **kwargs: None
        sys.modules["qgis.processing"] = processing
        sys.modules["processing"] = processing
        sys.modules["qgis"].processing = processing

    if "qgis.core" not in sys.modules:
        core = types.ModuleType("qgis.core")

        class Dummy:
            def __init__(self, *args, **kwargs):
                pass

        class DummyProject:
            @staticmethod
            def instance():
                return Dummy()

        core.edit = lambda *args, **kwargs: None
        attrs = [
            "Qgis",
            "QgsApplication",
            "QgsCoordinateReferenceSystem",
            "QgsCoordinateTransform",
            "QgsFeature",
            "QgsFeatureRequest",
            "QgsField",
            "QgsGeometry",
            "QgsGeometryUtils",
            "QgsMultiPoint",
            "QgsPoint",
            "QgsPointXY",
            "QgsProcessing",
            "QgsProject",
            "QgsProperty",
            "QgsRasterLayer",
            "QgsSpatialIndex",
            "QgsVector",
            "QgsVectorLayer",
            "QgsProcessingContext",
        ]
        for attr in attrs:
            setattr(core, attr, Dummy)
        core.QgsProject = DummyProject
        sys.modules["qgis.core"] = core

    try:
        import PyQt5  # type: ignore  # noqa: F401
    except ImportError:
        pyqt = types.ModuleType("PyQt5")
        qtcore = types.ModuleType("PyQt5.QtCore")

        class QVariant:
            Double = 0
            String = 1

        qtcore.QVariant = QVariant
        pyqt.QtCore = qtcore
        sys.modules["PyQt5"] = pyqt
        sys.modules["PyQt5.QtCore"] = qtcore

    return importlib.import_module("generic_functions")


gf = _load_generic_functions()


def test_create_dir_ifnotexists_creates_directory(tmp_path):
    target = tmp_path / "newdir"
    assert not target.exists()
    gf.create_dir_ifnotexists(str(target))
    assert target.exists() and target.is_dir()


def test_get_major_dif_signed_returns_max_difference():
    result, key = gf.get_major_dif_signed(10, {"a": 8, "b": 15})
    assert result == 15
    assert key == "b"


def test_get_major_dif_signed_returns_input_when_close():
    result, key = gf.get_major_dif_signed(10, {"a": 9.8})
    assert result == 10
    assert key == "a"


def test_wipe_folder_files_removes_contents(tmp_path):
    file1 = tmp_path / "a.txt"
    file2 = tmp_path / "b.txt"
    file1.write_text("x")
    file2.write_text("y")
    gf.wipe_folder_files(str(tmp_path))
    assert not any(tmp_path.iterdir())

