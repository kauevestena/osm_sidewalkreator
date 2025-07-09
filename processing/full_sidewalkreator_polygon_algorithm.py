# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterNumber, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsCoordinateReferenceSystem, QgsFields, QgsFeature, QgsWkbTypes,
    QgsProcessingException, QgsField, QgsProcessingMultiStepFeedback,
    QgsVectorLayer, QgsProcessingUtils, QgsRectangle, QgsProject, QgsFeatureRequest # Added QgsFeatureRequest
)
import math

# Assuming parameters.py has the defaults we need
from ..parameters import (
    default_curve_radius, min_d_to_building, d_to_add_to_each_side, minimal_buffer,
    perc_draw_kerbs, perc_tol_crossings, d_to_add_interp_d, CRS_LATLON_4326,
    default_widths, highway_tag # Import necessary for logic
)
# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (reproject_layer_localTM, cliplayer_v2,
                                remove_unconnected_lines_v2, polygonize_lines,
                                create_new_layerfield, edit, # For highway width processing
                                select_feats_by_attr, layer_from_featlist, # For existing sidewalks (future)
                                dissolve_tosinglegeom, generate_buffer, split_lines # For protoblock refinement and splitted_lines
                                )


class FullSidewalkreatorPolygonAlgorithm(QgsProcessingAlgorithm):
    """
    Full SidewalKreator workflow: Generates sidewalks, crossings, and kerbs
    from OSM data within an input polygon area.
    """
    # INPUTS
    INPUT_POLYGON = 'INPUT_POLYGON'
    TIMEOUT = 'TIMEOUT'
    FETCH_BUILDINGS_DATA = 'FETCH_BUILDINGS_DATA'
    FETCH_ADDRESS_DATA = 'FETCH_ADDRESS_DATA'

    DEAD_END_ITERATIONS = 'DEAD_END_ITERATIONS'

    SIDEWALK_CURVE_RADIUS = 'SIDEWALK_CURVE_RADIUS'
    SIDEWALK_ADDED_ROAD_WIDTH_TOTAL = 'SIDEWALK_ADDED_ROAD_WIDTH_TOTAL'
    SIDEWALK_CHECK_BUILDING_OVERLAP = 'SIDEWALK_CHECK_BUILDING_OVERLAP'
    SIDEWALK_MIN_DIST_TO_BUILDING = 'SIDEWALK_MIN_DIST_TO_BUILDING'
    SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING = 'SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING'

    CROSSING_METHOD_PARAM = 'CROSSING_METHOD_PARAM'
    CROSSING_KERB_OFFSET_PERCENT = 'CROSSING_KERB_OFFSET_PERCENT'
    CROSSING_MAX_LENGTH_TOLERANCE_PERCENT = 'CROSSING_MAX_LENGTH_TOLERANCE_PERCENT'
    CROSSING_INWARD_OFFSET = 'CROSSING_INWARD_OFFSET'
    CROSSING_MIN_ROAD_LENGTH = 'CROSSING_MIN_ROAD_LENGTH'
    CROSSING_AUTO_REMOVE_LONG = 'CROSSING_AUTO_REMOVE_LONG'

    SPLITTING_METHOD = 'SPLITTING_METHOD'
    SPLIT_VORONOI_MIN_POIS = 'SPLIT_VORONOI_MIN_POIS'
    SPLIT_MAX_LENGTH_VALUE = 'SPLIT_MAX_LENGTH_VALUE'
    SPLIT_SEGMENT_NUMBER_VALUE = 'SPLIT_SEGMENT_NUMBER_VALUE'

    # OUTPUTS
    OUTPUT_SIDEWALKS = 'OUTPUT_SIDEWALKS'
    OUTPUT_CROSSINGS = 'OUTPUT_CROSSINGS'
    OUTPUT_KERBS = 'OUTPUT_KERBS'
    OUTPUT_PROTOBLOCKS_DEBUG = 'OUTPUT_PROTOBLOCKS_DEBUG'

    # Enum options
    CROSSING_METHOD_OPTIONS_ENUM = [
        'Parallel to Transversal Segment',
        'Perpendicular to Road Segment'
    ]
    SPLITTING_METHOD_OPTIONS_ENUM = [
        'None (only protoblock corners)',
        'Voronoi Polygons',
        'By Maximum Length',
        'By Fixed Number of Segments'
    ]

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return FullSidewalkreatorPolygonAlgorithm()

    def name(self):
        return 'fullsidewalkreatorfrompolygon'

    def displayName(self):
        return self.tr('Generate Full Sidewalk Network (from Polygon)')

    def shortHelpString(self):
        return self.tr("Performs the full SidewalKreator workflow (sidewalks, crossings, kerbs) "
                       "for an area defined by an input polygon layer. Uses default highway widths. "
                       "Final outputs (Sidewalks, Crossings, Kerbs) are in EPSG:4326.")

    def initAlgorithm(self, config=None):
        # === Basic Inputs ===
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGON,
                self.tr('Input Area Polygon Layer (EPSG:4326 recommended)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT, self.tr('OSM Download Timeout (seconds)'),
                QgsProcessingParameterNumber.Integer, defaultValue=60, minValue=10, maxValue=300
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FETCH_BUILDINGS_DATA, self.tr('Fetch OSM Buildings Data (for overlap checks & POI splitting)'),
                defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FETCH_ADDRESS_DATA, self.tr('Fetch OSM Address Data (addr:housenumber, for POI splitting)'),
                defaultValue=True
            )
        )

        # === Protoblock/Street Cleaning Stage ===
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEAD_END_ITERATIONS, self.tr('Iterations to Remove Dead-End Streets (for protoblocks)'),
                QgsProcessingParameterNumber.Integer, defaultValue=1, minValue=0, maxValue=10
            )
        )

        # === Sidewalk Generation Stage ===
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIDEWALK_CURVE_RADIUS, self.tr('Sidewalk Corner Curve Radius (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=default_curve_radius, minValue=0.0, maxValue=20.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIDEWALK_ADDED_ROAD_WIDTH_TOTAL, self.tr('Total Added Width to Road for Sidewalk Axis (meters, for both sides)'),
                QgsProcessingParameterNumber.Double, defaultValue=d_to_add_to_each_side * 2, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SIDEWALK_CHECK_BUILDING_OVERLAP, self.tr('Adjust Sidewalk Width if Overlaps Buildings (slower if buildings are fetched)'),
                defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIDEWALK_MIN_DIST_TO_BUILDING, self.tr('Min. Distance Sidewalk to Buildings (m, if overlap checked)'),
                QgsProcessingParameterNumber.Double, defaultValue=min_d_to_building, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING, self.tr('Min. Sidewalk Width Near Buildings (m, if overlap checked)'),
                QgsProcessingParameterNumber.Double, defaultValue=minimal_buffer * 2, minValue=0.1, maxValue=10.0
            )
        )

        # === Crossing Generation Stage ===
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CROSSING_METHOD_PARAM, self.tr('Crossing Generation Method'),
                options=self.CROSSING_METHOD_OPTIONS_ENUM, defaultValue=0, # Parallel
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_KERB_OFFSET_PERCENT, self.tr('Crossing: Kerb Position (% of half-crossing from center)'),
                QgsProcessingParameterNumber.Integer, defaultValue=int(perc_draw_kerbs), minValue=0, maxValue=100
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_MAX_LENGTH_TOLERANCE_PERCENT, self.tr('Crossing: Max Length Tolerance (%) beyond orthogonal'),
                QgsProcessingParameterNumber.Integer, defaultValue=int(perc_tol_crossings), minValue=0, maxValue=100
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_INWARD_OFFSET, self.tr('Crossing: Inward Interpolation from Intersection (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=d_to_add_interp_d, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_MIN_ROAD_LENGTH, self.tr('Crossing: Min. Road Segment Length to Generate Crossing (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=20.0, minValue=0.0
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CROSSING_AUTO_REMOVE_LONG, self.tr('Crossing: Auto-Remove if Longer than Tolerance'),
                defaultValue=False
            )
        )

        # === Sidewalk Splitting Stage ===
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SPLITTING_METHOD, self.tr('Sidewalk Splitting Method (after protoblock corners)'),
                options=self.SPLITTING_METHOD_OPTIONS_ENUM, defaultValue=0, # None
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_VORONOI_MIN_POIS, self.tr('Splitting (Voronoi): Min. POIs per Cell (if method is Voronoi)'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_MAX_LENGTH_VALUE, self.tr('Splitting (Max Length): Value (m, if method is MaxLength)'),
                QgsProcessingParameterNumber.Double, defaultValue=50.0, minValue=1.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_SEGMENT_NUMBER_VALUE, self.tr('Splitting (By Number): Number of Segments (if method is ByNumber)'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1
            )
        )

        # === Outputs ===
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_SIDEWALKS, self.tr('Output Sidewalks'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_CROSSINGS, self.tr('Output Crossings'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_KERBS, self.tr('Output Kerbs'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS_DEBUG,
                self.tr('Output Protoblocks (Debug - in local TM CRS)'),
                type=QgsProcessing.TypeVectorPolygon,
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Algorithm Started."))

        # --- Parameter Retrieval ---
        input_polygon_fs = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        # fetch_buildings = self.parameterAsBoolean(parameters, self.FETCH_BUILDINGS_DATA, context) # TODO: Integrate
        # fetch_addresses = self.parameterAsBoolean(parameters, self.FETCH_ADDRESS_DATA, context) # TODO: Integrate
        dead_end_iterations = self.parameterAsInt(parameters, self.DEAD_END_ITERATIONS, context)

        # Retrieve other parameters as they are needed...

        # --- Stage 1: Data Fetching and Protoblock Generation (adapted from ProtoblockAlgorithm) ---
        feedback.pushInfo(self.tr("Stage 1: Initial Data Fetch and Processing for Protoblocks..."))
        if input_polygon_fs is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_POLYGON))

        actual_input_layer = input_polygon_fs.materialize(QgsFeatureRequest())
        if not actual_input_layer or not actual_input_layer.isValid() or actual_input_layer.featureCount() == 0:
            raise QgsProcessingException(self.tr("Materialized input polygon layer is invalid or empty."))
        feedback.pushInfo(self.tr(f"Using input polygon: {actual_input_layer.name()} ({actual_input_layer.featureCount()} features)"))

        source_crs = actual_input_layer.sourceCrs()
        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        input_poly_for_bbox = actual_input_layer

        feedback.pushInfo(self.tr(f"Input polygon CRS for BBOX: {source_crs.description()} (Auth ID: {source_crs.authid()})")) # This was the last line logged

        source_auth_id = "UNKNOWN_SOURCE_AUTH_ID"
        target_auth_id = "UNKNOWN_TARGET_AUTH_ID"
        is_different_crs = None

        try:
            feedback.pushInfo("Attempting to get source_crs.authid()...")
            source_auth_id = source_crs.authid()
            feedback.pushInfo(f"source_crs.authid() retrieved: {source_auth_id}")

            feedback.pushInfo("Attempting to get crs_4326.authid()...")
            target_auth_id = crs_4326.authid()
            feedback.pushInfo(f"crs_4326.authid() retrieved: {target_auth_id}")

            feedback.pushInfo("Attempting comparison source_auth_id != target_auth_id...")
            is_different_crs = (source_auth_id != target_auth_id)
            feedback.pushInfo(f"Comparison result (is_different_crs): {is_different_crs}")

        except Exception as e_crs_check:
            feedback.pushInfo(f"EXCEPTION during CRS authid check/comparison: {e_crs_check}")
            # Depending on the exception, we might want to raise or handle differently
            # For now, let it proceed to the if/else based on potentially incomplete info, or raise
            raise QgsProcessingException(self.tr(f"Critical error during CRS authid check: {e_crs_check}"))

        feedback.pushInfo(self.tr("DEBUG: Right before 'if is_different_crs:' check."))

        if is_different_crs:
            feedback.pushInfo(self.tr("DEBUG: Inside 'if is_different_crs:' block (should not happen for EPSG:4326 input)."))
            feedback.pushInfo(self.tr(f"CRS is different. Attempting to reproject input polygon from {source_auth_id} to EPSG:4326 for BBOX calculation..."))
            reproject_params_bbox = { 'INPUT': actual_input_layer, 'TARGET_CRS': crs_4326, 'OUTPUT': 'memory:input_reprojected_for_bbox'}
            sub_feedback_bbox = QgsProcessingMultiStepFeedback(1, feedback)
            sub_feedback_bbox.setCurrentStep(0)

            reproject_result_bbox = processing.run("native:reprojectlayer", reproject_params_bbox, context=context, feedback=sub_feedback_bbox, is_child_algorithm=True)
            feedback.pushInfo(self.tr(f"Input polygon reprojection attempt finished. Result: {reproject_result_bbox}"))

            if sub_feedback_bbox.isCanceled(): return {}

            output_value_bbox = reproject_result_bbox.get('OUTPUT')
            if not output_value_bbox:
                raise QgsProcessingException(self.tr("Input polygon reprojection failed to produce an output value."))

            input_poly_for_bbox = QgsProcessingUtils.mapLayerFromString(output_value_bbox, context)
            if not input_poly_for_bbox or not input_poly_for_bbox.isValid() or input_poly_for_bbox.featureCount() == 0:
                raise QgsProcessingException(self.tr("Failed to reproject input for BBOX, result is invalid or empty."))
            feedback.pushInfo(self.tr(f"Input polygon successfully reprojected to EPSG:4326. New layer: {input_poly_for_bbox.name()}"))
        else:
            feedback.pushInfo(self.tr("DEBUG: Inside 'else' block (CRS is already EPSG:4326)."))
            feedback.pushInfo(self.tr("Input layer is already in EPSG:4326."))
            # input_poly_for_bbox is already actual_input_layer, set before the if/else

        feedback.pushInfo(self.tr("DEBUG: After if/else for CRS check."))

        feedback.pushInfo(self.tr(f"DEBUG: About to call .extent() on input_poly_for_bbox. Name: {input_poly_for_bbox.name()}, isValid: {input_poly_for_bbox.isValid()}, featureCount: {input_poly_for_bbox.featureCount()}, CRS: {input_poly_for_bbox.crs().authid()}"))
        try:
            extent_4326 = input_poly_for_bbox.extent()
            feedback.pushInfo(self.tr(f"DEBUG: .extent() call completed. Extent: {extent_4326.toString()}")) # This was the last line seen in the previous successful log
        except Exception as e_extent:
            feedback.pushInfo(self.tr(f"EXCEPTION during .extent() call: {e_extent}"))
            raise QgsProcessingException(self.tr(f"Error getting extent from input polygon layer: {e_extent}"))

        # Granular logging for extent checks - THIS IS THE SECTION TO RE-APPLY CAREFULLY
        feedback.pushInfo(self.tr("DEBUG: Detailed extent checks starting..."))

        is_null_check = "N/A"
        try:
            feedback.pushInfo(self.tr("DEBUG: Checking extent_4326.isNull()..."))
            is_null_check = extent_4326.isNull()
            feedback.pushInfo(self.tr(f"DEBUG: extent_4326.isNull() is {is_null_check}"))
        except Exception as e_isNull:
            feedback.pushInfo(self.tr(f"EXCEPTION during extent_4326.isNull(): {e_isNull}"))
            raise QgsProcessingException(self.tr(f"Error checking if extent is null: {e_isNull}"))

        coords_for_finite_check = []
        xmin_val, ymin_val, xmax_val, ymax_val = None, None, None, None

        try:
            feedback.pushInfo(self.tr("DEBUG: Getting extent_4326.xMinimum()..."))
            xmin_val = extent_4326.xMinimum()
            coords_for_finite_check.append(xmin_val)
            feedback.pushInfo(self.tr(f"DEBUG: xMinimum is {xmin_val}"))
        except Exception as e_xmin:
            feedback.pushInfo(self.tr(f"EXCEPTION during extent_4326.xMinimum(): {e_xmin}"))
            # Continue to try and get other coords for logging, but this is likely the hang point if it errors

        try:
            feedback.pushInfo(self.tr("DEBUG: Getting extent_4326.yMinimum()..."))
            ymin_val = extent_4326.yMinimum()
            coords_for_finite_check.append(ymin_val)
            feedback.pushInfo(self.tr(f"DEBUG: yMinimum is {ymin_val}"))
        except Exception as e_ymin:
            feedback.pushInfo(self.tr(f"EXCEPTION during extent_4326.yMinimum(): {e_ymin}"))

        try:
            feedback.pushInfo(self.tr("DEBUG: Getting extent_4326.xMaximum()..."))
            xmax_val = extent_4326.xMaximum()
            coords_for_finite_check.append(xmax_val)
            feedback.pushInfo(self.tr(f"DEBUG: xMaximum is {xmax_val}"))
        except Exception as e_xmax:
            feedback.pushInfo(self.tr(f"EXCEPTION during extent_4326.xMaximum(): {e_xmax}"))

        try:
            feedback.pushInfo(self.tr("DEBUG: Getting extent_4326.yMaximum()..."))
            ymax_val = extent_4326.yMaximum()
            coords_for_finite_check.append(ymax_val)
            feedback.pushInfo(self.tr(f"DEBUG: yMaximum is {ymax_val}"))
        except Exception as e_ymax:
            feedback.pushInfo(self.tr(f"EXCEPTION during extent_4326.yMaximum(): {e_ymax}"))

        # Check if all coordinates were successfully retrieved before mapping
        if not all(c is not None for c in [xmin_val, ymin_val, xmax_val, ymax_val]):
             # If any coordinate is None here, it means an exception occurred above but we didn't re-raise immediately.
             # This check ensures we don't proceed with None values to math.isfinite.
             raise QgsProcessingException(self.tr(f"One or more extent coordinates could not be retrieved. Check previous EXCEPTION logs. Extent string: {extent_4326.toString()}"))

        feedback.pushInfo(self.tr("DEBUG: Checking finiteness of all retrieved coordinates..."))
        are_all_finite_check = all(map(math.isfinite, coords_for_finite_check))
        feedback.pushInfo(self.tr(f"DEBUG: Coordinates are all finite: {are_all_finite_check}"))

        if is_null_check or not are_all_finite_check:
            raise QgsProcessingException(self.tr(f"Invalid BBOX from input: {extent_4326.toString()}. isNull: {is_null_check}, allFinite: {are_all_finite_check}. Ensure input layer '{input_poly_for_bbox.name()}' has valid geometries."))

        min_lgt, min_lat = xmin_val, ymin_val
        max_lgt, max_lat = xmax_val, ymax_val
        feedback.pushInfo(f"Calculated BBOX (EPSG:4326) for query: MinLon={min_lgt}, MinLat={min_lat}, MaxLon={max_lgt}, MaxLat={max_lat}")

        query_str_roads = osm_query_string_by_bbox(min_lat, min_lgt, max_lat, max_lgt, interest_key=highway_tag, way=True)
        osm_roads_geojson_str = get_osm_data(query_str_roads, "osm_roads_full_algo", "LineString", timeout, True)
        if osm_roads_geojson_str is None: raise QgsProcessingException(self.tr("Failed to fetch OSM road data."))
        osm_roads_layer_4326 = QgsVectorLayer(osm_roads_geojson_str, "osm_roads_dl_4326_full", "ogr")
        if not osm_roads_layer_4326.isValid(): raise QgsProcessingException(self.tr("Fetched OSM road data is not a valid layer."))
        feedback.pushInfo(self.tr(f"Fetched {osm_roads_layer_4326.featureCount()} OSM ways."))

        # Clip roads to the precise input polygon (input_poly_for_bbox is already in 4326)
        clipped_osm_roads_4326 = cliplayer_v2(osm_roads_layer_4326, input_poly_for_bbox, 'memory:clipped_roads_4326_full')
        if not clipped_osm_roads_4326.isValid(): raise QgsProcessingException(self.tr("Clipping OSM roads failed."))
        if clipped_osm_roads_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM roads found within the input polygon after clipping."))
            # Prepare empty outputs for everything and return
            # (This part needs to be robustly handled for all output sinks)
            (s, d_s) = self.parameterAsSink(parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
            (c, d_c) = self.parameterAsSink(parameters, self.OUTPUT_CROSSINGS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
            (k, d_k) = self.parameterAsSink(parameters, self.OUTPUT_KERBS, context, QgsFields(), QgsWkbTypes.Point, crs_4326)
            results = {self.OUTPUT_SIDEWALKS: d_s, self.OUTPUT_CROSSINGS: d_c, self.OUTPUT_KERBS: d_k}
            debug_protoblocks_output_spec_val = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)
            if debug_protoblocks_output_spec_val:
                (p, d_p) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, QgsFields(), QgsWkbTypes.Polygon, crs_4326) # Placeholder CRS
                results[self.OUTPUT_PROTOBLOCKS_DEBUG] = d_p
            return results


        # Reproject clipped roads to local TM
        roads_local_tm, local_tm_crs = reproject_layer_localTM(clipped_osm_roads_4326, None, "roads_local_tm_full", extent_4326.center().x())
        if not roads_local_tm.isValid(): raise QgsProcessingException(self.tr("Reprojecting OSM roads to local TM failed."))

        # Clean street network
        filtered_streets_layer = QgsVectorLayer(f"LineString?crs={local_tm_crs.authid()}", "filtered_streets_full", "memory")
        # ... (copy fields from roads_local_tm) ...
        # ... (filter by highway_tag and default_widths into filtered_streets_layer) ...
        # This logic needs to be carefully copied and adapted:
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        if roads_local_tm.fields().count() > 0:
            filtered_streets_dp.addAttributes(roads_local_tm.fields())
        else:
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = roads_local_tm.fields().lookupField(highway_tag)
        if highway_field_idx == -1: raise QgsProcessingException(self.tr(f"'{highway_tag}' not found in reprojected OSM data."))
        for f_in in roads_local_tm.getFeatures():
            if feedback.isCanceled(): return {}
            highway_type_attr = f_in.attribute(highway_field_idx)
            highway_type_str = str(highway_type_attr).lower() if highway_type_attr is not None else ""
            width = default_widths.get(highway_type_str, 0.0)
            if width >= 0.5:
                new_feat = QgsFeature(filtered_streets_layer.fields())
                new_feat.setGeometry(f_in.geometry())
                new_feat.setAttributes(f_in.attributes())
                features_to_add_to_filtered.append(new_feat)
        if features_to_add_to_filtered: filtered_streets_dp.addFeatures(features_to_add_to_filtered)
        feedback.pushInfo(self.tr(f"Streets filtered by type/width: {filtered_streets_layer.featureCount()} ways remain."))

        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets after filtering. Output will be empty."))
            # Prepare empty outputs and return (similar to above)
            (s, d_s) = self.parameterAsSink(parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
            (c, d_c) = self.parameterAsSink(parameters, self.OUTPUT_CROSSINGS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
            (k, d_k) = self.parameterAsSink(parameters, self.OUTPUT_KERBS, context, QgsFields(), QgsWkbTypes.Point, crs_4326)
            results = {self.OUTPUT_SIDEWALKS: d_s, self.OUTPUT_CROSSINGS: d_c, self.OUTPUT_KERBS: d_k}
            debug_protoblocks_output_spec_val = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)
            if debug_protoblocks_output_spec_val:
                (p, d_p) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, QgsFields(), QgsWkbTypes.Polygon, local_tm_crs) # Use local_tm_crs for debug
                results[self.OUTPUT_PROTOBLOCKS_DEBUG] = d_p
            return results


        # remove_unconnected_lines_v2 (using DEAD_END_ITERATIONS)
        # Note: remove_unconnected_lines_v2 doesn't currently take iterations.
        # The main plugin calls it multiple times if dead_end_iters_box.value() > 0.
        # For now, call once. To implement iterations, this part needs a loop.
        feedback.pushInfo(self.tr(f"Removing unconnected lines (iterations: {dead_end_iterations})...")) # Log the param
        for _ in range(dead_end_iterations): # Basic iteration, could be more complex if needed
            if feedback.isCanceled(): return {}
            remove_unconnected_lines_v2(filtered_streets_layer)
        feedback.pushInfo(self.tr(f"After removing unconnected lines: {filtered_streets_layer.featureCount()} ways remain."))


        # Polygonize to get initial protoblocks
        initial_protoblocks_layer = polygonize_lines(filtered_streets_layer, 'memory:initial_protoblocks_full', False)
        if not initial_protoblocks_layer or not initial_protoblocks_layer.isValid():
            raise QgsProcessingException(self.tr("Initial polygonization failed."))

        # Re-clone to ensure CRS
        clean_protoblocks_layer_local_tm = QgsVectorLayer("Polygon", "clean_protoblocks_full", "memory")
        clean_protoblocks_layer_local_tm.setCrs(local_tm_crs)
        if initial_protoblocks_layer.featureCount() > 0:
            feats_to_clone = [QgsFeature(f) for f in initial_protoblocks_layer.getFeatures()]
            clean_protoblocks_layer_local_tm.dataProvider().addFeatures(feats_to_clone)
        feedback.pushInfo(self.tr(f"Protoblocks generated (local TM): {clean_protoblocks_layer_local_tm.featureCount()} features."))

        # --- Output Debug Protoblocks (if requested) ---
        protoblocks_debug_dest_id = None
        debug_protoblocks_output_spec = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)
        if debug_protoblocks_output_spec:
            (protoblocks_debug_sink, protoblocks_debug_dest_id) = self.parameterAsSink(
                parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context,
                clean_protoblocks_layer_local_tm.fields(), QgsWkbTypes.Polygon, local_tm_crs)
            if protoblocks_debug_sink:
                for feat in clean_protoblocks_layer_local_tm.getFeatures():
                    protoblocks_debug_sink.addFeature(feat, QgsFeatureSink.FastInsert)
            else:
                protoblocks_debug_dest_id = None # Failed to create sink

        # --- Placeholder for other outputs ---
        (sidewalks_sink, sidewalks_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
        (crossings_sink, crossings_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_CROSSINGS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
        (kerbs_sink, kerbs_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_KERBS, context, QgsFields(), QgsWkbTypes.Point, crs_4326)

        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Stage 1 (Protoblocks) Finished. Other outputs are placeholders."))
        results = {
            self.OUTPUT_SIDEWALKS: sidewalks_dest_id,
            self.OUTPUT_CROSSINGS: crossings_dest_id,
            self.OUTPUT_KERBS: kerbs_dest_id
        }
        if protoblocks_debug_dest_id:
            results[self.OUTPUT_PROTOBLOCKS_DEBUG] = protoblocks_debug_dest_id
        return results

    def postProcessAlgorithm(self, context, feedback):
        return {}
