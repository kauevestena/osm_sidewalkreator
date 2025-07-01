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
from .osm_fetch import osm_query_string_by_bbox, get_osm_data
from .generic_functions import (reproject_layer_localTM, cliplayer_v2,
                                remove_unconnected_lines_v2, polygonize_lines) # using polygonize_lines wrapper for simplicity now
from .parameters import default_widths, highway_tag, CRS_LATLON_4326

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
        return ProtoblockAlgorithm()

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
        input_polygon_layer = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        if input_polygon_layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_POLYGON))

        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)

        # --- 1. Get Input Polygon & Determine BBOX ---
        feedback.pushInfo(self.tr("Determining BBOX from input polygon..."))

        # Ensure input_polygon_layer is in EPSG:4326 for BBOX
        source_crs = input_polygon_layer.sourceCrs()
        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        input_polygon_layer_4326_path = 'memory:input_polygon_4326'
        if source_crs != crs_4326:
            reproject_params = {
                'INPUT': input_polygon_layer,
                'TARGET_CRS': crs_4326,
                'OUTPUT': input_polygon_layer_4326_path
            }
            reproject_result = processing.run("native:reprojectlayer", reproject_params, context=context, feedback=feedback, is_child_algorithm=True)
            if feedback.isCanceled(): return {}
            input_poly_4326_for_bbox = QgsVectorLayer(reproject_result['OUTPUT'], "input_4326", "memory")
        else:
            input_poly_4326_for_bbox = input_polygon_layer

        if not input_poly_4326_for_bbox.isValid() or input_poly_4326_for_bbox.featureCount() == 0:
            raise QgsProcessingException(self.tr("Input polygon layer is invalid or empty after CRS check."))

        # Use extent of the whole layer in 4326
        extent_4326 = input_poly_4326_for_bbox.extent()
        min_lgt, min_lat = extent_4326.xMinimum(), extent_4326.yMinimum()
        max_lgt, max_lat = extent_4326.xMaximum(), extent_4326.yMaximum()

        # Also get the first feature's geometry from original input for clipping (or its union)
        # For simplicity, we'll use the whole input_polygon_layer for clipping later.
        # If we need a single dissolved geometry for clipping:
        # dissolved_input_path = 'memory:dissolved_input'
        # dissolve_params = {'INPUT': input_polygon_layer, 'OUTPUT': dissolved_input_path}
        # processing.run("native:dissolve", dissolve_params, context=context, feedback=feedback, is_child_algorithm=True)
        # clip_poly_layer = QgsVectorLayer(dissolved_input_path, "dissolved_input", "memory")
        # For now, use the input_polygon_layer directly for clipping.

        feedback.setProgress(10)
        if feedback.isCanceled(): return {}

        # --- 2. Fetch OSM Data ---
        feedback.pushInfo(self.tr(f"Fetching OSM street data for BBOX: {min_lat},{min_lgt} to {max_lat},{max_lgt}"))
        query_str = osm_query_string_by_bbox(min_lat, min_lgt, max_lat, max_lgt, interest_key=highway_tag, way=True, node=False, relation=False)

        osm_geojson_str = get_osm_data(query_str, "osm_streets_data", geomtype="LineString", timeout=timeout, return_as_string=True)
        if osm_geojson_str is None:
            raise QgsProcessingException(self.tr("Failed to download or parse OSM data."))

        osm_data_layer_4326 = QgsVectorLayer(osm_geojson_str, "osm_streets_dl_4326", "ogr")
        if not osm_data_layer_4326.isValid():
            raise QgsProcessingException(self.tr("Downloaded OSM data is not a valid layer."))

        feedback.setProgress(30)
        if feedback.isCanceled(): return {}

        # --- 3. Initial OSM Data Processing ---
        feedback.pushInfo(self.tr("Clipping and reprojecting OSM data..."))
        # Clip the downloaded OSM data (in 4326) with the input_poly_4326_for_bbox
        clipped_osm_data_4326_path = 'memory:clipped_osm_4326'
        clipped_osm_layer_4326 = cliplayer_v2(osm_data_layer_4326, input_poly_4326_for_bbox, clipped_osm_data_4326_path)

        if not clipped_osm_layer_4326.isValid() or clipped_osm_layer_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM ways found within the input polygon after clipping."))
            # Create an empty sink and return if no features
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, crs_4326)
            return {self.OUTPUT_PROTOBLOCKS: dest_id}


        # Reproject to local TM
        # bbox_center_x for localTM is from the 4326 extent
        clipped_reproj_layer, local_tm_crs = reproject_layer_localTM(
            clipped_osm_layer_4326,
            outputpath=None, # Memory layer
            layername="clipped_osm_local_tm",
            lgt_0=extent_4326.center().x()
        )
        if not clipped_reproj_layer.isValid():
            raise QgsProcessingException(self.tr("Failed to reproject clipped OSM data."))

        feedback.setProgress(50)
        if feedback.isCanceled(): return {}

        # --- 4. Clean Street Network (Simplified) ---
        feedback.pushInfo(self.tr("Cleaning street network..."))

        # Create a new memory layer for filtered streets
        # Copy fields from clipped_reproj_layer
        filtered_streets_layer = QgsVectorLayer(
            f"LineString?crs={local_tm_crs.authid()}",
            "filtered_streets_local_tm",
            "memory"
        )
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        filtered_streets_dp.addAttributes(clipped_reproj_layer.fields())
        filtered_streets_layer.updateFields()

        features_to_add = []
        highway_field_idx = clipped_reproj_layer.fields().lookupField(highway_tag)

        if highway_field_idx == -1:
            raise QgsProcessingException(self.tr(f"Highway tag '{highway_tag}' not found in OSM data attributes."))

        for f_in in clipped_reproj_layer.getFeatures():
            if feedback.isCanceled(): return {}

            highway_type = f_in.attribute(highway_field_idx)
            if highway_type is None: # Skip features with no highway tag
                continue

            # Get width from default_widths, fallback to 0 if not found (to discard)
            width = default_widths.get(str(highway_type).lower(), 0.0)

            if width >= 0.5: # Corresponds to "width < 0.5" for deletion in original plugin
                new_feat = QgsFeature(filtered_streets_layer.fields())
                new_feat.setGeometry(f_in.geometry())
                new_feat.setAttributes(f_in.attributes())
                # Optionally, add a 'width' attribute if it's not already there from OSM
                # and fill it with the 'width' value determined here if needed downstream.
                # For protoblock generation itself, this specific width value isn't directly used by polygonize.
                features_to_add.append(new_feat)

        if features_to_add:
            filtered_streets_dp.addFeatures(features_to_add)

        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets remaining after filtering by highway type/width criteria."))
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs) # Output in local_tm_crs
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # (Optional but good) Call remove_unconnected_lines_v2
        # This function modifies the layer in-place.
        # Need to ensure it works correctly with memory layers and feedback.
        # For now, let's assume it works; if it causes issues, we might need to adapt it or skip.
        try:
            feedback.pushInfo(self.tr("Removing unconnected lines..."))
            remove_unconnected_lines_v2(filtered_streets_layer) # Modifies in-place
        except Exception as e:
            feedback.pushWarning(self.tr(f"Could not remove unconnected lines: {e}. Proceeding without this step."))


        feedback.setProgress(70)
        if feedback.isCanceled(): return {}

        # --- 5. Polygonize ---
        feedback.pushInfo(self.tr("Polygonizing street network..."))
        # polygonize_lines is a wrapper that returns a layer.
        # It expects an output path, so provide a memory path.
        protoblocks_temp_path = 'memory:protoblocks_raw'

        # The polygonize_lines function from generic_functions needs to be checked if it handles feedback/context correctly for child algorithms
        # For now, calling it directly. If it doesn't propagate cancellation, native:polygonize would be better.
        # Switching to native:polygonize for better control
        polygonize_params = {
            'INPUT': filtered_streets_layer,
            'KEEP_FIELDS': False, # Protoblocks typically don't need street attributes
            'OUTPUT': protoblocks_temp_path
        }
        polygonized_result = processing.run('native:polygonize', polygonize_params, context=context, feedback=feedback, is_child_algorithm=True)
        if feedback.isCanceled(): return {}

        protoblocks_layer = QgsVectorLayer(polygonized_result['OUTPUT'], "protoblocks_final", "memory")

        if not protoblocks_layer.isValid() or protoblocks_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("Polygonization resulted in no protoblock features."))
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs)
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        feedback.setProgress(90)
        if feedback.isCanceled(): return {}

        # --- 6. Output ---
        feedback.pushInfo(self.tr("Writing protoblocks to output..."))
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            protoblocks_layer.fields(), # Fields from polygonized layer
            QgsWkbTypes.Polygon,       # Geometry type is Polygon
            local_tm_crs               # CRS of the generated protoblocks
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))

        total_out_feats = protoblocks_layer.featureCount()
        for i, feat in enumerate(protoblocks_layer.getFeatures()):
            if feedback.isCanceled(): break
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            feedback.setProgress(90 + int( (i + 1) * 10.0 / total_out_feats) ) # Progress from 90 to 100

        if feedback.isCanceled(): return {}

        feedback.setProgress(100)
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        # Clean up any persistent temporary layers if necessary
        # Memory layers are usually handled by QGIS, but explicit deletion can be added if needed
        # e.g., for layers like 'input_polygon_4326_path' if they were file-based.
        return {}

from qgis import processing
from qgis.core import QgsWkbTypes, QgsProcessingException, QgsCoordinateTransform, QgsRectangle
