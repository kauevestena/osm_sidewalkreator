# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterNumber, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsCoordinateReferenceSystem, QgsFields, QgsFeature, QgsWkbTypes, QgsFeatureSink,
    QgsProcessingException, QgsField, QgsProcessingMultiStepFeedback,
    QgsVectorLayer, QgsProcessingUtils, QgsRectangle, QgsProject, QgsFeatureRequest
)
import math

from ..parameters import (
    default_curve_radius, min_d_to_building, d_to_add_to_each_side, minimal_buffer,
    perc_draw_kerbs, perc_tol_crossings, d_to_add_interp_d, CRS_LATLON_4326,
    default_widths, highway_tag, widths_fieldname
)
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (reproject_layer_localTM, cliplayer_v2,
                                remove_unconnected_lines_v2, polygonize_lines,
                                create_new_layerfield, edit,
                                select_feats_by_attr, layer_from_featlist,
                                dissolve_tosinglegeom, generate_buffer, split_lines,
                                check_empty_layer
                                )
from .sidewalk_generation_logic import generate_sidewalk_geometries_and_zones


class FullSidewalkreatorPolygonAlgorithm(QgsProcessingAlgorithm):
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
    OUTPUT_SIDEWALKS = 'OUTPUT_SIDEWALKS'
    OUTPUT_CROSSINGS = 'OUTPUT_CROSSINGS'
    OUTPUT_KERBS = 'OUTPUT_KERBS'
    OUTPUT_PROTOBLOCKS_DEBUG = 'OUTPUT_PROTOBLOCKS_DEBUG'
    CROSSING_METHOD_OPTIONS_ENUM = ['Parallel to Transversal Segment', 'Perpendicular to Road Segment']
    SPLITTING_METHOD_OPTIONS_ENUM = ['None (only protoblock corners)', 'Voronoi Polygons', 'By Maximum Length', 'By Fixed Number of Segments']

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return FullSidewalkreatorPolygonAlgorithm()

    def name(self):
        return 'fullsidewalkreatorfrompolygon'

    def displayName(self):
        return self.tr('Generate Full Sidewalk Network (from Polygon)')

    def shortHelpString(self):
        return self.tr("Fetches OSM road and building data for an input polygon area. This algorithm focuses on generating sidewalk lines and related features (like exclusion zones for debugging) using configurable parameters. Main sidewalk output is in EPSG:4326. (Full plugin includes crossings and kerbs).")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_POLYGON, self.tr('Input Area Polygon Layer (EPSG:4326 recommended)'), [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber(self.TIMEOUT, self.tr('OSM Download Timeout (seconds)'), QgsProcessingParameterNumber.Integer, defaultValue=60, minValue=10, maxValue=300))
        self.addParameter(QgsProcessingParameterBoolean(self.FETCH_BUILDINGS_DATA, self.tr('Fetch OSM Buildings Data (for overlap checks & POI splitting)'), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(self.FETCH_ADDRESS_DATA, self.tr('Fetch OSM Address Data (addr:housenumber, for POI splitting)'), defaultValue=True))
        self.addParameter(QgsProcessingParameterNumber(self.DEAD_END_ITERATIONS, self.tr('Iterations to Remove Dead-End Streets (for protoblocks)'), QgsProcessingParameterNumber.Integer, defaultValue=1, minValue=0, maxValue=10))
        self.addParameter(QgsProcessingParameterNumber(self.SIDEWALK_CURVE_RADIUS, self.tr('Sidewalk Corner Curve Radius (meters)'), QgsProcessingParameterNumber.Double, defaultValue=default_curve_radius, minValue=0.0, maxValue=20.0))
        self.addParameter(QgsProcessingParameterNumber(self.SIDEWALK_ADDED_ROAD_WIDTH_TOTAL, self.tr('Total Added Width to Road for Sidewalk Axis (meters, for both sides)'), QgsProcessingParameterNumber.Double, defaultValue=d_to_add_to_each_side * 2, minValue=0.0, maxValue=10.0))
        self.addParameter(QgsProcessingParameterBoolean(self.SIDEWALK_CHECK_BUILDING_OVERLAP, self.tr('Adjust Sidewalk Width if Overlaps Buildings (slower if buildings are fetched)'), defaultValue=True))
        self.addParameter(QgsProcessingParameterNumber(self.SIDEWALK_MIN_DIST_TO_BUILDING, self.tr('Min. Distance Sidewalk to Buildings (m, if overlap checked)'), QgsProcessingParameterNumber.Double, defaultValue=min_d_to_building, minValue=0.0, maxValue=10.0))
        self.addParameter(QgsProcessingParameterNumber(self.SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING, self.tr('Min. Sidewalk Width Near Buildings (m, if overlap checked)'), QgsProcessingParameterNumber.Double, defaultValue=minimal_buffer * 2, minValue=0.1, maxValue=10.0))
        self.addParameter(QgsProcessingParameterEnum(self.CROSSING_METHOD_PARAM, self.tr('Crossing Generation Method'), options=self.CROSSING_METHOD_OPTIONS_ENUM, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.CROSSING_KERB_OFFSET_PERCENT, self.tr('Crossing: Kerb Position (%)'), QgsProcessingParameterNumber.Integer, defaultValue=int(perc_draw_kerbs), minValue=0, maxValue=100))
        self.addParameter(QgsProcessingParameterNumber(self.CROSSING_MAX_LENGTH_TOLERANCE_PERCENT, self.tr('Crossing: Max Length Tolerance (%)'), QgsProcessingParameterNumber.Integer, defaultValue=int(perc_tol_crossings), minValue=0, maxValue=100))
        self.addParameter(QgsProcessingParameterNumber(self.CROSSING_INWARD_OFFSET, self.tr('Crossing: Inward Offset (m)'), QgsProcessingParameterNumber.Double, defaultValue=d_to_add_interp_d, minValue=0.0, maxValue=10.0))
        self.addParameter(QgsProcessingParameterNumber(self.CROSSING_MIN_ROAD_LENGTH, self.tr('Crossing: Min Road Length (m)'), QgsProcessingParameterNumber.Double, defaultValue=20.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterBoolean(self.CROSSING_AUTO_REMOVE_LONG, self.tr('Crossing: Auto-Remove Long'), defaultValue=False))
        self.addParameter(QgsProcessingParameterEnum(self.SPLITTING_METHOD, self.tr('Sidewalk Splitting Method'), options=self.SPLITTING_METHOD_OPTIONS_ENUM, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.SPLIT_VORONOI_MIN_POIS, self.tr('Splitting (Voronoi): Min POIs'), QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1))
        self.addParameter(QgsProcessingParameterNumber(self.SPLIT_MAX_LENGTH_VALUE, self.tr('Splitting (Max Length): Value (m)'), QgsProcessingParameterNumber.Double, defaultValue=50.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(self.SPLIT_SEGMENT_NUMBER_VALUE, self.tr('Splitting (By Number): Segments'), QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_SIDEWALKS, self.tr('Output Sidewalks (EPSG:4326)')))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_CROSSINGS, self.tr('Output Crossings (EPSG:4326)')))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_KERBS, self.tr('Output Kerbs (EPSG:4326)')))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_PROTOBLOCKS_DEBUG, self.tr('Output Protoblocks (Debug - local TM CRS)'), type=QgsProcessing.TypeVectorPolygon, optional=True ))

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Algorithm Started."))

        # --- Parameter Retrieval ---
        input_polygon_fs = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        fetch_buildings_param = self.parameterAsBoolean(parameters, self.FETCH_BUILDINGS_DATA, context)
        # fetch_addresses_param = self.parameterAsBoolean(parameters, self.FETCH_ADDRESS_DATA, context) # TODO
        dead_end_iterations = self.parameterAsInt(parameters, self.DEAD_END_ITERATIONS, context)

        sw_curve_radius = self.parameterAsDouble(parameters, self.SIDEWALK_CURVE_RADIUS, context)
        sw_added_width_total = self.parameterAsDouble(parameters, self.SIDEWALK_ADDED_ROAD_WIDTH_TOTAL, context)
        sw_check_overlap = self.parameterAsBoolean(parameters, self.SIDEWALK_CHECK_BUILDING_OVERLAP, context)
        sw_min_dist_building = self.parameterAsDouble(parameters, self.SIDEWALK_MIN_DIST_TO_BUILDING, context)
        sw_min_width_near_building = self.parameterAsDouble(parameters, self.SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING, context)

        # --- Stage 1: Data Fetching and Protoblock Generation ---
        feedback.pushInfo(self.tr("Stage 1: Initial Data Fetch and Processing..."))
        if input_polygon_fs is None: raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_POLYGON))

        actual_input_layer = input_polygon_fs.materialize(QgsFeatureRequest())
        if not actual_input_layer or not actual_input_layer.isValid() or actual_input_layer.featureCount() == 0:
            raise QgsProcessingException(self.tr("Materialized input polygon layer is invalid or empty."))
        feedback.pushInfo(self.tr(f"Using input polygon: {actual_input_layer.name()} ({actual_input_layer.featureCount()} features)"))

        source_crs = actual_input_layer.sourceCrs()
        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        input_poly_for_bbox = actual_input_layer

        # Granular CRS check logging (can be removed later)
        # feedback.pushInfo(self.tr(f"Input polygon CRS for BBOX: {source_crs.description()} (Auth ID: {source_crs.authid()})"))
        # source_auth_id = source_crs.authid()
        # target_auth_id = crs_4326.authid()
        # is_different_crs = (source_auth_id != target_auth_id)
        # feedback.pushInfo(f"Comparison result (is_different_crs for BBOX reprojection): {is_different_crs}")

        if source_crs.authid() != crs_4326.authid():
            feedback.pushInfo(self.tr(f"Reprojecting input layer from {source_crs.authid()} to EPSG:4326 for BBOX calculation."))
            reproject_params_bbox = { 'INPUT': actual_input_layer, 'TARGET_CRS': crs_4326, 'OUTPUT': 'memory:input_reprojected_for_bbox'}
            res_bbox_reproj = processing.run("native:reprojectlayer", reproject_params_bbox, context=context, feedback=feedback, is_child_algorithm=True)
            if feedback.isCanceled(): return {}
            output_value_bbox = res_bbox_reproj.get('OUTPUT')
            if not output_value_bbox: raise QgsProcessingException(self.tr("Input polygon reprojection failed to produce an output value."))
            input_poly_for_bbox = QgsProcessingUtils.mapLayerFromString(output_value_bbox, context)
            if not input_poly_for_bbox or not input_poly_for_bbox.isValid() or input_poly_for_bbox.featureCount() == 0:
                raise QgsProcessingException(self.tr("Failed to reproject input for BBOX or result is empty."))
        # else: feedback.pushInfo(self.tr("Input layer is already in EPSG:4326 for BBOX."))

        extent_4326 = input_poly_for_bbox.extent()
        if extent_4326.isNull() or not all(map(math.isfinite, [extent_4326.xMinimum(), extent_4326.yMinimum(), extent_4326.xMaximum(), extent_4326.yMaximum()])):
            raise QgsProcessingException(self.tr(f"Invalid BBOX from input: {extent_4326.toString()}. Ensure input layer '{input_poly_for_bbox.name()}' has valid geometries."))
        min_lgt, min_lat, max_lgt, max_lat = extent_4326.xMinimum(), extent_4326.yMinimum(), extent_4326.xMaximum(), extent_4326.yMaximum()
        # feedback.pushInfo(f"Query BBOX (EPSG:4326): {min_lgt}, {min_lat}, {max_lgt}, {max_lat}")

        # Fetch Roads
        query_str_roads = osm_query_string_by_bbox(min_lat, min_lgt, max_lat, max_lgt, interest_key=highway_tag, way=True)
        osm_roads_geojson_str = get_osm_data(querystring=query_str_roads,tempfilesname="osm_roads_full_algo",geomtype="LineString",timeout=timeout,return_as_string=True)
        if osm_roads_geojson_str is None: raise QgsProcessingException(self.tr("Failed to fetch OSM road data."))
        osm_roads_layer_4326 = QgsVectorLayer(osm_roads_geojson_str, "osm_roads_dl_4326_full", "ogr")
        if not osm_roads_layer_4326.isValid(): raise QgsProcessingException(self.tr("Fetched OSM road data is not a valid layer."))
        feedback.pushInfo(self.tr(f"Fetched {osm_roads_layer_4326.featureCount()} OSM ways."))

        # Fetch Buildings (if requested)
        osm_buildings_layer_4326 = None
        if fetch_buildings_param:
            feedback.pushInfo(self.tr("Fetching OSM building data..."))
            query_buildings = osm_query_string_by_bbox(min_lat, min_lgt, max_lat, max_lgt, interest_key="building", way=True, relation=True)
            osm_bldgs_geojson_str = get_osm_data(querystring=query_buildings,tempfilesname="osm_bldgs_full_algo",geomtype="Polygon",timeout=timeout,return_as_string=True)
            if osm_bldgs_geojson_str:
                osm_buildings_layer_4326 = QgsVectorLayer(osm_bldgs_geojson_str, "osm_bldgs_dl_4326_full", "ogr")
                if osm_buildings_layer_4326.isValid() and osm_buildings_layer_4326.featureCount() > 0:
                    feedback.pushInfo(self.tr(f"Fetched {osm_buildings_layer_4326.featureCount()} OSM buildings."))
                else:
                    feedback.pushInfo(self.tr("No valid building data fetched or layer is empty."))
                    osm_buildings_layer_4326 = None
            else:
                feedback.pushInfo(self.tr("Failed to fetch building data string."))
                osm_buildings_layer_4326 = None

        # Clip roads
        clipped_osm_roads_4326 = cliplayer_v2(osm_roads_layer_4326, input_poly_for_bbox, 'memory:clipped_roads_4326_full')
        if not clipped_osm_roads_4326.isValid() or clipped_osm_roads_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM roads after clipping. Output will be empty."))
            return self.handle_empty_results(parameters, context, crs_4326)

        # Reproject clipped roads to local TM
        roads_local_tm, local_tm_crs = reproject_layer_localTM(clipped_osm_roads_4326, None, "roads_local_tm_full", extent_4326.center().x())
        if not roads_local_tm.isValid(): raise QgsProcessingException(self.tr("Reprojecting OSM roads to local TM failed."))

        # Reproject buildings if fetched
        reproj_buildings_layer = None
        if osm_buildings_layer_4326 and osm_buildings_layer_4326.featureCount() > 0 :
            feedback.pushInfo(self.tr("Clipping and Reprojecting building data to local TM..."))
            clipped_buildings_4326 = cliplayer_v2(osm_buildings_layer_4326, input_poly_for_bbox, 'memory:clipped_bldgs_4326_full')
            if clipped_buildings_4326 and clipped_buildings_4326.isValid() and clipped_buildings_4326.featureCount() > 0:
                # Use the same lgt_0 for consistency; reproject_layer_localTM returns the new CRS it generated.
                temp_reproj_bldgs, bldg_tm_crs_obj = reproject_layer_localTM(
                    clipped_buildings_4326, None, "bldgs_local_tm_full_temp", extent_4326.center().x()
                )
                if not temp_reproj_bldgs or not temp_reproj_bldgs.isValid():
                    feedback.pushWarning(self.tr("Failed to reproject building data. Proceeding without it for overlap checks."))
                else:
                    # Crucially, ensure the building layer uses the exact same CRS object as roads_local_tm
                    if not bldg_tm_crs_obj.isIdenticalTo(local_tm_crs):
                        feedback.pushWarning(self.tr("Building TM CRS definition differs from road TM CRS. Forcing road TM CRS for buildings."))
                        temp_reproj_bldgs.setCrs(local_tm_crs)
                    reproj_buildings_layer = temp_reproj_bldgs
                    feedback.pushInfo(self.tr(f"Buildings reprojected to local TM: {reproj_buildings_layer.featureCount()} features. CRS: {reproj_buildings_layer.crs().description()}"))
            else:
                feedback.pushInfo(self.tr("No buildings after clipping, or clipping failed."))

        # Clean street network
        feedback.pushInfo(self.tr("Cleaning street network..."))
        filtered_streets_layer = QgsVectorLayer(f"LineString?crs={local_tm_crs.authid()}", "filtered_streets_full", "memory")
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        street_fields = roads_local_tm.fields()
        if street_fields.count() > 0: filtered_streets_dp.addAttributes(street_fields)
        else: filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = roads_local_tm.fields().lookupField(highway_tag)
        width_field_idx_on_source = roads_local_tm.fields().lookupField(widths_fieldname)

        for f_in in roads_local_tm.getFeatures():
            if feedback.isCanceled(): return {}
            highway_type_attr = f_in.attribute(highway_field_idx) if highway_field_idx != -1 else None
            highway_type_str = str(highway_type_attr).lower() if highway_type_attr is not None else ""
            width_from_defaults = default_widths.get(highway_type_str, 0.0)

            if width_from_defaults >= 0.5:
                new_feat = QgsFeature(filtered_streets_layer.fields())
                new_feat.setGeometry(f_in.geometry())
                new_feat.setAttributes(f_in.attributes())
                target_width_idx = new_feat.fields().lookupField(widths_fieldname)
                if target_width_idx != -1: # Ensure width field exists on target
                    current_osm_width = f_in.attribute(width_field_idx_on_source) if width_field_idx_on_source != -1 else None
                    # Try to use actual OSM width if valid, otherwise use default
                    try:
                        final_width = float(current_osm_width)
                        if final_width <= 0: # Or some other threshold for invalid OSM width
                            final_width = width_from_defaults
                    except (TypeError, ValueError):
                        final_width = width_from_defaults
                    new_feat.setAttribute(target_width_idx, final_width)
                features_to_add_to_filtered.append(new_feat)

        if features_to_add_to_filtered: filtered_streets_dp.addFeatures(features_to_add_to_filtered)
        feedback.pushInfo(self.tr(f"Streets filtered by type/width: {filtered_streets_layer.featureCount()} ways remain."))
        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets after filtering. Output will be empty."))
            return self.handle_empty_results(parameters, context, crs_4326, local_tm_crs)

        for i in range(dead_end_iterations): # Use parameter
            if feedback.isCanceled(): return {}
            feedback.pushInfo(self.tr(f"Removing unconnected lines (iteration {i+1}/{dead_end_iterations})..."))
            remove_unconnected_lines_v2(filtered_streets_layer)
        feedback.pushInfo(self.tr(f"After removing unconnected lines: {filtered_streets_layer.featureCount()} ways remain."))
        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(self.tr("No streets after removing dead-ends. Output will be empty."))
            return self.handle_empty_results(parameters, context, crs_4326, local_tm_crs)

        initial_protoblocks_layer = polygonize_lines(filtered_streets_layer, 'memory:initial_protoblocks_full', False)
        if not initial_protoblocks_layer or not initial_protoblocks_layer.isValid():
            raise QgsProcessingException(self.tr("Initial polygonization failed."))

        clean_protoblocks_layer_local_tm = QgsVectorLayer(f"Polygon?crs={local_tm_crs.authid()}", "clean_protoblocks_full", "memory")
        if initial_protoblocks_layer.featureCount() > 0:
            cloned_protoblock_feats = [QgsFeature(f) for f in initial_protoblocks_layer.getFeatures()]
            clean_protoblocks_layer_local_tm.dataProvider().addFeatures(cloned_protoblock_feats)
        feedback.pushInfo(self.tr(f"Protoblocks generated (local TM): {clean_protoblocks_layer_local_tm.featureCount()} features."))

        protoblocks_debug_dest_id = None
        debug_protoblocks_output_spec = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)
        if debug_protoblocks_output_spec:
            (protoblocks_debug_sink, protoblocks_debug_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, clean_protoblocks_layer_local_tm.fields(), QgsWkbTypes.Polygon, local_tm_crs)
            if protoblocks_debug_sink:
                for feat_pb_debug in clean_protoblocks_layer_local_tm.getFeatures():
                    if feedback.isCanceled(): return {}
                    protoblocks_debug_sink.addFeature(feat_pb_debug, QgsFeatureSink.FastInsert)
            else: protoblocks_debug_dest_id = None
        feedback.pushInfo(self.tr("Stage 1 (Protoblocks for Debug) Finished."))

        # --- Stage 2: Sidewalk Generation ---
        feedback.pushInfo(self.tr("Stage 2: Generating Sidewalks..."))
        dissolved_protoblocks_for_sidewalks = dissolve_tosinglegeom(clean_protoblocks_layer_local_tm)
        if not dissolved_protoblocks_for_sidewalks or not dissolved_protoblocks_for_sidewalks.isValid():
            feedback.pushWarning(self.tr("Failed to dissolve protoblocks for sidewalk generation. Using undissolved."))
            dissolved_protoblocks_for_sidewalks = clean_protoblocks_layer_local_tm

        sidewalk_lines_local_tm, exclusion_zones_local_tm, sure_zones_local_tm, width_adjusted_streets_local_tm = \
            generate_sidewalk_geometries_and_zones( street_network_layer=filtered_streets_layer, dissolved_protoblocks_layer=dissolved_protoblocks_for_sidewalks, buildings_layer=reproj_buildings_layer, check_building_overlap=sw_check_overlap, min_dist_to_building=sw_min_dist_building, min_generated_width_near_building=sw_min_width_near_building, added_width_for_sidewalk_axis_total=sw_added_width_total, curve_radius=sw_curve_radius, feedback=feedback)
        if feedback.isCanceled(): return {}
        if not sidewalk_lines_local_tm or not sidewalk_lines_local_tm.isValid():
            raise QgsProcessingException(self.tr("Sidewalk generation function failed or returned an invalid layer."))
        feedback.pushInfo(self.tr(f"Generated {sidewalk_lines_local_tm.featureCount()} raw sidewalk lines (local TM)."))

        sidewalks_final_epsg4326 = None
        if sidewalk_lines_local_tm.featureCount() > 0:
            reproject_sw_params = {'INPUT': sidewalk_lines_local_tm, 'TARGET_CRS': crs_4326, 'OUTPUT': 'memory:sidewalks_epsg4326_final_full'}
            res_sw_reproj = processing.run("native:reprojectlayer", reproject_sw_params, context=context, feedback=feedback, is_child_algorithm=True)
            if feedback.isCanceled(): return {}
            sidewalks_final_epsg4326 = QgsProcessingUtils.mapLayerFromString(res_sw_reproj['OUTPUT'], context)
            if not sidewalks_final_epsg4326 or not sidewalks_final_epsg4326.isValid():
                raise QgsProcessingException(self.tr("Failed to reproject sidewalks to EPSG:4326."))

        (sidewalks_sink, sidewalks_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_SIDEWALKS, context, sidewalks_final_epsg4326.fields() if sidewalks_final_epsg4326 else QgsFields(), QgsWkbTypes.LineString, crs_4326)
        if sidewalks_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_SIDEWALKS))
        if sidewalks_final_epsg4326 and sidewalks_final_epsg4326.featureCount() > 0:
            for feat_sw in sidewalks_final_epsg4326.getFeatures():
                if feedback.isCanceled(): return {}
                sidewalks_sink.addFeature(feat_sw, QgsFeatureSink.FastInsert)
        feedback.pushInfo(self.tr("Sidewalks output prepared."))

        (crossings_sink, crossings_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_CROSSINGS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326)
        (kerbs_sink, kerbs_dest_id) = self.parameterAsSink(parameters, self.OUTPUT_KERBS, context, QgsFields(), QgsWkbTypes.Point, crs_4326)

        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Algorithm Finished."))
        results = { self.OUTPUT_SIDEWALKS: sidewalks_dest_id, self.OUTPUT_CROSSINGS: crossings_dest_id, self.OUTPUT_KERBS: kerbs_dest_id }
        if protoblocks_debug_dest_id: results[self.OUTPUT_PROTOBLOCKS_DEBUG] = protoblocks_debug_dest_id
        return results

    def handle_empty_results(self, parameters, context, crs_4326_obj, local_tm_crs_if_defined=None):
        feedback = QgsProcessingFeedback()
        feedback.pushInfo("handle_empty_results called because a critical intermediate layer was empty.")
        (s_sink, s_id) = self.parameterAsSink(parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326_obj)
        (c_sink, c_id) = self.parameterAsSink(parameters, self.OUTPUT_CROSSINGS, context, QgsFields(), QgsWkbTypes.LineString, crs_4326_obj)
        (k_sink, k_id) = self.parameterAsSink(parameters, self.OUTPUT_KERBS, context, QgsFields(), QgsWkbTypes.Point, crs_4326_obj)
        results = { self.OUTPUT_SIDEWALKS: s_id, self.OUTPUT_CROSSINGS: c_id, self.OUTPUT_KERBS: k_id }
        debug_protoblocks_output_spec = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)
        if debug_protoblocks_output_spec:
            debug_crs = local_tm_crs_if_defined if local_tm_crs_if_defined and local_tm_crs_if_defined.isValid() else crs_4326_obj
            (p_sink, p_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, QgsFields(), QgsWkbTypes.Polygon, debug_crs)
            if p_id: results[self.OUTPUT_PROTOBLOCKS_DEBUG] = p_id
        return results

    def postProcessAlgorithm(self, context, feedback):
        return {}

from qgis import processing # For processing.run
# Ensure newline at end of file
