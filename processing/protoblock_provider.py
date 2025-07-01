# -*- coding: utf-8 -*-

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingProvider
from .protoblock_algorithm import ProtoblockAlgorithm
import os

class ProtoblockProvider(QgsProcessingProvider):

    def __init__(self):
        super().__init__()

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        self.addAlgorithm(ProtoblockAlgorithm())
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
