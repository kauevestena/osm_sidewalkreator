# -*- coding: utf-8 -*-

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider, Qgis, QgsMessageLog  # Added message log
import os
import traceback

# Try to import the algorithms
# It's cleaner to have these imports inside the provider or loadAlgorithms,
# or ensure iface is available if using messageBar at module level.
# For now, assuming iface is available via a global or passed in if this was a class method.
# However, direct iface usage at module level is not standard.
# Let's simplify and assume imports work, errors will be caught by QGIS plugin loader.

from .protoblock_algorithm import ProtoblockAlgorithm
from .protoblock_bbox_algorithm import ProtoblockBboxAlgorithm
from .full_sidewalkreator_polygon_algorithm import FullSidewalkreatorPolygonAlgorithm
from .full_sidewalkreator_bbox_algorithm import (
    FullSidewalkreatorBboxAlgorithm,
)  # Added import
from .draw_missing_crossings_bbox_algorithm import (
    DrawMissingCrossingsBboxAlgorithm,
)  # New algorithm

# It's better practice to handle import errors where these are used (e.g. in loadAlgorithms)
# or ensure the plugin gracefully handles their absence if an import fails.


class ProtoblockProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def loadAlgorithms(self):
        # It's good practice to check if the class was imported successfully before using it
        # However, if an import fails at the top, this code might not even be reached or
        # the class variable would be undefined. The try/except around imports is better.
        # For now, let's assume they imported or are None due to earlier try/except.

        # Re-adding the try-except for robustness during actual addAlgorithm call
        try:
            if ProtoblockAlgorithm:  # Check if class was successfully imported
                alg = ProtoblockAlgorithm()
                self.addAlgorithm(alg)
                try:
                    QgsMessageLog.logMessage(
                        f"Loaded algorithm: {alg.id()}",
                        "SidewalKreator",
                        Qgis.Info,
                    )
                except Exception:
                    pass
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load ProtoblockAlgorithm: {e}",
                "SidewalKreator",
                Qgis.Critical,
            )
            traceback.print_exc()

        try:
            if ProtoblockBboxAlgorithm:  # Check if class was successfully imported
                alg = ProtoblockBboxAlgorithm()
                self.addAlgorithm(alg)
                try:
                    QgsMessageLog.logMessage(
                        f"Loaded algorithm: {alg.id()}",
                        "SidewalKreator",
                        Qgis.Info,
                    )
                except Exception:
                    pass
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load ProtoblockBboxAlgorithm: {e}",
                "SidewalKreator",
                Qgis.Critical,
            )
            traceback.print_exc()

        try:
            if (
                FullSidewalkreatorPolygonAlgorithm
            ):  # Check if class was successfully imported
                alg = FullSidewalkreatorPolygonAlgorithm()
                self.addAlgorithm(alg)
                try:
                    QgsMessageLog.logMessage(
                        f"Loaded algorithm: {alg.id()}",
                        "SidewalKreator",
                        Qgis.Info,
                    )
                except Exception:
                    pass
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load FullSidewalkreatorPolygonAlgorithm: {e}",
                "SidewalKreator",
                Qgis.Critical,
            )
            traceback.print_exc()

        try:
            if (
                FullSidewalkreatorBboxAlgorithm
            ):  # Check if class was successfully imported
                alg = FullSidewalkreatorBboxAlgorithm()
                self.addAlgorithm(alg)
                try:
                    QgsMessageLog.logMessage(
                        f"Loaded algorithm: {alg.id()}",
                        "SidewalKreator",
                        Qgis.Info,
                    )
                except Exception:
                    pass
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load FullSidewalkreatorBboxAlgorithm: {e}",
                "SidewalKreator",
                Qgis.Critical,
            )
            traceback.print_exc()

        try:
            if DrawMissingCrossingsBboxAlgorithm:  # Check if class was successfully imported
                alg = DrawMissingCrossingsBboxAlgorithm()
                self.addAlgorithm(alg)
                try:
                    QgsMessageLog.logMessage(
                        f"Loaded algorithm: {alg.id()}",
                        "SidewalKreator",
                        Qgis.Info,
                    )
                except Exception:
                    pass
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Failed to load DrawMissingCrossingsBboxAlgorithm: {e}",
                "SidewalKreator",
                Qgis.Critical,
            )
            traceback.print_exc()

    def id(self):
        provider_id = "sidewalkreator_algorithms_provider"
        return provider_id

    def name(self):
        # Display name for the provider, using tr() as is standard
        provider_name = self.tr("SidewalKreator")
        return provider_name

    def longName(self):
        # More descriptive name (optional)
        long_provider_name = self.name()  # Uses the translated name
        return long_provider_name

    def icon(self):
        # Path to an icon for the provider (optional)
        try:
            # Corrected path: __file__ is processing/protoblock_provider.py
            # os.path.dirname(__file__) is processing/
            # os.path.dirname(os.path.dirname(__file__)) is plugin_root/
            plugin_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            icon_path = os.path.join(plugin_dir, "icon.png")
            if os.path.exists(icon_path):
                return QIcon(icon_path)
            else:
                # This case might occur if the icon is missing or path is wrong.
                # QGIS might show a default icon or no icon.
                # Avoid using iface here as it might not be available during provider loading.
                QgsMessageLog.logMessage(
                    f"Provider icon not found at: {icon_path}",
                    "SidewalKreator",
                    Qgis.Warning,
                )
                return QIcon()
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error in provider icon() method: {e}",
                "SidewalKreator",
                Qgis.Warning,
            )
            # Avoid using iface here.
            # iface.messageBar().pushMessage("Warning", f"Error loading provider icon: {e}", level=Qgis.Warning)
            return QIcon()

    def helpId(self):
        # Optional: return a QUrl or string to a help resource
        return None
