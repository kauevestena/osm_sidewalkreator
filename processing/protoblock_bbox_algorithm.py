# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingContext, QgsFeatureSink,
                       QgsProcessingMultiStepFeedback,
                       QgsVectorLayer, QgsProcessingUtils,
                       QgsCoordinateReferenceSystem, QgsFields,
                       QgsFeature, QgsRectangle, QgsWkbTypes,
                       QgsProcessingException, QgsField, QgsCoordinateTransform) # Added QgsCoordinateTransform
import math

# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (reproject_layer_localTM, cliplayer_v2, # cliplayer might not be needed
                                remove_unconnected_lines_v2, polygonize_lines)
from ..parameters import default_widths, highway_tag, CRS_LATLON_4326

class ProtoblockBboxAlgorithm(QgsProcessingAlgorithm):
    """
    Generates protoblocks by fetching OSM street data within a given
    bounding box, processing it, and then polygonizing the street network.
    """
    EXTENT = 'EXTENT' # Changed from individual BBOX parameters
    TIMEOUT = 'TIMEOUT'
    OUTPUT_PROTOBLOCKS = 'OUTPUT_PROTOBLOCKS'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ProtoblockBboxAlgorithm()

    def name(self):
        return 'generateprotoblocksfrombbox'

    def displayName(self):
        return self.tr('Generate Protoblocks from OSM Data in Bounding Box')

    def shortHelpString(self):
        return self.tr("Fetches OSM street data for a given BBOX (extent), processes it (filters by type, removes dangles), and polygonizes the network to create protoblocks. The input extent should ideally be in EPSG:4326. Output is in EPSG:4326.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT,
                self.tr('Area of Interest (Bounding Box Extent)'),
                # Optional: defaultValue=None, optional=False by default
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr('OSM Download Timeout (seconds)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=60, minValue=10, maxValue=300
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS,
                self.tr('Output Protoblocks (EPSG:4326)')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo(self.tr("Algorithm started: Generate Protoblocks from OSM Data in Bounding Box"))

        extent_param_value = self.parameterAsExtent(parameters, self.EXTENT, context)
        extent_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)

        feedback.pushInfo(self.tr(f"Input extent: {extent_param_value.toString()} (CRS: {extent_crs.authid()})"))

        # Transform extent to EPSG:4326 if necessary
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent_crs != crs_epsg4326:
            feedback.pushInfo(self.tr(f"Transforming input extent from {extent_crs.authid()} to EPSG:4326..."))
            transform = QgsCoordinateTransform(extent_crs, crs_epsg4326, context.transformContext())
            extent_4326 = transform.transform(extent_param_value) # extent_4326 is a QgsRectangle
            if extent_4326.isEmpty(): # Use isEmpty() for QgsRectangle
                raise QgsProcessingException(self.tr("Failed to transform extent to EPSG:4326 or transformed extent is empty."))
        else:
            extent_4326 = extent_param_value

        min_lon = extent_4326.xMinimum()
        min_lat = extent_4326.yMinimum()
        max_lon = extent_4326.xMaximum()
        max_lat = extent_4326.yMaximum()

        if not (min_lon < max_lon and min_lat < max_lat): # Basic check, QgsRectangle.isValid() is better
             if not extent_4326.isValid() or extent_4326.isEmpty(): # More robust check
                raise QgsProcessingException(self.tr("Provided extent is invalid or empty after transformation."))

        feedback.pushInfo(self.tr(f"Query BBOX (EPSG:4326): MinLon={min_lon}, MinLat={min_lat}, MaxLon={max_lon}, MaxLat={max_lat}"))

        # --- OSM Data Fetching (based on BBOX) ---
        feedback.pushInfo(self.tr("Fetching OSM street data for BBOX..."))
        # osm_query_string_by_bbox expects (min_lat, min_lon, max_lat, max_lon)
        query_str = osm_query_string_by_bbox(min_lat, min_lon, max_lat, max_lon,
                                             interest_key=highway_tag, way=True, node=False, relation=False)

        osm_geojson_str = get_osm_data(query_str, "osm_streets_bbox_algo",
                                       geomtype="LineString", timeout=timeout,
                                       return_as_string=True)
        if osm_geojson_str is None:
            raise QgsProcessingException(self.tr("Failed to download or parse OSM data (returned None)."))

        osm_data_layer_4326 = QgsVectorLayer(osm_geojson_str, "osm_streets_dl_bbox_4326_algo", "ogr")
        if not osm_data_layer_4326.isValid():
            details = ""
            if osm_geojson_str: details = f" GeoJSON string started with: {osm_geojson_str[:200]}"
            raise QgsProcessingException(self.tr(f"Downloaded OSM data did not form a valid vector layer.{details}"))

        feedback.pushInfo(self.tr(f"OSM data fetched: {osm_data_layer_4326.featureCount()} ways."))

        if osm_data_layer_4326.featureCount() == 0:
            feedback.pushWarning(self.tr("No OSM ways found within the specified BBOX. Output will be empty."))
            # Prepare an empty sink and return
            crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, crs_epsg4326)
            if sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # --- Reproject Fetched Data to Local TM ---
        # For lgt_0 of local TM, use center of the input BBOX
        lgt_0_tm = (min_lon + max_lon) / 2.0
        feedback.pushInfo(self.tr(f"Reprojecting OSM data to local TM centered at lon {lgt_0_tm}..."))

        reproj_layer, local_tm_crs = reproject_layer_localTM(
            osm_data_layer_4326, # Input is already clipped to BBOX by Overpass query
            outputpath=None,
            layername="osm_data_local_tm_bbox_algo",
            lgt_0=lgt_0_tm
        )
        if not reproj_layer.isValid():
            raise QgsProcessingException(self.tr("Failed to reproject OSM data to local TM."))

        feedback.pushInfo(self.tr(f"Data reprojected to local TM ({local_tm_crs.authid()}): {reproj_layer.featureCount()} ways."))

        # --- Clean Street Network ---
        feedback.pushInfo(self.tr("Cleaning street network..."))
        filtered_streets_layer = QgsVectorLayer(
            f"LineString?crs={local_tm_crs.authid()}",
            "filtered_streets_local_tm_bbox_algo", "memory")
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        if reproj_layer.fields().count() > 0:
            filtered_streets_dp.addAttributes(reproj_layer.fields())
        else:
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = reproj_layer.fields().lookupField(highway_tag)
        if highway_field_idx == -1:
            raise QgsProcessingException(self.tr(f"'{highway_tag}' not found in reprojected OSM data."))

        for f_in in reproj_layer.getFeatures():
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

        # --- Polygonize ---
        feedback.pushInfo(self.tr("Polygonizing street network..."))
        protoblocks_in_local_tm = polygonize_lines(
            filtered_streets_layer,
            outputlayer='memory:protoblocks_temp_bbox_algo',
            keepfields=False)

        if not protoblocks_in_local_tm or not protoblocks_in_local_tm.isValid():
            raise QgsProcessingException(self.tr("Polygonization failed or returned an invalid layer."))

        if not protoblocks_in_local_tm.crs().isValid() or protoblocks_in_local_tm.crs().authid() != local_tm_crs.authid():
            feedback.pushInfo(f"Warning: Polygonized layer CRS ({protoblocks_in_local_tm.crs().authid()}) differs from expected local TM CRS ({local_tm_crs.authid()}). Forcing correct CRS.")
            protoblocks_in_local_tm.setCrs(local_tm_crs)

        feedback.pushInfo(self.tr(f"Polygonization created {protoblocks_in_local_tm.featureCount()} protoblocks in local TM. CRS: {protoblocks_in_local_tm.crs().description()} ({protoblocks_in_local_tm.crs().authid()})"))

        # --- Re-clone to a new layer (Optional, but good for CRS robustness if issues persist) ---
        # For now, assume protoblocks_in_local_tm is fine after polygonize_lines's own CRS setting.
        # If not, re-cloning step from other algorithm can be inserted here.
        # protoblocks_layer_for_reprojection = protoblocks_in_local_tm (if not re-cloning)

        if protoblocks_in_local_tm.featureCount() == 0:
            feedback.pushWarning(self.tr("No protoblocks after polygonization. Output will be empty."))
            # Fallthrough to create an empty sink with correct type and CRS (EPSG:4326)
            crs_epsg4326_final = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_PROTOBLOCKS, context, QgsFields(), QgsWkbTypes.Polygon, crs_epsg4326_final)
            if sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # --- Final Reprojection to EPSG:4326 ---
        feedback.pushInfo(self.tr("Reprojecting final protoblocks to EPSG:4326..."))
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        reproject_params_final = {
            'INPUT': protoblocks_in_local_tm,
            'TARGET_CRS': crs_epsg4326,
            'OUTPUT': 'memory:protoblocks_final_epsg4326_bbox_algo'
        }
        sub_feedback_reproj_final = QgsProcessingMultiStepFeedback(1, feedback)
        sub_feedback_reproj_final.setCurrentStep(0)
        reproject_final_result = processing.run("native:reprojectlayer",
                                                reproject_params_final,
                                                context=context,
                                                feedback=sub_feedback_reproj_final,
                                                is_child_algorithm=True)
        if sub_feedback_reproj_final.isCanceled(): return {}

        output_layer_epsg4326 = QgsProcessingUtils.mapLayerFromString(reproject_final_result.get('OUTPUT'), context)
        if output_layer_epsg4326: output_layer_epsg4326.setName("protoblocks_epsg4326_loaded")

        if not output_layer_epsg4326 or not output_layer_epsg4326.isValid():
            raise QgsProcessingException(self.tr("Failed to obtain a valid layer after final reprojection to EPSG:4326."))

        if output_layer_epsg4326.crs().authid() != crs_epsg4326.authid():
            feedback.pushWarning(self.tr(f"CRS of final reprojected layer is {output_layer_epsg4326.crs().authid()} instead of desired {crs_epsg4326.authid()}."))

        feedback.pushInfo(self.tr(f"Final protoblocks reprojected to EPSG:4326. Features: {output_layer_epsg4326.featureCount()}, CRS: {output_layer_epsg4326.crs().authid()}"))

        # --- Prepare Sink and Output ---
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_PROTOBLOCKS, context,
            output_layer_epsg4326.fields(), QgsWkbTypes.Polygon, crs_epsg4326)
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS))

        if output_layer_epsg4326.featureCount() > 0:
            total_out_feats = output_layer_epsg4326.featureCount()
            for i, feat in enumerate(output_layer_epsg4326.getFeatures()):
                if feedback.isCanceled(): break
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                feedback.setProgress(int(90 + (i + 1) * 10.0 / total_out_feats))

        feedback.pushInfo(self.tr("Protoblock generation complete. Output (EPSG:4326) written."))
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        return {}

from qgis import processing # For processing.run
