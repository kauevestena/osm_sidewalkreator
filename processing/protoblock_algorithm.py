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
import math # For math.isfinite

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

        if not actual_input_layer.isValid() or actual_input_layer.featureCount() == 0:
            raise QgsProcessingException(self.tr("Materialized input polygon layer is invalid or empty. Cannot proceed."))

        feedback.pushInfo(f"Input polygon layer: {actual_input_layer.name()} | Source: {actual_input_layer.source()} with {actual_input_layer.featureCount()} features.")

        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        feedback.pushInfo(f"Timeout: {timeout} seconds")

        feedback.pushInfo("Step 2: Calculating BBOX and generating OSM query string...")

        # Ensure input_poly_for_bbox is in EPSG:4326
        source_crs = actual_input_layer.sourceCrs()
        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        input_poly_for_bbox = actual_input_layer
        if source_crs.authid() != crs_4326.authid(): # Compare authids for robustness
            feedback.pushInfo(f"Reprojecting input layer from {source_crs.authid()} to EPSG:4326 for BBOX calculation.")
            reproject_params = {
                'INPUT': actual_input_layer,
                'TARGET_CRS': crs_4326,
                'OUTPUT': 'memory:input_reprojected_for_bbox'
            }
            sub_feedback_reproject = QgsProcessingMultiStepFeedback(1, feedback) # Child feedback
            sub_feedback_reproject.setCurrentStep(0)
            reproject_result = processing.run("native:reprojectlayer", reproject_params, context=context, feedback=sub_feedback_reproject, is_child_algorithm=True)
            if sub_feedback_reproject.isCanceled(): return {}

            input_poly_for_bbox = QgsVectorLayer(reproject_result['OUTPUT'], "input_reprojected_for_bbox_layer", "memory")
            if not input_poly_for_bbox.isValid() or input_poly_for_bbox.featureCount() == 0:
                raise QgsProcessingException(self.tr("Failed to reproject, or reprojected input layer is empty."))
        else:
            feedback.pushInfo("Input layer is already in EPSG:4326.")

        # Calculate BBOX from the (potentially reprojected) layer
        extent_4326 = input_poly_for_bbox.extent()
        if extent_4326.isNull() or not all(map(math.isfinite, [extent_4326.xMinimum(), extent_4326.yMinimum(), extent_4326.xMaximum(), extent_4326.yMaximum()])):
            raise QgsProcessingException(self.tr(f"Cannot determine a valid bounding box. Extent: {extent_4326.toString()}. Ensure the input layer '{input_poly_for_bbox.name()}' contains valid geometries and is not empty."))

        min_lgt, min_lat = extent_4326.xMinimum(), extent_4326.yMinimum()
        max_lgt, max_lat = extent_4326.xMaximum(), extent_4326.yMaximum()
        feedback.pushInfo(f"Calculated BBOX (EPSG:4326): MinLon={min_lgt}, MinLat={min_lat}, MaxLon={max_lgt}, MaxLat={max_lat}")

        # Generate OSM Query String
        query_str = osm_query_string_by_bbox(min_lat, min_lgt, max_lat, max_lgt,
                                             interest_key=highway_tag, way=True, node=False, relation=False)
        feedback.pushInfo(f"Generated OSM Query (first 100 chars): {query_str[:100]}...")

        # --- Step 3: Fetch OSM Data ---
        feedback.pushInfo("Step 3: Fetching OSM data...")
        osm_geojson_str = get_osm_data(query_str, "osm_streets_data_algo",
                                       geomtype="LineString", timeout=timeout,
                                       return_as_string=True)

        if osm_geojson_str is None:
            raise QgsProcessingException(self.tr("Failed to download or parse OSM data (returned None)."))

        osm_data_layer_4326 = QgsVectorLayer(osm_geojson_str, "osm_streets_dl_4326_algo", "ogr")
        if not osm_data_layer_4326.isValid():
            # Attempt to get more details if the string was non-empty but layer is invalid
            details = ""
            if osm_geojson_str: # Check if string is not empty
                details = f" GeoJSON string started with: {osm_geojson_str[:200]}"
            raise QgsProcessingException(self.tr(f"Downloaded OSM data did not form a valid vector layer.{details}"))

        feedback.pushInfo(f"OSM data fetched successfully. Layer '{osm_data_layer_4326.name()}' created with {osm_data_layer_4326.featureCount()} features (in EPSG:4326).")

        # --- Step 4: Clip and Reproject Fetched OSM Data ---
        feedback.pushInfo("Step 4: Clipping and reprojecting fetched OSM data...")

        # The layer used for BBOX extent was input_poly_for_bbox (which is actual_input_layer reprojected to 4326 if needed)
        # We should use this same layer for clipping.
        clipped_osm_data_4326_path = 'memory:clipped_osm_data_4326_algo'
        clipped_osm_layer_4326 = cliplayer_v2(osm_data_layer_4326, input_poly_for_bbox, clipped_osm_data_4326_path)

        if not clipped_osm_layer_4326.isValid():
            # This might happen if cliplayer_v2 returns None or an invalid layer on error
            raise QgsProcessingException(self.tr("Clipping of OSM data failed."))

        feedback.pushInfo(f"OSM data clipped successfully. Features after clipping: {clipped_osm_layer_4326.featureCount()}")

        if clipped_osm_layer_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM ways found within the precise input polygon after clipping. Output will be empty."))
            # Prepare an empty sink and return if no features
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, crs_4326) # Use crs_4326 or local_tm_crs if preferred for empty output
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # Reproject Clipped Data to Local TM
        # extent_4326 was calculated earlier from input_poly_for_bbox
        clipped_reproj_layer, local_tm_crs = reproject_layer_localTM(
            clipped_osm_layer_4326,
            outputpath=None,
            layername="clipped_osm_local_tm_algo",
            lgt_0=extent_4326.center().x() # Use the center of the original input polygon's extent in EPSG:4326
        )
        if not clipped_reproj_layer.isValid():
            raise QgsProcessingException(self.tr("Failed to reproject clipped OSM data to local TM."))

        feedback.pushInfo(f"Clipped OSM data reprojected to local TM ({local_tm_crs.authid()}). Features: {clipped_reproj_layer.featureCount()}")

        # --- Step 5: Clean Street Network ---
        feedback.pushInfo("Step 5: Cleaning street network (filtering by highway type/width)...")

        filtered_streets_layer = QgsVectorLayer(
            f"LineString?crs={local_tm_crs.authid()}",
            "filtered_streets_local_tm_algo",
            "memory"
        )
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        # Ensure clipped_reproj_layer has fields before trying to add them
        if clipped_reproj_layer.fields().count() > 0:
            filtered_streets_dp.addAttributes(clipped_reproj_layer.fields())
        else: # Add at least one dummy field if there are no fields, e.g. if source was simplified
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])

        filtered_streets_layer.updateFields() # Important after adding attributes

        features_to_add_to_filtered = []
        highway_field_idx = clipped_reproj_layer.fields().lookupField(highway_tag)

        if highway_field_idx == -1:
            # If no highway_tag, we might want to copy all lines or raise an error.
            # For protoblocks, highway_tag is essential.
            raise QgsProcessingException(self.tr(f"Highway tag '{highway_tag}' not found in attributes of reprojected OSM data. Cannot filter streets."))

        for f_in in clipped_reproj_layer.getFeatures():
            if feedback.isCanceled(): return {}

            highway_type_attr = f_in.attribute(highway_field_idx)
            # Ensure highway_type_attr is treated as a string for .lower() and dictionary lookup
            highway_type_str = str(highway_type_attr).lower() if highway_type_attr is not None else ""

            width = default_widths.get(highway_type_str, 0.0)

            if width >= 0.5: # Corresponds to "width < 0.5" for deletion in original plugin logic
                new_feat = QgsFeature(filtered_streets_layer.fields())
                new_feat.setGeometry(f_in.geometry())
                new_feat.setAttributes(f_in.attributes())
                features_to_add_to_filtered.append(new_feat)

        if features_to_add_to_filtered:
            filtered_streets_dp.addFeatures(features_to_add_to_filtered)

        feedback.pushInfo(f"Streets filtered by highway type/width. Kept {filtered_streets_layer.featureCount()} features.")

        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets remaining after filtering by highway type/width. Output will be empty."))
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs)
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # Remove unconnected lines
        try:
            feedback.pushInfo(self.tr("Attempting to remove unconnected lines..."))
            # remove_unconnected_lines_v2 modifies the layer in-place
            remove_unconnected_lines_v2(filtered_streets_layer)
            feedback.pushInfo(f"After removing unconnected lines, {filtered_streets_layer.featureCount()} features remain.")
        except Exception as e:
            feedback.pushWarning(self.tr(f"Could not remove unconnected lines due to an error: {e}. Proceeding with current street network."))
            # Optionally, log traceback.print_exc() here for more detail if needed during debugging

        # --- Step 6: Polygonize Cleaned Streets and Output Protoblocks ---
        feedback.pushInfo("Step 6: Polygonizing cleaned street network...")

        # Ensure polygonize_lines from generic_functions.py returns a QgsVectorLayer
        # and handles memory layer output correctly.
        # It internally calls 'native:polygonize'.
        protoblocks_layer = polygonize_lines(
            filtered_streets_layer,
            outputlayer='memory:protoblocks_temp_algo',
            keepfields=False # Protoblocks generally don't need attributes from lines
        )

        if not protoblocks_layer or not protoblocks_layer.isValid():
            raise QgsProcessingException(self.tr("Polygonization failed or returned an invalid layer."))

        feedback.pushInfo(f"Polygonization successful. Generated {protoblocks_layer.featureCount()} protoblock features.")

        if protoblocks_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("Polygonization resulted in no protoblock features. Output will be empty."))
            # Fallthrough to create an empty sink with correct type and CRS

        # Prepare the final output sink with the correct CRS and fields
        # The CRS of protoblocks_layer should be local_tm_crs
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            protoblocks_layer.fields(), # Fields from the newly created protoblocks_layer
            QgsWkbTypes.Polygon,    # Expected geometry type
            local_tm_crs            # CRS of the generated protoblocks
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))

        # Add features to the sink if any were generated
        if protoblocks_layer.featureCount() > 0:
            total_out_feats = protoblocks_layer.featureCount()
            for i, feat in enumerate(protoblocks_layer.getFeatures()):
                if feedback.isCanceled(): break
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                # Update progress based on adding features to sink, assuming this is the last major step
                # If polygonization was step 90, this can be 90-100
                # Let's say cleaning was 80, polygonize 90, this is 90-100
                # We need a more consistent progress update strategy across steps.
                # For now, just a general progress for this part.
                feedback.setProgress(int(80 + (i + 1) * 20.0 / total_out_feats) )


        feedback.pushInfo("Step 6: Protoblock generation complete. Output written.")
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        # Clean up any persistent temporary layers if necessary
        # Memory layers are usually handled by QGIS, but explicit deletion can be added if needed
        # e.g., for layers like 'input_polygon_4326_path' if they were file-based.
        return {}

from qgis import processing
from qgis.core import QgsWkbTypes, QgsProcessingException, QgsCoordinateTransform, QgsRectangle
