# -*- coding: utf-8 -*-

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider
import os
import traceback

# Try to import the algorithm with detailed logging
try:
    # print("[SidewalKreator Provider] Attempting to import ProtoblockAlgorithm...") # Removed
    from .protoblock_algorithm import ProtoblockAlgorithm
    # print("[SidewalKreator Provider] Successfully imported ProtoblockAlgorithm.") # Removed
except Exception as e:
    # print(f"[SidewalKreator Provider] CRITICAL: Failed to import ProtoblockAlgorithm: {e}") # Removed
    # Consider logging to QGIS message bar for critical import failures even in non-debug state
    iface.messageBar().pushMessage("Error", f"Failed to import ProtoblockAlgorithm: {e}", level=Qgis.Critical)
    traceback.print_exc() # Keep traceback for critical errors
    ProtoblockAlgorithm = None # Ensure it's None if import fails

class ProtoblockProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()
        # print("[SidewalKreator Provider] ProtoblockProvider __init__ called.") # Removed

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        # print("[SidewalKreator Provider] In loadAlgorithms CALLED.") # Removed
        if ProtoblockAlgorithm is not None:
            try:
                # print("[SidewalKreator Provider] Attempting to instantiate and add ProtoblockAlgorithm...") # Removed
                algo_instance = ProtoblockAlgorithm()
                self.addAlgorithm(algo_instance)
                # print("[SidewalKreator Provider] Successfully added ProtoblockAlgorithm.") # Removed
            except Exception as e:
                # print(f"[SidewalKreator Provider] CRITICAL: Failed to instantiate or add ProtoblockAlgorithm: {e}") # Removed
                # Log critical error to QGIS message bar
                iface.messageBar().pushMessage("Error", f"Failed to load ProtoblockAlgorithm: {e}", level=Qgis.Critical)
                traceback.print_exc() # Keep traceback for critical errors
        else:
            # print("[SidewalKreator Provider] ProtoblockAlgorithm class is None, cannot add algorithm.") # Removed
            iface.messageBar().pushMessage("Warning", "ProtoblockAlgorithm class not available to provider.", level=Qgis.Warning)

        # Add other algorithms here if any

    def id(self):
        provider_id = 'sidewalkreator_algorithms_provider'
        # print(f"[SidewalKreator Provider] id() CALLED, returning: {provider_id}") # Removed
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
