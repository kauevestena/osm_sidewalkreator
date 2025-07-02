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
        print("[SidewalKreator Provider] ProtoblockProvider __init__ called.")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        print("[SidewalKreator Provider] In loadAlgorithms CALLED.")
        # No algorithms added for this test

    def id(self):
        # Unique ID for the provider
        # Using a simpler ID, ensuring it's unique.
        provider_id = 'sidewalkreator_algorithms_provider'
        print(f"[SidewalKreator Provider] id() called, returning: {provider_id}")
        return provider_id

    def name(self):
        # Display name for the provider
        provider_name = self.tr('SidewalKreator Algorithms')
        print(f"[SidewalKreator Provider] name() called, returning: {provider_name}")
        return provider_name

    def longName(self):
        # More descriptive name (optional)
        long_provider_name = self.name()
        print(f"[SidewalKreator Provider] longName() called, returning: {long_provider_name}")
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
