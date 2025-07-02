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
        # This tr method is fine, but we'll avoid using it in name/longName for this test
        return QCoreApplication.translate('Processing', string)

    def loadAlgorithms(self):
        print("[SidewalKreator Provider] In loadAlgorithms CALLED. (No algorithms added for this test)")
        # No algorithms added for this test

    def id(self):
        provider_id = 'sidewalkreator_algorithms_provider'
        print(f"[SidewalKreator Provider] id() CALLED, returning: {provider_id}")
        return provider_id

    def name(self):
        provider_name = "SidewalKreator Algorithms Test" # Hardcoded, no tr()
        print(f"[SidewalKreator Provider] name() CALLED, returning: {provider_name}")
        return provider_name

    def longName(self):
        long_provider_name = "SidewalKreator Algorithms Test Long Name" # Hardcoded, no tr()
        print(f"[SidewalKreator Provider] longName() CALLED, returning: {long_provider_name}")
        return long_provider_name

    def icon(self):
        print("[SidewalKreator Provider] icon() CALLED, returning empty QIcon()")
        return QIcon() # Simplest valid return

    def helpId(self):
        # Optional: return a QUrl or string to a help resource
        return None
