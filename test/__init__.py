# Import QGIS libs to set the correct SIP API version when available.
# Allow the tests to run without QGIS by ignoring missing module errors.
try:
    import qgis  # pylint: disable=W0611  # NOQA
except ModuleNotFoundError:
    pass
