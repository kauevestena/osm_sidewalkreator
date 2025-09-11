# import qgis libs so that we set the correct sip api version when available
try:
    import qgis  # pylint: disable=W0611  # NOQA
except ImportError:  # pragma: no cover - qgis not installed
    pass
