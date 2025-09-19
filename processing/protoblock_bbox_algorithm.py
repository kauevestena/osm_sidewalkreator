# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingContext,
    QgsFeatureSink,
    QgsProcessingMultiStepFeedback,
    QgsVectorLayer,
    QgsProcessingUtils,
    QgsCoordinateReferenceSystem,
    QgsFields,
    QgsFeature,
    QgsRectangle,
    QgsGeometry,
    QgsWkbTypes,
    QgsProcessingException,
    QgsField,
    QgsCoordinateTransform,
    QgsProcessingParameterExtent,
    QgsSpatialIndex,
    QgsFeatureRequest,
)  # Added QgsProcessingParameterExtent, Added QgsCoordinateTransform, Added QgsSpatialIndex
import math
import os



# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (
    reproject_layer_localTM,
    cliplayer_v2,  # cliplayer might not be needed
    remove_unconnected_lines_v2,
    polygonize_lines,
    layer_from_featlist,
    create_incidence_field_layers_A_B,
)
from ..parameters import (
    default_widths,
    highway_tag,
    CRS_LATLON_4326,
    cutoff_percent_protoblock,
)


class ProtoblockBboxAlgorithm(QgsProcessingAlgorithm):
    """
    Generates protoblocks by fetching OSM street data within a given
    bounding box, processing it, and then polygonizing the street network.
    """

    EXTENT = "EXTENT"  # Changed from individual BBOX parameters
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
            print("[ProtoblockBboxAlgorithm] createInstance() called")
            return ProtoblockBboxAlgorithm()
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog, Qgis
                import traceback

                QgsMessageLog.logMessage(
                    f"ProtoblockBboxAlgorithm createInstance failed: {e}",
                    "SidewalKreator",
                    Qgis.Critical,
                )
                traceback.print_exc()
            except Exception:
                pass
            raise

    def name(self):
        return "generateprotoblocksfrombbox"

    def displayName(self):
        return self.tr("Generate Protoblocks from OSM Data in Bounding Box")

    def shortHelpString(self):
        return self.tr(
            "Fetches OSM street data for a given BBOX (extent), processes it (filters by type, removes dangles), and polygonizes the network to create protoblocks. The input extent should ideally be in EPSG:4326. Output is in EPSG:4326."
        )

    def icon(self):
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(plugin_dir, "icon.png")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(  # Now correctly imported at the top
                self.EXTENT,
                self.tr("Area of Interest (Bounding Box Extent)"),
                # Optional: defaultValue=None, optional=False by default
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
            self.tr(
                "Algorithm started: Generate Protoblocks from OSM Data in Bounding Box"
            )
        )

        extent_param_value = self.parameterAsExtent(parameters, self.EXTENT, context)
        extent_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)

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

        feedback.pushInfo(
            self.tr(
                f"Input extent: {extent_param_value.toString()} (CRS: {extent_crs.authid()})"
            )
        )

        # Transform extent to EPSG:4326 if necessary
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent_crs != crs_epsg4326:
            feedback.pushInfo(
                self.tr(
                    f"Transforming input extent from {extent_crs.authid()} to EPSG:4326..."
                )
            )
            transform = QgsCoordinateTransform(
                extent_crs, crs_epsg4326, context.transformContext()
            )
            extent_4326 = transform.transform(
                extent_param_value
            )  # extent_4326 is a QgsRectangle
            if extent_4326.isEmpty():  # Use isEmpty() for QgsRectangle
                raise QgsProcessingException(
                    self.tr(
                        "Failed to transform extent to EPSG:4326 or transformed extent is empty."
                    )
                )
        else:
            extent_4326 = extent_param_value

        min_lon = extent_4326.xMinimum()
        min_lat = extent_4326.yMinimum()
        max_lon = extent_4326.xMaximum()
        max_lat = extent_4326.yMaximum()

        if not (
            min_lon < max_lon and min_lat < max_lat
        ):  # Basic check, QgsRectangle.isValid() is better
            if not extent_4326.isValid() or extent_4326.isEmpty():  # More robust check
                raise QgsProcessingException(
                    self.tr("Provided extent is invalid or empty after transformation.")
                )

        feedback.pushInfo(
            self.tr(
                f"Query BBOX (EPSG:4326): MinLon={min_lon}, MinLat={min_lat}, MaxLon={max_lon}, MaxLat={max_lat}"
            )
        )

        # --- OSM Data Fetching (based on BBOX) ---
        feedback.pushInfo(self.tr("Fetching OSM street data for BBOX..."))
        # osm_query_string_by_bbox expects (min_lat, min_lon, max_lat, max_lon)
        query_str = osm_query_string_by_bbox(
            min_lat,
            min_lon,
            max_lat,
            max_lon,
            interest_key=highway_tag,
            way=True,
            node=False,
            relation=False,
        )

        osm_geojson_path = get_osm_data(
            query_str,
            "osm_streets_bbox_algo",
            geomtype="LineString",
            timeout=timeout,
            return_as_string=False,
        )
        if osm_geojson_path is None:
            raise QgsProcessingException(
                self.tr("Failed to download or parse OSM data (returned None).")
            )

        osm_data_layer_4326 = QgsVectorLayer(
            osm_geojson_path, "osm_streets_dl_bbox_4326_algo", "ogr"
        )
        if not osm_data_layer_4326.isValid():
            raise QgsProcessingException(
                self.tr("Downloaded OSM data did not form a valid vector layer.")
            )

        feedback.pushInfo(
            self.tr(f"OSM data fetched: {osm_data_layer_4326.featureCount()} ways.")
        )

        if osm_data_layer_4326.featureCount() == 0:
            feedback.pushWarning(
                self.tr(
                    "No OSM ways found within the specified BBOX. Output will be empty."
                )
            )
            # Prepare an empty sink and return
            crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_PROTOBLOCKS,
                context,
                QgsFields(),
                QgsWkbTypes.Polygon,
                crs_epsg4326,
            )
            if sink is None:
                raise QgsProcessingException(
                    self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS)
                )
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # --- Reproject Fetched Data to Local TM ---
        # For lgt_0 of local TM, use center of the input BBOX
        lgt_0_tm = (min_lon + max_lon) / 2.0
        feedback.pushInfo(
            self.tr(f"Reprojecting OSM data to local TM centered at lon {lgt_0_tm}...")
        )

        reproj_layer, local_tm_crs = reproject_layer_localTM(
            osm_data_layer_4326,  # Input is already clipped to BBOX by Overpass query
            outputpath=None,
            layername="osm_data_local_tm_bbox_algo",
            lgt_0=lgt_0_tm,
        )
        if not reproj_layer.isValid():
            raise QgsProcessingException(
                self.tr("Failed to reproject OSM data to local TM.")
            )

        feedback.pushInfo(
            self.tr(
                f"Data reprojected to local TM ({local_tm_crs.authid()}): {reproj_layer.featureCount()} ways."
            )
        )

        # --- Clean Street Network ---
        feedback.pushInfo(self.tr("Cleaning street network..."))
        filtered_streets_layer = QgsVectorLayer(
            "LineString", "filtered_streets_local_tm_bbox_algo", "memory"
        )
        filtered_streets_layer.setCrs(local_tm_crs)
        filtered_streets_dp = filtered_streets_layer.dataProvider()
        if reproj_layer.fields().count() > 0:
            filtered_streets_dp.addAttributes(reproj_layer.fields())
        else:
            filtered_streets_dp.addAttributes([QgsField("dummy_id", QVariant.Int)])
        filtered_streets_layer.updateFields()

        features_to_add_to_filtered = []
        highway_field_idx = reproj_layer.fields().lookupField(highway_tag)
        if highway_field_idx == -1:
            raise QgsProcessingException(
                self.tr(f"'{highway_tag}' not found in reprojected OSM data.")
            )

        for f_in in reproj_layer.getFeatures():
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
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_PROTOBLOCKS,
                context,
                QgsFields(),
                QgsWkbTypes.Polygon,
                QgsCoordinateReferenceSystem(CRS_LATLON_4326),
            )
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

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

        # --- Polygonize ---
        feedback.pushInfo(self.tr("Polygonizing street network..."))
        protoblocks_in_local_tm = polygonize_lines(
            filtered_streets_layer,
            outputlayer="memory:protoblocks_temp_bbox_algo",
            keepfields=False,
        )

        if not protoblocks_in_local_tm or not protoblocks_in_local_tm.isValid():
            raise QgsProcessingException(
                self.tr("Polygonization failed or returned an invalid layer.")
            )

        if (
            not protoblocks_in_local_tm.crs().isValid()
            or protoblocks_in_local_tm.crs().authid() != local_tm_crs.authid()
        ):
            feedback.pushInfo(
                f"Warning: Polygonized layer CRS ({protoblocks_in_local_tm.crs().authid()}) differs from expected local TM CRS ({local_tm_crs.authid()}). Forcing correct CRS."
            )
            protoblocks_in_local_tm.setCrs(local_tm_crs)

        feedback.pushInfo(
            self.tr(
                f"Polygonization created {protoblocks_in_local_tm.featureCount()} protoblocks in local TM. CRS: {protoblocks_in_local_tm.crs().description()} ({protoblocks_in_local_tm.crs().authid()})"
            )
        )

        # --- Re-clone to a new layer (Optional, but good for CRS robustness if issues persist) ---
        # For now, assume protoblocks_in_local_tm is fine after polygonize_lines's own CRS setting.
        # If not, re-cloning step from other algorithm can be inserted here.
        # protoblocks_layer_for_reprojection = protoblocks_in_local_tm (if not re-cloning)

        if protoblocks_in_local_tm.featureCount() == 0:
            feedback.pushWarning(
                self.tr("No protoblocks after polygonization. Output will be empty.")
            )
            # Fallthrough to create an empty sink with correct type and CRS (EPSG:4326)
            crs_epsg4326_final = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_PROTOBLOCKS,
                context,
                QgsFields(),
                QgsWkbTypes.Polygon,
                crs_epsg4326_final,
            )
            if sink is None:
                raise QgsProcessingException(
                    self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS)
                )
            return {self.OUTPUT_PROTOBLOCKS: dest_id}

        # --- Sidewalk Analysis (match full pipeline semantics) ---
        feedback.pushInfo(self.tr("Analyzing pre-existing sidewalks (footway=sidewalk) per protoblock..."))

        # Build a layer of existing sidewalks mapped as separate ways: highway=footway AND footway=sidewalk
        existing_sidewalk_feats = []
        hwy_idx = reproj_layer.fields().lookupField(highway_tag)
        footway_idx = reproj_layer.fields().lookupField("footway")
        if hwy_idx != -1 and footway_idx != -1:
            for f in reproj_layer.getFeatures():
                try:
                    if str(f.attribute(hwy_idx)).lower() == "footway" and str(f.attribute(footway_idx)).lower() == "sidewalk":
                        existing_sidewalk_feats.append(f)
                except Exception:
                    continue

        if existing_sidewalk_feats:
            existing_sw_layer = layer_from_featlist(
                existing_sidewalk_feats,
                "existing_sidewalks_local_tm",
                "LineString",
                CRS=local_tm_crs,
            )
            # Sum existing sidewalk length within each protoblock
            _ = create_incidence_field_layers_A_B(
                protoblocks_in_local_tm,
                existing_sw_layer,
                fieldname="inc_sidewalk_len",
                total_length_instead=True,
            )
        else:
            feedback.pushInfo(self.tr("No separate sidewalks (footway=sidewalk) detected in AOI."))
            # Add field with 0 length to simplify downstream
            _ = create_incidence_field_layers_A_B(
                protoblocks_in_local_tm,
                layer_from_featlist([], "empty_sidewalks", "LineString", CRS=local_tm_crs),
                fieldname="inc_sidewalk_len",
                total_length_instead=True,
            )

        # Prepare output protoblocks-with-sidewalk info layer
        output_fields = QgsFields()
        output_fields.append(QgsField("existing_sidewalks", QVariant.Bool))
        output_fields.append(QgsField("existing_sidewalks_length", QVariant.Double))
        protoblocks_with_sidewalks = QgsVectorLayer(
            "Polygon", "protoblocks_with_sidewalks_info", "memory"
        )
        protoblocks_with_sidewalks.setCrs(local_tm_crs)
        protoblocks_with_sidewalks_dp = protoblocks_with_sidewalks.dataProvider()
        protoblocks_with_sidewalks_dp.addAttributes(output_fields)
        protoblocks_with_sidewalks.updateFields()

        features_out = []
        for pb in protoblocks_in_local_tm.getFeatures():
            if feedback.isCanceled():
                return {}
            area = pb.geometry().area() if pb.hasGeometry() else 0.0
            try:
                inc_len = float(pb["inc_sidewalk_len"] or 0.0)
            except Exception:
                inc_len = 0.0
            ratio = 0.0
            if area > 0 and inc_len > 0:
                ratio = (((inc_len / 4.0) ** 2) / area) * 100.0
            has_existing = ratio > cutoff_percent_protoblock
            nf = QgsFeature(output_fields)
            nf.setGeometry(pb.geometry())
            nf.setAttributes([has_existing, inc_len])
            features_out.append(nf)

        if features_out:
            protoblocks_with_sidewalks_dp.addFeatures(features_out)
        feedback.pushInfo(self.tr("Sidewalk analysis complete."))

        # --- Final Reprojection to EPSG:4326 ---
        feedback.pushInfo(self.tr("Reprojecting final protoblocks to EPSG:4326..."))
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        reproject_params_final = {
            "INPUT": protoblocks_with_sidewalks,
            "TARGET_CRS": crs_epsg4326,
            "OUTPUT": "memory:protoblocks_final_epsg4326_bbox_algo",
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

        # Robustly obtain the output layer (can be instance or string)
        output_value = reproject_final_result.get("OUTPUT")
        output_layer_epsg4326 = None
        if isinstance(output_value, QgsVectorLayer):
            output_layer_epsg4326 = output_value
        elif output_value is not None:
            output_layer_epsg4326 = QgsProcessingUtils.mapLayerFromString(
                str(output_value), context
            )
        if output_layer_epsg4326:
            output_layer_epsg4326.setName("protoblocks_epsg4326_loaded")

        if not output_layer_epsg4326 or not output_layer_epsg4326.isValid():
            raise QgsProcessingException(
                self.tr(
                    "Failed to obtain a valid layer after final reprojection to EPSG:4326."
                )
            )

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
                    protoblocks_with_sidewalks.crs(), crs_epsg4326, context.transformContext()
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
                for f in protoblocks_with_sidewalks.getFeatures():
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

        # --- Prepare Sink and Output ---
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_PROTOBLOCKS,
            context,
            output_layer_epsg4326.fields(),
            QgsWkbTypes.Polygon,
            crs_epsg4326,
        )
        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT_PROTOBLOCKS)
            )

        if output_layer_epsg4326.featureCount() > 0:
            total_out_feats = output_layer_epsg4326.featureCount()
            for i, feat in enumerate(output_layer_epsg4326.getFeatures()):
                if feedback.isCanceled():
                    break
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                feedback.setProgress(int(90 + (i + 1) * 10.0 / total_out_feats))

        feedback.pushInfo(
            self.tr("Protoblock generation complete. Output (EPSG:4326) written.")
        )
        return {self.OUTPUT_PROTOBLOCKS: dest_id}

    def postProcessAlgorithm(self, context, feedback):
        return {}


from qgis import processing  # For processing.run

# Removed redundant QgsProcessingParameterExtent import from here as it's now at the top
