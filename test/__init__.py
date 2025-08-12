# Import qgis if available; otherwise create a minimal stub so tests that
# do not require QGIS can still run without the dependency.
try:  # pragma: no cover - optional dependency
    import qgis  # pylint: disable=W0611  # NOQA
except ImportError:  # pragma: no cover - used when QGIS is absent
    import types
    import sys

    qgis = types.ModuleType("qgis")
    sys.modules["qgis"] = qgis
