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
        # print("[SidewalKreator] Attempting to create instance of ProtoblockAlgorithm") # Removed
        try:
            instance = ProtoblockAlgorithm()
            # print("[SidewalKreator] Successfully created instance of ProtoblockAlgorithm") # Removed
            return instance
        except Exception as e:
            # print(f"[SidewalKreator] Error in ProtoblockAlgorithm createInstance or __init__: {e}") # Removed
            # It's better to let QGIS handle the display of critical errors if instantiation fails.
            # Re-raising is good. Logging to QGIS message bar or log panel is also an option for critical plugin errors.
            # For now, just re-raise.
            # import traceback # Not needed if not printing exc here
            # traceback.print_exc() # Not needed if not printing exc here
            raise

    def name(self):
        return 'generateprotoblocksfromosm'

    def displayName(self):
        return self.tr('Generate Protoblocks from OSM Data in Polygon')

    # Removed group(self) and groupId(self) to place algorithm directly under provider

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
        feedback.pushInfo(self.tr("Algorithm started: Generate Protoblocks from OSM Data in Polygon")) # General start message

        input_polygon_feature_source = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        if input_polygon_feature_source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_POLYGON))

        actual_input_layer = input_polygon_feature_source.materialize(QgsFeatureRequest())
        if actual_input_layer is None:
            raise QgsProcessingException(self.tr("Failed to materialize input polygon layer."))

        if not actual_input_layer.isValid() or actual_input_layer.featureCount() == 0:
            raise QgsProcessingException(self.tr("Materialized input polygon layer is invalid or empty. Cannot proceed."))

        feedback.pushInfo(self.tr(f"Using input polygon layer: {actual_input_layer.name()} ({actual_input_layer.featureCount()} features)"))

        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        # feedback.pushInfo(f"Timeout: {timeout} seconds") # Might be too verbose for normal operation

        feedback.pushInfo(self.tr("Calculating BBOX for OSM query..."))

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
        # feedback.pushInfo(f"Generated OSM Query (first 100 chars): {query_str[:100]}...") # Can be verbose

        feedback.pushInfo(self.tr("Fetching OSM street data..."))
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

        feedback.pushInfo(self.tr(f"OSM data fetched: {osm_data_layer_4326.featureCount()} ways."))

        feedback.pushInfo(self.tr("Clipping and reprojecting OSM data..."))
        clipped_osm_data_4326_path = 'memory:clipped_osm_data_4326_algo'
        # Use input_poly_for_bbox for clipping (it's the original input polygon, possibly reprojected to 4326)
        clipped_osm_layer_4326 = cliplayer_v2(osm_data_layer_4326, input_poly_for_bbox, clipped_osm_data_4326_path)

        if not clipped_osm_layer_4326.isValid():
            raise QgsProcessingException(self.tr("Clipping of OSM data failed."))

        feedback.pushInfo(self.tr(f"OSM data clipped: {clipped_osm_layer_4326.featureCount()} ways remain."))

        if clipped_osm_layer_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM ways after clipping. Output will be empty."))
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs if 'local_tm_crs' in locals() else crs_4326)
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        clipped_reproj_layer, local_tm_crs = reproject_layer_localTM(
            clipped_osm_layer_4326,
            outputpath=None,
            layername="clipped_osm_local_tm_algo",
            lgt_0=extent_4326.center().x()
        )
        if not clipped_reproj_layer.isValid():
            raise QgsProcessingException(self.tr("Failed to reproject clipped OSM data."))

        feedback.pushInfo(self.tr(f"Data reprojected to local TM ({local_tm_crs.authid()}): {clipped_reproj_layer.featureCount()} ways."))

        feedback.pushInfo(self.tr("Cleaning street network..."))
        filtered_streets_layer = QgsVectorLayer(
            f"LineString?crs={local_tm_crs.authid()}",
            "filtered_streets_local_tm_algo", "memory")
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        if clipped_reproj_layer.fields().count() > 0:
            filtered_streets_dp.addAttributes(clipped_reproj_layer.fields())
        else:
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = clipped_reproj_layer.fields().lookupField(highway_tag)
        if highway_field_idx == -1:
            raise QgsProcessingException(self.tr(f"'{highway_tag}' not found in reprojected OSM data."))

        for f_in in clipped_reproj_layer.getFeatures():
            if feedback.isCanceled(): return {}
            highway_type_attr = f_in.attribute(highway_field_idx)
            highway_type_str = str(highway_type_attr).lower() if highway_type_attr is not None else ""
            width = default_widths.get(highway_type_str, 0.0)
            if width >= 0.5:
                new_feat = QgsFeature(filtered_streets_layer.fields())
                new_feat.setGeometry(f_in.geometry())
                new_feat.setAttributes(f_in.attributes())
                features_to_add_to_filtered.append(new_feat)

        if features_to_add_to_filtered:
            filtered_streets_dp.addFeatures(features_to_add_to_filtered)
        feedback.pushInfo(self.tr(f"Streets filtered by type/width: {filtered_streets_layer.featureCount()} ways remain."))

        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets after filtering. Output will be empty."))
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs)
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        try:
            feedback.pushInfo(self.tr("Removing unconnected lines..."))
            remove_unconnected_lines_v2(filtered_streets_layer)
            feedback.pushInfo(self.tr(f"After removing unconnected lines: {filtered_streets_layer.featureCount()} ways remain."))
        except Exception as e:
            feedback.pushWarning(self.tr(f"Could not remove unconnected lines: {e}."))

        feedback.pushInfo(self.tr("Polygonizing street network..."))
        protoblocks_layer = polygonize_lines(
            filtered_streets_layer,
            outputlayer='memory:protoblocks_temp_algo',
            keepfields=False)

        if not protoblocks_layer or not protoblocks_layer.isValid():
            raise QgsProcessingException(self.tr("Polygonization failed or returned an invalid layer."))

        # Ensure protoblocks_layer has the correct CRS (local_tm_crs)
        # The polygonize_lines wrapper should handle this, but an explicit set here is safer.
        if not protoblocks_layer.crs().isValid() or protoblocks_layer.crs().authid() != local_tm_crs.authid():
            feedback.pushInfo(f"Warning: Protoblocks layer CRS ({protoblocks_layer.crs().authid()}) differs from expected local TM CRS ({local_tm_crs.authid()}). Forcing correct CRS.")
            protoblocks_layer.setCrs(local_tm_crs)

        feedback.pushInfo(self.tr(f"Polygonization created {protoblocks_layer.featureCount()} protoblocks. Output CRS will be: {protoblocks_layer.crs().description()} ({protoblocks_layer.crs().authid()})"))

        # --- Geometry Inspection Loop ---
        if protoblocks_layer.featureCount() > 0:
            feedback.pushInfo(self.tr("Inspecting first few protoblock geometries..."))
            count = 0
            for feat in protoblocks_layer.getFeatures():
                if count >= 5: # Inspect up to 5 features
                    break

                geom_info = f"  Feature {feat.id()}: "
                if not feat.hasGeometry():
                    geom_info += "Has NO geometry."
                else:
                    geom = feat.geometry()
                    geom_info += f"hasGeometry=True, isNull={geom.isNull()}, isEmpty={geom.isEmpty()}, wkbType={QgsWkbTypes.displayString(geom.wkbType())}"
                    if not geom.isNull() and not geom.isEmpty():
                        try:
                            geom_info += f", area={geom.area()}"
                        except Exception as e_area:
                            geom_info += f", area_calc_error='{e_area}'"
                feedback.pushInfo(geom_info)
                count += 1
        # --- End Geometry Inspection Loop ---

        # Prepare the final output sink
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            protoblocks_layer.fields(),
            QgsWkbTypes.Polygon,
            protoblocks_layer.crs() # Use the CRS from the protoblocks_layer itself
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))

        if protoblocks_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No protoblocks after polygonization (feature count is 0). Output will be an empty layer with correct CRS."))
            # No features to add, but sink is correctly prepared.
        else:
            # Add features to the sink
            total_out_feats = protoblocks_layer.featureCount()
            for i, feat in enumerate(protoblocks_layer.getFeatures()):
                if feedback.isCanceled(): break
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                feedback.setProgress(int(80 + (i + 1) * 20.0 / total_out_feats))

        feedback.pushInfo(self.tr("Protoblock generation complete. Output written."))
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        # Clean up any persistent temporary layers if necessary
        # Memory layers are usually handled by QGIS, but explicit deletion can be added if needed
        # e.g., for layers like 'input_polygon_4326_path' if they were file-based.
        return {}

from qgis import processing
from qgis.core import QgsWkbTypes, QgsProcessingException, QgsCoordinateTransform, QgsRectangle
