"""
Ensure QGIS + Processing are initialized during test collection.

Python auto-imports this module if present on sys.path (the CWD is on sys.path
when running pytest). This prepares a headless QGIS environment so tests that
check Processing at import-time don’t skip.
"""
import os

# Make Qt headless-friendly
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-qgis")
try:
    os.makedirs(os.environ["XDG_RUNTIME_DIR"], exist_ok=True)
except Exception:
    pass

try:
    import sys
    from qgis.core import QgsApplication
    import sys as _sys

    # Set prefix path if not already configured
    QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", "/usr"), True)

    # Create an application if needed and initialize QGIS
    if not QgsApplication.instance():
        # Avoid pulling in full Qt GUI; QGIS handles internals as needed
        _app = QgsApplication(sys.argv, False)
    if not QgsApplication.isInitialized():
        QgsApplication.initQgis()

    # Ensure QGIS Python plugin path has priority over local packages
    try:
        qgis_plugins_path = "/usr/share/qgis/python/plugins"
        if qgis_plugins_path not in _sys.path:
            _sys.path.insert(0, qgis_plugins_path)
        else:
            # Move it to front to avoid local 'processing' package shadowing
            _sys.path.remove(qgis_plugins_path)
            _sys.path.insert(0, qgis_plugins_path)
    except Exception:
        pass

    # Initialize Processing and native algorithms if available
    try:
        # Force-import the QGIS Processing plugin (not the local package)
        try:
            # Explicitly load QGIS 'processing' plugin module by path to avoid
            # shadowing from local package named 'processing'. This will
            # monkey-patch qgis.processing functions.
            import importlib.util as _ilu
            _proc_path = "/usr/share/qgis/python/plugins/processing/__init__.py"
            _spec = _ilu.spec_from_file_location("processing", _proc_path)
            if _spec and _spec.loader:
                import sys as _sys2
                _mod = _ilu.module_from_spec(_spec)
                _sys2.modules['processing'] = _mod
                _spec.loader.exec_module(_mod)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            from processing.core.Processing import Processing  # type: ignore
            Processing.initialize()
        except Exception:
            pass
        # Mark processing as loaded for qgis.processing convenience wrapper
        try:
            import qgis.utils as qutils  # type: ignore
            if isinstance(getattr(qutils, "plugins", None), dict):
                qutils.plugins.setdefault("processing", object())
        except Exception:
            pass
        try:
            from qgis.analysis import QgsNativeAlgorithms
            QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
        except Exception:
            pass
        # Ensure processing module is importable and algorithms are discoverable
        try:
            import processing  # noqa: F401
            # Probe a built-in algorithm to warm up registry
            try:
                processing.algorithmHelp("native:buffer")
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        # Processing might not be available in some environments
        pass
except Exception:
    # If QGIS imports fail, leave environment unchanged; tests will handle skips
    pass
