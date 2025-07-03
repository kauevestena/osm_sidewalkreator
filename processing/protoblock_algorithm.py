# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingContext, QgsFeatureSink,
                       QgsProcessingParameterEnum, QgsProcessingMultiStepFeedback,
                       QgsVectorLayer)
from qgis.core import (QgsProcessingParameterNumber, QgsCoordinateReferenceSystem,
                       QgsProject, QgsFeatureRequest, QgsFields, QgsField, QgsFeature, edit)
from qgis.PyQt.QtCore import QVariant

# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (reproject_layer_localTM, cliplayer_v2,
                                remove_unconnected_lines_v2, polygonize_lines) # Using polygonize_lines wrapper for now
from ..parameters import default_widths, highway_tag, CRS_LATLON_4326

class ProtoblockAlgorithm(QgsProcessingAlgorithm):
    """
    Generates protoblocks by fetching OSM street data within an input polygon,
    processing it, and then polygonizing the street network.
    """
    INPUT_POLYGON = 'INPUT_POLYGON'
    TIMEOUT = 'TIMEOUT'
    OUTPUT_PROTOBLOCKS = 'OUTPUT_PROTOBLOCKS'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        print("[SidewalKreator] Attempting to create instance of ProtoblockAlgorithm")
        try:
            instance = ProtoblockAlgorithm()
            print("[SidewalKreator] Successfully created instance of ProtoblockAlgorithm")
            return instance
        except Exception as e:
            print(f"[SidewalKreator] Error in ProtoblockAlgorithm createInstance or __init__: {e}")
            import traceback
            traceback.print_exc()
            raise # Re-raise the exception to allow QGIS to handle it as before

    def name(self):
        return 'generateprotoblocksfromosm'

    def displayName(self):
        return self.tr('Generate Protoblocks from OSM Data in Polygon')

    def group(self):
        return self.tr('OSM SidewalKreator')

    def groupId(self):
        return 'osmsidewalkreator'

    def shortHelpString(self):
        return self.tr("Generates protoblocks by fetching and processing OSM street data within the extent of an input polygon layer.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGON,
                self.tr('Input Area Polygon Layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr('OSM Download Timeout (seconds)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=60,
                minValue=10,
                maxValue=300
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS,
                self.tr('Output Protoblocks')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo("Step 1: Algorithm started, imports un-commented, retrieving parameters.")

        input_polygon_feature_source = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        if input_polygon_feature_source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_POLYGON))

        # Materialize the layer to access its properties like name and source
        # Note: materialize can be slow for complex sources, but necessary here for info.
        # It also might load all features into memory depending on the source.
        actual_input_layer = input_polygon_feature_source.materialize(QgsFeatureRequest())
        if actual_input_layer is None:
            raise QgsProcessingException(self.tr("Failed to materialize input polygon layer."))

        feedback.pushInfo(f"Input polygon layer: {actual_input_layer.name()} | Source: {actual_input_layer.source()}")

        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        feedback.pushInfo(f"Timeout: {timeout} seconds")

        # Define fields for the output layer (can be empty if no attributes)
        fields = QgsFields()
        # Example: fields.append(QgsField("id", QVariant.Int))

        # Prepare the output sink
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            fields,
            QgsWkbTypes.Polygon,
            QgsCoordinateReferenceSystem("EPSG:4326") # Dummy CRS for now
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))

        feedback.pushInfo("Step 1: Finished. Sink prepared for empty output. Imports and params retrieved.")
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        # Clean up any persistent temporary layers if necessary
        # Memory layers are usually handled by QGIS, but explicit deletion can be added if needed
        # e.g., for layers like 'input_polygon_4326_path' if they were file-based.
        return {}

from qgis import processing
from qgis.core import QgsWkbTypes, QgsProcessingException, QgsCoordinateTransform, QgsRectangle
