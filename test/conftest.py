"""Pytest session-wide QGIS bootstrap to enable Processing in headless CI.

Initializes a minimal QGIS application and loads the Python Processing plugin
so that tests which check for Processing at import-time do not skip.
"""
import os
import sys


def pytest_sessionstart(session):  # noqa: D401
    # Headless Qt
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-qgis")
    try:
        os.makedirs(os.environ["XDG_RUNTIME_DIR"], exist_ok=True)
    except Exception:
        pass

    try:
        from qgis.core import QgsApplication

        prefix = os.environ.get("QGIS_PREFIX_PATH", "/usr")
        QgsApplication.setPrefixPath(prefix, True)
        plugin_path = os.environ.get("QGIS_PLUGINPATH", "/usr/lib/qgis/plugins")
        QgsApplication.setPluginPath(plugin_path)

        # Start a minimal, non-GUI app
        app = QgsApplication([], False)
        app.initQgis()

        # Ensure Python plugin path precedes local packages to avoid name clashes
        qgis_py_plugins = "/usr/share/qgis/python/plugins"
        if qgis_py_plugins in sys.path:
            sys.path.remove(qgis_py_plugins)
        sys.path.insert(0, qgis_py_plugins)

        # Load QGIS 'processing' Python plugin explicitly by path and
        # register native algorithms so the qgis.processing convenience
        # wrapper is ready during module import
        try:
            import importlib.util as ilu

            proc_init = os.path.join(qgis_py_plugins, "processing", "__init__.py")
            spec = ilu.spec_from_file_location("processing", proc_init)
            if spec and spec.loader:
                mod = ilu.module_from_spec(spec)
                sys.modules["processing"] = mod
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                # Initialize Processing framework and add native provider
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
        except Exception:
            # If anything fails, tests may still choose to skip gracefully
            pass
    except Exception:
        # If QGIS is unavailable, tests with @pytest.mark.qgis will skip
        pass

