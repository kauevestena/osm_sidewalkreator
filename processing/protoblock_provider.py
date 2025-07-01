# -*- coding: utf-8 -*-

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider
import os
import traceback

# Try to import the algorithm with detailed logging
try:
    print("[SidewalKreator Provider] Attempting to import ProtoblockAlgorithm...")
    from .protoblock_algorithm import ProtoblockAlgorithm
    print("[SidewalKreator Provider] Successfully imported ProtoblockAlgorithm.")
except Exception as e:
    print(f"[SidewalKreator Provider] CRITICAL: Failed to import ProtoblockAlgorithm: {e}")
    traceback.print_exc()
    ProtoblockAlgorithm = None # Ensure it's None if import fails

class ProtoblockProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        print("[SidewalKreator Provider] In loadAlgorithms...")
        if ProtoblockAlgorithm is not None:
            try:
                print("[SidewalKreator Provider] Attempting to instantiate and add ProtoblockAlgorithm...")
                algo_instance = ProtoblockAlgorithm()
                self.addAlgorithm(algo_instance)
                print("[SidewalKreator Provider] Successfully added ProtoblockAlgorithm.")
            except Exception as e:
                print(f"[SidewalKreator Provider] CRITICAL: Failed to instantiate or add ProtoblockAlgorithm: {e}")
                traceback.print_exc()
        else:
            print("[SidewalKreator Provider] ProtoblockAlgorithm class is None, cannot add algorithm.")
        # Add other algorithms here if any

    def id(self):
        # Unique ID for the provider
        return 'osm_sidewalkreator_protoblock_provider'

    def name(self):
        # Display name for the provider
        return self.tr('OSM SidewalKreator Tools')

    def longName(self):
        # More descriptive name (optional)
        return self.name()

    def icon(self):
        # Path to an icon for the provider (optional)
        # Return QIcon() for no icon or path to .svg/.png
        # Assuming icon.png is in the root of the plugin, like the main plugin icon
        plugin_dir = os.path.dirname(os.path.dirname(__file__)) # Get parent directory (root of plugin)
        icon_path = os.path.join(plugin_dir, 'icon.png')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def helpId(self):
        # Optional: return a QUrl or string to a help resource
        return None
