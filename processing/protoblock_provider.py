# -*- coding: utf-8 -*-

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider
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
# It's better practice to handle import errors where these are used (e.g. in loadAlgorithms)
# or ensure the plugin gracefully handles their absence if an import fails.

class ProtoblockProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        # It's good practice to check if the class was imported successfully before using it
        # However, if an import fails at the top, this code might not even be reached or
        # the class variable would be undefined. The try/except around imports is better.
        # For now, let's assume they imported or are None due to earlier try/except.

        # Re-adding the try-except for robustness during actual addAlgorithm call
        try:
            if ProtoblockAlgorithm: # Check if class was successfully imported
                self.addAlgorithm(ProtoblockAlgorithm())
        except Exception as e:
            # Use QgsMessageLog for errors not tied to iface, or pass iface if available
            print(f"CRITICAL: Failed to load ProtoblockAlgorithm: {e}") # Fallback print
            traceback.print_exc()

        try:
            if ProtoblockBboxAlgorithm: # Check if class was successfully imported
                self.addAlgorithm(ProtoblockBboxAlgorithm())
        except Exception as e:
            print(f"CRITICAL: Failed to load ProtoblockBboxAlgorithm: {e}") # Fallback print
            traceback.print_exc()

    def id(self):
        provider_id = 'sidewalkreator_algorithms_provider'
        return provider_id

    def name(self):
        # Display name for the provider, using tr() as is standard
        provider_name = self.tr('SidewalKreator Algorithms')
        # print(f"[SidewalKreator Provider] name() CALLED, returning: {provider_name}") # Removed
        return provider_name

    def longName(self):
        # More descriptive name (optional)
        long_provider_name = self.name() # Uses the translated name
        # print(f"[SidewalKreator Provider] longName() CALLED, returning: {long_provider_name}") # Removed
        return long_provider_name

    def icon(self):
        # print("[SidewalKreator Provider] icon() CALLED.") # Removed
        # Path to an icon for the provider (optional)
        try:
            plugin_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            icon_path = os.path.join(plugin_dir, 'icon.png')
            if os.path.exists(icon_path):
                # print(f"[SidewalKreator Provider] Icon path found: {icon_path}") # Removed
                return QIcon(icon_path)
            else:
                # print(f"[SidewalKreator Provider] Icon path NOT found: {icon_path}, returning empty QIcon().") # Removed
                return QIcon()
        except Exception as e:
            # print(f"[SidewalKreator Provider] Error in icon() method: {e}, returning empty QIcon().") # Removed
            # Log to QGIS message bar if icon loading fails unexpectedly
            iface.messageBar().pushMessage("Warning", f"Error loading provider icon: {e}", level=Qgis.Warning)
            return QIcon()

    def helpId(self):
        # Optional: return a QUrl or string to a help resource
        return None
