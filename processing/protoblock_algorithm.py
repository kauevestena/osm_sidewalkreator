# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingContext,
    QgsFeatureSink,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingMultiStepFeedback,
    QgsVectorLayer,
    QgsProcessingUtils,
    QgsMessageLog,
    Qgis,
    QgsProcessingParameterNumber,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsFeatureRequest,
    QgsFields,
    QgsField,
    QgsFeature,
    edit,
    QgsWkbTypes,
    QgsProcessingException,
    QgsCoordinateTransform,
    QgsRectangle,
    QgsGeometry,
    QgsProject,
)  # Added QgsProcessingUtils and logging classes
from qgis.PyQt.QtCore import QVariant
import math  # For math.isfinite
import os

# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from .protoblock_bbox_algorithm import ProtoblockBboxAlgorithm
from ..generic_functions import (
    reproject_layer_localTM,
    cliplayer_v2,
    remove_unconnected_lines_v2,
    polygonize_lines,
)  # Using polygonize_lines wrapper for now
from ..parameters import default_widths, highway_tag, CRS_LATLON_4326


class ProtoblockAlgorithm(QgsProcessingAlgorithm):
    """
    Generates protoblocks by fetching OSM street data within an input polygon,
    processing it, and then polygonizing the street network.
    """

    INPUT_POLYGON = "INPUT_POLYGON"
    TIMEOUT = "TIMEOUT"
    OUTPUT_PROTOBLOCKS = "OUTPUT_PROTOBLOCKS"
    
    # Highway type checkbox parameters - one for each key in default_widths
    HIGHWAY_MOTORWAY = "HIGHWAY_MOTORWAY"
    HIGHWAY_TRUNK = "HIGHWAY_TRUNK"
    HIGHWAY_PRIMARY = "HIGHWAY_PRIMARY"
    HIGHWAY_RESIDENTIAL = "HIGHWAY_RESIDENTIAL"
    HIGHWAY_SECONDARY = "HIGHWAY_SECONDARY"
    HIGHWAY_TERTIARY = "HIGHWAY_TERTIARY"
    HIGHWAY_UNCLASSIFIED = "HIGHWAY_UNCLASSIFIED"
    HIGHWAY_ROAD = "HIGHWAY_ROAD"
    HIGHWAY_LIVING_STREET = "HIGHWAY_LIVING_STREET"
    HIGHWAY_TRUNK_LINK = "HIGHWAY_TRUNK_LINK"
    HIGHWAY_MOTORWAY_LINK = "HIGHWAY_MOTORWAY_LINK"
    HIGHWAY_SECONDARY_LINK = "HIGHWAY_SECONDARY_LINK"
    HIGHWAY_TERTIARY_LINK = "HIGHWAY_TERTIARY_LINK"
    HIGHWAY_PRIMARY_LINK = "HIGHWAY_PRIMARY_LINK"
    HIGHWAY_SIDEWALK = "HIGHWAY_SIDEWALK"
    HIGHWAY_CROSSING = "HIGHWAY_CROSSING"
    HIGHWAY_PATH = "HIGHWAY_PATH"
    HIGHWAY_SERVICE = "HIGHWAY_SERVICE"
    HIGHWAY_PEDESTRIAN = "HIGHWAY_PEDESTRIAN"
    HIGHWAY_ESCAPE = "HIGHWAY_ESCAPE"
    HIGHWAY_RACEWAY = "HIGHWAY_RACEWAY"
    HIGHWAY_CYCLEWAY = "HIGHWAY_CYCLEWAY"
    HIGHWAY_PROPOSED = "HIGHWAY_PROPOSED"
    HIGHWAY_CONSTRUCTION = "HIGHWAY_CONSTRUCTION"
    HIGHWAY_PLATFORM = "HIGHWAY_PLATFORM"
    HIGHWAY_SERVICES = "HIGHWAY_SERVICES"
    HIGHWAY_FOOTWAY = "HIGHWAY_FOOTWAY"
    HIGHWAY_TRACK = "HIGHWAY_TRACK"
    HIGHWAY_CORRIDOR = "HIGHWAY_CORRIDOR"
    HIGHWAY_STEPS = "HIGHWAY_STEPS"
    HIGHWAY_STREET_LAMP = "HIGHWAY_STREET_LAMP"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        try:
            print("[ProtoblockAlgorithm] createInstance() called")
            return ProtoblockAlgorithm()
        except Exception as e:
            try:
                QgsMessageLog.logMessage(
                    f"ProtoblockAlgorithm createInstance failed: {e}",
                    "SidewalKreator",
                    Qgis.Critical,
                )
                import traceback

                traceback.print_exc()
            except Exception:
                pass
            raise

    def name(self):
        return "generateprotoblocksfromosm"

    def displayName(self):
        return self.tr("Generate Protoblocks from OSM Data in Polygon")

    # Removed group(self) and groupId(self) to place algorithm directly under provider

    def shortHelpString(self):
        return self.tr(
            "Fetches OSM street data for an input polygon area, processes it (filters by type, removes dangles), and polygonizes the network to create protoblocks. "
            "Input must have a valid layer CRS, which will be used automatically. Output is always in EPSG:4326."
        )

    def icon(self):
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(plugin_dir, "icon.png")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGON,
                self.tr("Input Area Polygon Layer"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr("OSM Download Timeout (seconds)"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=60,
                minValue=10,
                maxValue=300,
            )
        )
        
        # Highway type checkboxes - motorized roads checked by default
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_MOTORWAY,
                self.tr("Include Motorway"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_TRUNK,
                self.tr("Include Trunk"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PRIMARY,
                self.tr("Include Primary"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_RESIDENTIAL,
                self.tr("Include Residential"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_SECONDARY,
                self.tr("Include Secondary"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_TERTIARY,
                self.tr("Include Tertiary"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_UNCLASSIFIED,
                self.tr("Include Unclassified"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_ROAD,
                self.tr("Include Road"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_LIVING_STREET,
                self.tr("Include Living Street"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_TRUNK_LINK,
                self.tr("Include Trunk Link"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_MOTORWAY_LINK,
                self.tr("Include Motorway Link"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_SECONDARY_LINK,
                self.tr("Include Secondary Link"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_TERTIARY_LINK,
                self.tr("Include Tertiary Link"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PRIMARY_LINK,
                self.tr("Include Primary Link"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_SIDEWALK,
                self.tr("Include Sidewalk"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_CROSSING,
                self.tr("Include Crossing"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PATH,
                self.tr("Include Path"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_SERVICE,
                self.tr("Include Service"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PEDESTRIAN,
                self.tr("Include Pedestrian"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_ESCAPE,
                self.tr("Include Escape"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_RACEWAY,
                self.tr("Include Raceway"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_CYCLEWAY,
                self.tr("Include Cycleway"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PROPOSED,
                self.tr("Include Proposed"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_CONSTRUCTION,
                self.tr("Include Construction"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_PLATFORM,
                self.tr("Include Platform"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_SERVICES,
                self.tr("Include Services"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_FOOTWAY,
                self.tr("Include Footway"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_TRACK,
                self.tr("Include Track"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_CORRIDOR,
                self.tr("Include Corridor"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_STEPS,
                self.tr("Include Steps"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.HIGHWAY_STREET_LAMP,
                self.tr("Include Street Lamp"),
                defaultValue=False,
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS, self.tr("Output Protoblocks (EPSG:4326)")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo(
            self.tr("Algorithm started: Generate Protoblocks from OSM Data in Polygon")
        )  # General start message

        input_polygon_feature_source = self.parameterAsSource(
            parameters, self.INPUT_POLYGON, context
        )
        if input_polygon_feature_source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT_POLYGON)
            )

        # Use the source CRS from the input layer
        source_crs = input_polygon_feature_source.sourceCrs()
        if not source_crs or not source_crs.isValid():
            raise QgsProcessingException(
                self.tr(
                    "Input layer has no valid CRS. Please define a CRS on the layer and try again."
                )
            )
        effective_input_crs = source_crs
        feedback.pushInfo(
            f"Using source CRS from input layer: {effective_input_crs.authid()}"
        )

        feedback.pushInfo(f"Input polygon source CRS: {source_crs.authid()}")

        actual_input_layer = input_polygon_feature_source.materialize(
            QgsFeatureRequest()
        )
        if actual_input_layer is None:
            raise QgsProcessingException(
                self.tr("Failed to materialize input polygon layer.")
            )

        if not actual_input_layer.isValid() or actual_input_layer.featureCount() == 0:
            raise QgsProcessingException(
                self.tr(
                    "Materialized input polygon layer is invalid or empty. Cannot proceed."
                )
            )

        # Ensure the materialized layer has the same CRS as the source
        if actual_input_layer.crs().authid() != effective_input_crs.authid():
            actual_input_layer.setCrs(effective_input_crs)

        feedback.pushInfo(
            self.tr(
                f"Using input polygon layer: {actual_input_layer.name()} ({actual_input_layer.featureCount()} features)"
            )
        )

        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        # feedback.pushInfo(f"Timeout: {timeout} seconds") # Might be too verbose for normal operation

        # Get highway type selections from checkboxes
        allowed_highway_types = set()
        highway_checkbox_mapping = {
            "motorway": self.HIGHWAY_MOTORWAY,
            "trunk": self.HIGHWAY_TRUNK,
            "primary": self.HIGHWAY_PRIMARY,
            "residential": self.HIGHWAY_RESIDENTIAL,
            "secondary": self.HIGHWAY_SECONDARY,
            "tertiary": self.HIGHWAY_TERTIARY,
            "unclassified": self.HIGHWAY_UNCLASSIFIED,
            "road": self.HIGHWAY_ROAD,
            "living_street": self.HIGHWAY_LIVING_STREET,
            "trunk_link": self.HIGHWAY_TRUNK_LINK,
            "motorway_link": self.HIGHWAY_MOTORWAY_LINK,
            "secondary_link": self.HIGHWAY_SECONDARY_LINK,
            "tertiary_link": self.HIGHWAY_TERTIARY_LINK,
            "primary_link": self.HIGHWAY_PRIMARY_LINK,
            "sidewalk": self.HIGHWAY_SIDEWALK,
            "crossing": self.HIGHWAY_CROSSING,
            "path": self.HIGHWAY_PATH,
            "service": self.HIGHWAY_SERVICE,
            "pedestrian": self.HIGHWAY_PEDESTRIAN,
            "escape": self.HIGHWAY_ESCAPE,
            "raceway": self.HIGHWAY_RACEWAY,
            "cycleway": self.HIGHWAY_CYCLEWAY,
            "proposed": self.HIGHWAY_PROPOSED,
            "construction": self.HIGHWAY_CONSTRUCTION,
            "platform": self.HIGHWAY_PLATFORM,
            "services": self.HIGHWAY_SERVICES,
            "footway": self.HIGHWAY_FOOTWAY,
            "track": self.HIGHWAY_TRACK,
            "corridor": self.HIGHWAY_CORRIDOR,
            "steps": self.HIGHWAY_STEPS,
            "street_lamp": self.HIGHWAY_STREET_LAMP,
        }
        
        for highway_type, param_name in highway_checkbox_mapping.items():
            if self.parameterAsBoolean(parameters, param_name, context):
                allowed_highway_types.add(highway_type)

        feedback.pushInfo(self.tr("Calculating BBOX for OSM query..."))

        # Ensure input_poly_for_bbox is in EPSG:4326
        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        input_poly_for_bbox = actual_input_layer
        if (
            effective_input_crs.authid() != crs_4326.authid()
        ):  # Compare authids for robustness
            feedback.pushInfo(
                f"Reprojecting input layer from {effective_input_crs.authid()} to EPSG:4326 for BBOX calculation."
            )
            reproject_params = {
                "INPUT": actual_input_layer,
                "TARGET_CRS": crs_4326,
                "OUTPUT": "memory:input_reprojected_for_bbox",
            }
            sub_feedback_reproject = QgsProcessingMultiStepFeedback(
                1, feedback
            )  # Child feedback
            sub_feedback_reproject.setCurrentStep(0)

            try:
                reproject_result = processing.run(
                    "native:reprojectlayer",
                    reproject_params,
                    context=context,
                    feedback=sub_feedback_reproject,
                    is_child_algorithm=True,
                )
                feedback.pushInfo(f"Results: {reproject_result}")

                if sub_feedback_reproject.isCanceled():
                    return {}

                if not reproject_result or "OUTPUT" not in reproject_result:
                    raise QgsProcessingException(
                        self.tr("Reprojection did not return expected output.")
                    )

                # Try to get the output layer
                output_path = reproject_result["OUTPUT"]
                feedback.pushInfo(f"Reprojection output path: {output_path}")

                # Use QgsProcessingUtils to get the layer properly
                input_poly_for_bbox = QgsProcessingUtils.mapLayerFromString(
                    output_path, context
                )

                if input_poly_for_bbox is None:
                    # Fallback to creating layer directly
                    feedback.pushInfo("Falling back to direct layer creation")
                    input_poly_for_bbox = QgsVectorLayer(
                        output_path,
                        "input_reprojected_for_bbox_layer",
                        "memory" if "memory:" in output_path else "ogr",
                    )

                if input_poly_for_bbox is None or not input_poly_for_bbox.isValid():
                    raise QgsProcessingException(
                        self.tr(
                            f"Failed to create layer from reprojection output: {output_path}"
                        )
                    )

                if input_poly_for_bbox.featureCount() == 0:
                    raise QgsProcessingException(
                        self.tr(
                            f"Reprojected layer is empty. Layer path: {output_path}"
                        )
                    )

                feedback.pushInfo(
                    f"Successfully reprojected to EPSG:4326. Features: {input_poly_for_bbox.featureCount()}"
                )

            except Exception as e:
                raise QgsProcessingException(
                    self.tr(f"Reprojection failed with error: {str(e)}")
                )
        else:
            feedback.pushInfo("Input layer is already in EPSG:4326.")

        # Calculate BBOX from the (potentially reprojected) layer
        extent_4326 = input_poly_for_bbox.extent()

        # Debug: log the extent details
        feedback.pushInfo(f"Layer extent: {extent_4326.toString()}")
        feedback.pushInfo(f"Extent isNull: {extent_4326.isNull()}")
        feedback.pushInfo(
            f"Extent bounds: xMin={extent_4326.xMinimum()}, yMin={extent_4326.yMinimum()}, xMax={extent_4326.xMaximum()}, yMax={extent_4326.yMaximum()}"
        )

        # Also check individual feature geometries for debugging
        feature_count = 0
        for feature in input_poly_for_bbox.getFeatures():
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                geom_bbox = geom.boundingBox()
                feedback.pushInfo(
                    f"Feature {feature_count} geometry bbox: {geom_bbox.toString()}"
                )
                feature_count += 1
                if feature_count >= 3:  # Limit debug output
                    break

        # Validate extent coordinates are within reasonable geographic bounds
        if (
            extent_4326.isNull()
            or not all(
                map(
                    math.isfinite,
                    [
                        extent_4326.xMinimum(),
                        extent_4326.yMinimum(),
                        extent_4326.xMaximum(),
                        extent_4326.yMaximum(),
                    ],
                )
            )
            or extent_4326.xMinimum() < -180
            or extent_4326.xMaximum() > 180
            or extent_4326.yMinimum() < -90
            or extent_4326.yMaximum() > 90
        ):
            raise QgsProcessingException(
                self.tr(
                    f"Invalid bounding box coordinates. Extent: {extent_4326.toString()}. "
                    f"Coordinates must be in valid lat/lon range (-180 to 180 for longitude, -90 to 90 for latitude). "
                    f"Ensure the input layer '{input_poly_for_bbox.name()}' contains valid geometries and was properly reprojected to EPSG:4326."
                )
            )

        # Delegate to BBOX algorithm using the polygon extent, to match the bbox pipeline behavior
        west_lon = extent_4326.xMinimum()
        east_lon = extent_4326.xMaximum()
        south_lat = extent_4326.yMinimum()
        north_lat = extent_4326.yMaximum()
        bbox_str = f"{west_lon},{east_lon},{south_lat},{north_lat} [EPSG:4326]"
        feedback.pushInfo(self.tr(f"Delegating to Protoblocks BBOX pipeline with extent: {bbox_str}"))

        bbox_params = {
            ProtoblockBboxAlgorithm.EXTENT: bbox_str,
            ProtoblockBboxAlgorithm.TIMEOUT: self.parameterAsInt(parameters, self.TIMEOUT, context),
            self.OUTPUT_PROTOBLOCKS: parameters.get(self.OUTPUT_PROTOBLOCKS, "memory:protoblocks"),
        }
        from qgis import processing as qproc
        return qproc.run(
            ProtoblockBboxAlgorithm(),
            bbox_params,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

        min_lgt, min_lat = extent_4326.xMinimum(), extent_4326.yMinimum()
        max_lgt, max_lat = extent_4326.xMaximum(), extent_4326.yMaximum()
        feedback.pushInfo(
            f"Calculated BBOX (EPSG:4326): MinLon={min_lgt}, MinLat={min_lat}, MaxLon={max_lgt}, MaxLat={max_lat}"
        )

        # Generate OSM Query String
        query_str = osm_query_string_by_bbox(
            min_lat,
            min_lgt,
            max_lat,
            max_lgt,
            interest_key=highway_tag,
            way=True,
            node=False,
            relation=False,
        )
        # feedback.pushInfo(f"Generated OSM Query (first 100 chars): {query_str[:100]}...") # Can be verbose

        feedback.pushInfo(self.tr("Fetching OSM street data..."))
        osm_geojson_path = get_osm_data(
            query_str,
            "osm_streets_data_algo",
            geomtype="LineString",
            timeout=timeout,
            return_as_string=False,
        )

        if osm_geojson_path is None:
            raise QgsProcessingException(
                self.tr("Failed to download or parse OSM data (returned None).")
            )

        osm_data_layer_4326 = QgsVectorLayer(
            osm_geojson_path, "osm_streets_dl_4326_algo", "ogr"
        )
        if not osm_data_layer_4326.isValid():
            raise QgsProcessingException(
                self.tr("Downloaded OSM data did not form a valid vector layer.")
            )

        feedback.pushInfo(
            self.tr(f"OSM data fetched: {osm_data_layer_4326.featureCount()} ways.")
        )

        feedback.pushInfo(self.tr("Clipping and reprojecting OSM data..."))
        clipped_osm_data_4326_path = "memory:clipped_osm_data_4326_algo"
        # Use input_poly_for_bbox for clipping (it's the original input polygon, possibly reprojected to 4326)
        clipped_osm_layer_4326 = cliplayer_v2(
            osm_data_layer_4326, input_poly_for_bbox, clipped_osm_data_4326_path
        )

        if not clipped_osm_layer_4326.isValid():
            raise QgsProcessingException(self.tr("Clipping of OSM data failed."))

        feedback.pushInfo(
            self.tr(
                f"OSM data clipped: {clipped_osm_layer_4326.featureCount()} ways remain."
            )
        )

        if clipped_osm_layer_4326.featureCount() == 0:
            feedback.pushWarning(
                self.tr("No OSM ways after clipping. Output will be empty.")
            )
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_PROTOBLOCKS,
                context,
                QgsFields(),
                QgsWkbTypes.Polygon,
                local_tm_crs if "local_tm_crs" in locals() else crs_4326,
            )
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        clipped_reproj_layer, local_tm_crs = reproject_layer_localTM(
            clipped_osm_layer_4326,
            outputpath=None,
            layername="clipped_osm_local_tm_algo",
            lgt_0=extent_4326.center().x(),
        )
        if not clipped_reproj_layer.isValid():
            raise QgsProcessingException(
                self.tr("Failed to reproject clipped OSM data.")
            )

        feedback.pushInfo(
            self.tr(
                f"Data reprojected to local TM ({local_tm_crs.authid()}): {clipped_reproj_layer.featureCount()} ways."
            )
        )

        feedback.pushInfo(self.tr("Cleaning street network..."))
        filtered_streets_layer = QgsVectorLayer(
            "LineString", "filtered_streets_local_tm_algo", "memory"
        )
        filtered_streets_layer.setCrs(local_tm_crs)
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        if clipped_reproj_layer.fields().count() > 0:
            filtered_streets_dp.addAttributes(clipped_reproj_layer.fields())
        else:
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = clipped_reproj_layer.fields().lookupField(highway_tag)
        if highway_field_idx == -1:
            raise QgsProcessingException(
                self.tr(f"'{highway_tag}' not found in reprojected OSM data.")
            )

        for f_in in clipped_reproj_layer.getFeatures():
            if feedback.isCanceled():
                return {}
            highway_type_attr = f_in.attribute(highway_field_idx)
            highway_type_str = (
                str(highway_type_attr).lower() if highway_type_attr is not None else ""
            )
            # Use checkbox selections instead of hardcoded width filtering
            if highway_type_str in allowed_highway_types:
                width = default_widths.get(highway_type_str, 0.0)
                if width >= 0.5:  # Keep the width check for consistency
                    new_feat = QgsFeature(filtered_streets_layer.fields())
                    new_feat.setGeometry(f_in.geometry())
                    new_feat.setAttributes(f_in.attributes())
                    features_to_add_to_filtered.append(new_feat)

        if features_to_add_to_filtered:
            filtered_streets_dp.addFeatures(features_to_add_to_filtered)
        feedback.pushInfo(
            self.tr(
                f"Streets filtered by type/width: {filtered_streets_layer.featureCount()} ways remain."
            )
        )

        if filtered_streets_layer.featureCount() == 0:
            feedback.pushWarning(
                self.tr("No streets after filtering. Output will be empty.")
            )
            (sink_empty, dest_id_empty) = self.parameterAsSink(
                parameters,
                self.OUTPUT_PROTOBLOCKS,
                context,
                QgsFields(),
                QgsWkbTypes.Polygon,
                QgsCoordinateReferenceSystem(CRS_LATLON_4326),
            )
            if sink_empty is None:
                raise QgsProcessingException(
                    self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS)
                )
            layer_obj = QgsProcessingUtils.mapLayerFromString(dest_id_empty, context)
            try:
                QgsProject.instance().addMapLayer(layer_obj, addToLegend=False)
            except Exception:
                pass
            return {self.OUTPUT_PROTOBLOCKS: layer_obj if layer_obj else dest_id_empty}

        try:
            feedback.pushInfo(self.tr("Removing unconnected lines..."))
            remove_unconnected_lines_v2(filtered_streets_layer)
            feedback.pushInfo(
                self.tr(
                    f"After removing unconnected lines: {filtered_streets_layer.featureCount()} ways remain."
                )
            )
        except Exception as e:
            feedback.pushWarning(self.tr(f"Could not remove unconnected lines: {e}."))

        feedback.pushInfo(self.tr("Polygonizing street network..."))
        protoblocks_layer = polygonize_lines(
            filtered_streets_layer,
            outputlayer="memory:protoblocks_temp_algo",
            keepfields=False,
        )

        if not protoblocks_layer or not protoblocks_layer.isValid():
            raise QgsProcessingException(
                self.tr("Polygonization failed or returned an invalid layer.")
            )

        # Ensure protoblocks_layer has the correct CRS (local_tm_crs)
        # The polygonize_lines wrapper should handle this, but an explicit set here is safer.
        if (
            not protoblocks_layer.crs().isValid()
            or protoblocks_layer.crs().authid() != local_tm_crs.authid()
        ):
            feedback.pushInfo(
                f"Warning: Protoblocks layer CRS ({protoblocks_layer.crs().authid()}) differs from expected local TM CRS ({local_tm_crs.authid()}). Forcing correct CRS."
            )
            protoblocks_layer.setCrs(local_tm_crs)

        if (
            not protoblocks_layer or not protoblocks_layer.isValid()
        ):  # protoblocks_layer is from polygonize_lines
            raise QgsProcessingException(
                self.tr("Polygonization failed or returned an invalid layer.")
            )

        feedback.pushInfo(
            self.tr(
                f"Initial polygonization created {protoblocks_layer.featureCount()} features. Initial CRS: {protoblocks_layer.crs().authid()} - {protoblocks_layer.crs().description()}"
            )
        )

        # --- Re-clone to a new layer with explicitly defined CRS ---
        feedback.pushInfo(
            self.tr(
                f"Re-cloning features to a new layer with CRS: {local_tm_crs.authid()} - {local_tm_crs.description()}"
            )
        )

        # Define the URI for the new memory layer with the correct CRS
        # Note: local_tm_crs.authid() will be empty for a custom CRS. Using WKT or Proj string might be more robust if available.
        # However, QgsVectorLayer constructor takes a QgsCoordinateReferenceSystem object directly.
        clean_protoblocks_layer_uri = f"Polygon?crs={local_tm_crs.toWkt()}"
        # Using WKT ensures the full CRS definition is passed for the new layer.
        # Alternatively, if QGIS handles custom CRS objects well by their internal ID in memory sources:
        # clean_protoblocks_layer_uri = f"Polygon?crs=USER:{local_tm_crs.userFriendlyIdentifier().replace(' ','_')}" # Needs testing if this works reliably for non-saved custom CRSs
        # For now, WKT is safest if a direct CRS object isn't accepted in URI for memory layers.
        # Actually, QgsVectorLayer can take QgsCoordinateReferenceSystem object directly in constructor, but not via URI string alone easily for custom CRSs.
        # The best way to create a memory layer with a specific custom CRS is:
        clean_protoblocks_layer = QgsVectorLayer(
            "Polygon", "protoblocks_clean_algo", "memory"
        )
        clean_protoblocks_layer.setCrs(local_tm_crs)  # Set the CRS object directly

        # Define fields (should be none if keepfields=False in polygonize_lines)
        # If polygonize_lines's keepfields=False was effective, protoblocks_layer.fields() would be empty or minimal.
        # Forcing no fields for protoblocks:
        # clean_protoblocks_dp = clean_protoblocks_layer.dataProvider()
        # clean_protoblocks_dp.addAttributes([]) # No attributes
        # clean_protoblocks_layer.updateFields() # Not strictly needed if no fields added

        if protoblocks_layer.featureCount() > 0:
            temp_feats_for_clean_layer = []
            for feat_original in protoblocks_layer.getFeatures():
                if feedback.isCanceled():
                    return {}
                new_feat_clean = QgsFeature(
                    clean_protoblocks_layer.fields()
                )  # Fields for the clean layer
                new_feat_clean.setGeometry(
                    feat_original.geometry()
                )  # Geometries are numerically in local_tm_crs
                # No attributes to copy if keepfields=False was effective
                temp_feats_for_clean_layer.append(new_feat_clean)

            clean_protoblocks_layer.dataProvider().addFeatures(
                temp_feats_for_clean_layer
            )

        feedback.pushInfo(
            self.tr(
                f"Re-cloned to clean_protoblocks_layer: {clean_protoblocks_layer.featureCount()} features. Clean layer CRS: {clean_protoblocks_layer.crs().authid()} - {clean_protoblocks_layer.crs().description()}"
            )
        )

        # Use this clean_protoblocks_layer for geometry inspection and for the sink
        protoblocks_layer_for_sink = clean_protoblocks_layer
        # --- End Re-clone ---

        # --- Geometry Inspection Loop (on clean_protoblocks_layer) ---
        if protoblocks_layer_for_sink.featureCount() > 0:
            feedback.pushInfo(
                self.tr("Inspecting first few (re-cloned) protoblock geometries...")
            )
            # ... (geometry inspection loop as before, but using protoblocks_layer_for_sink) ...
            count = 0
            for feat in protoblocks_layer_for_sink.getFeatures():
                if count >= 5:
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

        if protoblocks_layer_for_sink.featureCount() == 0:
            feedback.pushWarning(
                self.tr(
                    "No protoblocks after polygonization and re-cloning. Output will be an empty layer."
                )
            )

        # Prepare the final output sink
        feedback.pushInfo(
            self.tr(
                f"Preparing final sink with CRS: {local_tm_crs.authid()} - {local_tm_crs.description()}"
            )
        )  # This log refers to the CRS before final reprojection

        # --- Final Reprojection to EPSG:4326 ---
        feedback.pushInfo(self.tr("Reprojecting final protoblocks to EPSG:4326..."))
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        reproject_params_final = {
            "INPUT": protoblocks_layer_for_sink,  # This is clean_protoblocks_layer in local_tm_crs
            "TARGET_CRS": crs_epsg4326,
            "OUTPUT": "memory:protoblocks_final_epsg4326_algo",
        }
        sub_feedback_reproj_final = QgsProcessingMultiStepFeedback(1, feedback)
        sub_feedback_reproj_final.setCurrentStep(0)
        reproject_final_result = processing.run(
            "native:reprojectlayer",
            reproject_params_final,
            context=context,
            feedback=sub_feedback_reproj_final,
            is_child_algorithm=True,
        )
        if sub_feedback_reproj_final.isCanceled():
            return {}

        # Get the output from native:reprojectlayer
        # It should be a QgsVectorLayer object if 'OUTPUT' was 'memory:...'
        # and the algorithm is well-behaved with memory outputs.
        reprojected_output_value = reproject_final_result.get("OUTPUT")
        output_layer_epsg4326 = None

        if isinstance(reprojected_output_value, QgsVectorLayer):
            output_layer_epsg4326 = reprojected_output_value
        elif reprojected_output_value is not None:
            feedback.pushInfo(
                self.tr(
                    f"Reprojection output was of type {type(reprojected_output_value)}; attempting to load via QgsProcessingUtils.mapLayerFromString"
                )
            )
            output_layer_epsg4326 = QgsProcessingUtils.mapLayerFromString(
                str(reprojected_output_value), context
            )
            if output_layer_epsg4326:
                output_layer_epsg4326.setName("protoblocks_epsg4326_loaded")

        if (
            not output_layer_epsg4326 or not output_layer_epsg4326.isValid()
        ):  # Check if None or invalid
            raise QgsProcessingException(
                self.tr(
                    "Failed to obtain a valid layer after final reprojection to EPSG:4326."
                )
            )

        # Ensure CRS is correctly EPSG:4326 after reprojection
        # native:reprojectlayer should handle setting the CRS correctly on its output.
        # If it's not EPSG:4326 at this point, something is more fundamentally wrong with the reprojection.
        if output_layer_epsg4326.crs().authid() != crs_epsg4326.authid():
            feedback.pushWarning(
                self.tr(
                    f"CRS of final reprojected layer is {output_layer_epsg4326.crs().authid()} instead of desired {crs_epsg4326.authid()}."
                )
            )

        # Validate geographic bounds; if out-of-range, force a manual transform as fallback
        ext = output_layer_epsg4326.extent()
        if (
            ext.isNull()
            or ext.xMinimum() < -180
            or ext.xMaximum() > 180
            or ext.yMinimum() < -90
            or ext.yMaximum() > 90
        ):
            feedback.pushWarning(
                self.tr(
                    "Detected coordinates outside valid EPSG:4326 bounds after reprojection. Applying manual transform as fallback."
                )
            )
            try:
                transformer = QgsCoordinateTransform(
                    local_tm_crs, crs_epsg4326, context.transformContext()
                )
                manual_layer = QgsVectorLayer(
                    f"Polygon?crs={crs_epsg4326.authid()}",
                    "protoblocks_epsg4326_manual",
                    "memory",
                )
                manual_dp = manual_layer.dataProvider()
                manual_dp.addAttributes(output_layer_epsg4326.fields())
                manual_layer.updateFields()
                feats = []
                for f in protoblocks_layer_for_sink.getFeatures():
                    g = f.geometry()
                    if not g.isEmpty():
                        g = QgsGeometry(g)  # copy
                        g.transform(transformer)
                    nf = QgsFeature(manual_layer.fields())
                    nf.setGeometry(g)
                    nf.setAttributes(f.attributes())
                    feats.append(nf)
                if feats:
                    manual_dp.addFeatures(feats)
                output_layer_epsg4326 = manual_layer
                feedback.pushInfo(self.tr("Manual transform to EPSG:4326 completed."))
            except Exception as e:
                feedback.pushWarning(self.tr(f"Manual transform failed: {e}"))

        feedback.pushInfo(
            self.tr(
                f"Final protoblocks reprojected to EPSG:4326. Features: {output_layer_epsg4326.featureCount()}, CRS: {output_layer_epsg4326.crs().authid()}"
            )
        )
        # --- End Final Reprojection ---

        # Write to sink (no fields) and return the layer object from context
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            QgsFields(),  # no fields expected in tests
            QgsWkbTypes.Polygon,
            crs_epsg4326,
        )
        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS)
            )
        if output_layer_epsg4326.featureCount() > 0:
            for feat in output_layer_epsg4326.getFeatures():
                f = QgsFeature()
                f.setGeometry(feat.geometry())
                sink.addFeature(f, QgsFeatureSink.FastInsert)
        layer_obj = QgsProcessingUtils.mapLayerFromString(dest_id, context)
        try:
            QgsProject.instance().addMapLayer(layer_obj, addToLegend=False)
        except Exception:
            pass
        feedback.pushInfo(self.tr("Protoblock generation complete. Sink written."))
        return {self.OUTPUT_PROTOBLOCKS: layer_obj if layer_obj else dest_id}

    def postProcessAlgorithm(self, context, feedback):
        # Clean up any persistent temporary layers if necessary
        # Memory layers are usually handled by QGIS, but explicit deletion can be added if needed
        # e.g., for layers like 'input_polygon_4326_path' if they were file-based.
        return {}


try:
    from qgis import processing
except ImportError as e:
    QgsMessageLog.logMessage(
        f"Failed to import processing module: {e}",
        "SidewalKreator",
        Qgis.Critical,
    )
    raise
