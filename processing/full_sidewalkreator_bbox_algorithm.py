# -*- coding: utf-8 -*-

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterExtent,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterDefinition,
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsFeatureSink,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsField,
    QgsFields,
    QgsFeatureRequest,
    QgsProcessingUtils,
    QgsProcessingException,
    QgsMessageLog,
    QgsWkbTypes,
    Qgis,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QCoreApplication, QVariant
import qgis.core as qcore

# Utility functions from the plugin
from ..osm_fetch import (
    get_osm_data,
    osm_query_string_by_bbox,
)  # for fetching OSM data
from .. import parameters  # For default values and constants
from .. import generic_functions
from ..generic_functions import (
    polygonize_lines,
    reproject_layer_localTM,
    reproject_layer,
    # log_plugin_message,
    cliplayer_v2,
    clean_street_network_data,
    assign_street_widths,
    # create_memory_layer_from_features,
)
from ..parameters import CRS_LATLON_4326
from .sidewalk_generation_logic import (
    generate_sidewalk_geometries_and_zones,
)  # Core logic

import os

try:
    import processing  # For native algorithms
except ImportError as e:
    QgsMessageLog.logMessage(
        f"Failed to import processing module: {e}",
        "SidewalKreator",
        Qgis.Critical,
    )
    raise


class FullSidewalkreatorBboxAlgorithm(QgsProcessingAlgorithm):
    """
    This algorithm generates a full sidewalk network based on OSM data within a specified bounding box.
    It fetches OSM road and building data, processes it, and then generates sidewalk lines.
    """

    INPUT_EXTENT = "INPUT_EXTENT"
    TIMEOUT = "TIMEOUT"
    GET_BUILDING_DATA = "GET_BUILDING_DATA"
    DEFAULT_WIDTH = "DEFAULT_WIDTH"
    MIN_WIDTH = "MIN_WIDTH"
    MAX_WIDTH = "MAX_WIDTH"
    STREET_CLASSES = "STREET_CLASSES"

    SAVE_PROTOBLOCKS_DEBUG = "SAVE_PROTOBLOCKS_DEBUG"
    SAVE_EXCLUSION_ZONES_DEBUG = "SAVE_EXCLUSION_ZONES_DEBUG"
    SAVE_SURE_ZONES_DEBUG = "SAVE_SURE_ZONES_DEBUG"
    SAVE_STREETS_WIDTH_ADJUSTED_DEBUG = "SAVE_STREETS_WIDTH_ADJUSTED_DEBUG"

    OUTPUT_SIDEWALKS = "OUTPUT_SIDEWALKS"
    OUTPUT_PROTOBLOCKS_DEBUG = "OUTPUT_PROTOBLOCKS_DEBUG"
    OUTPUT_EXCLUSION_ZONES_DEBUG = "OUTPUT_EXCLUSION_ZONES_DEBUG"
    OUTPUT_SURE_ZONES_DEBUG = "OUTPUT_SURE_ZONES_DEBUG"
    OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG = "OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(
                self.INPUT_EXTENT,
                self.tr("Area of Interest (Bounding Box in EPSG:4326)"),
                defaultValue=None,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr("OSM Data Fetch Timeout (seconds)"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=parameters.DEFAULT_TIMEOUT_SECONDS,
                minValue=10,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.GET_BUILDING_DATA,
                self.tr("Fetch OSM Building Data (for better exclusion zones)"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_WIDTH,
                self.tr("Default Sidewalk Width (meters)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=parameters.fallback_default_width,
                minValue=0.1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_WIDTH,
                self.tr("Minimum Sidewalk Width (meters)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=parameters.fallback_default_width,
                minValue=0.1,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAX_WIDTH,
                self.tr("Maximum Sidewalk Width (meters)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=parameters.MAX_SIDEWALK_WIDTH_METERS,
                minValue=0.1,
            )
        )

        # Street classes to process (multi-enum)
        # Using a fixed list for now as QgsProcessingParameterEnum seems to have issues with dynamic lists from parameters.STREET_CLASSES_OPTIONS
        street_options = [
            "motorway",
            "motorway_link",
            "trunk",
            "trunk_link",
            "primary",
            "primary_link",
            "secondary",
            "secondary_link",
            "tertiary",
            "tertiary_link",
            "residential",
            "living_street",
            "service",
            "unclassified",
            "road",
            "track",
            "path",
            "cycleway",
            "footway",
            "pedestrian",
        ]
        self.addParameter(
            QgsProcessingParameterEnum(
                self.STREET_CLASSES,
                self.tr("Street Classes to Process"),
                options=street_options,
                allowMultiple=True,
                defaultValue=list(range(len(street_options))),
            )
        )

        # Debug outputs (optional)
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_PROTOBLOCKS_DEBUG,
                self.tr("Save Protoblocks (Debug Output in EPSG:4326)"),
                defaultValue=False,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_EXCLUSION_ZONES_DEBUG,
                self.tr("Save Exclusion Zones (Debug Output in Local TM)"),
                defaultValue=False,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_SURE_ZONES_DEBUG,
                self.tr("Save Sure Zones (Debug Output in Local TM)"),
                defaultValue=False,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SAVE_STREETS_WIDTH_ADJUSTED_DEBUG,
                self.tr("Save Width-Adjusted Streets (Debug Output in Local TM)"),
                defaultValue=False,
                optional=True,
            )
        )

        # Main output
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_SIDEWALKS, self.tr("Generated Sidewalks (EPSG:4326)")
            )
        )

        # Optional debug outputs
        param = QgsProcessingParameterFeatureSink(
            self.OUTPUT_PROTOBLOCKS_DEBUG,
            self.tr("Protoblocks (Debug)"),
            QgsProcessing.TypeVectorPolygon,
            optional=True,
        )
        param.setFlags(
            param.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )  # Mark as advanced
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
            self.OUTPUT_EXCLUSION_ZONES_DEBUG,
            self.tr("Exclusion Zones (Debug)"),
            QgsProcessing.TypeVectorPolygon,
            optional=True,
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
            self.OUTPUT_SURE_ZONES_DEBUG,
            self.tr("Sure Zones (Debug)"),
            QgsProcessing.TypeVectorPolygon,
            optional=True,
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterFeatureSink(
            self.OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG,
            self.tr("Width-Adjusted Streets (Debug)"),
            QgsProcessing.TypeVectorLine,  # Or polygon if they are buffered representations
            optional=True,
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

    def processAlgorithm(self, parameters_alg, context, feedback):
        # Get parameters
        input_extent_rect = self.parameterAsExtent(
            parameters_alg, self.INPUT_EXTENT, context
        )  # QgsRectangle
        extent_crs = self.parameterAsExtentCrs(
            parameters_alg, self.INPUT_EXTENT, context
        )
        # Fallback: parse string extents like "minx,miny,maxx,maxy [EPSG:XXXX]"
        if not input_extent_rect or input_extent_rect.isEmpty():
            raw = parameters_alg.get(self.INPUT_EXTENT)
            feedback.pushInfo(f"DEBUG: Parsing extent string: '{raw}'")
            if isinstance(raw, str):
                try:
                    spec, _, crs_part = raw.partition("[")
                    nums = [float(x.strip()) for x in spec.split(",")[:4]]
                    feedback.pushInfo(f"DEBUG: Parsed numbers: {nums}")
                    from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem

                    if len(nums) == 4:
                        # Create test rectangles for both interpretations
                        rect1 = QgsRectangle(
                            nums[0], nums[1], nums[2], nums[3]
                        )  # minX,minY,maxX,maxY
                        rect2 = QgsRectangle(
                            nums[0], nums[2], nums[1], nums[3]
                        )  # minX,maxX,minY,maxY reordered

                        area1 = rect1.width() * rect1.height()
                        area2 = rect2.width() * rect2.height()

                        feedback.pushInfo(
                            f"DEBUG: Interpretation 1 (minX,minY,maxX,maxY): {rect1.width():.1f}m × {rect1.height():.1f}m (area: {area1:.0f})"
                        )
                        feedback.pushInfo(
                            f"DEBUG: Interpretation 2 (minX,maxX,minY,maxY): {rect2.width():.1f}m × {rect2.height():.1f}m (area: {area2:.0f})"
                        )

                        # Choose the interpretation that results in a smaller, more reasonable area
                        # For neighborhood processing, we expect areas less than 100 km²
                        if (
                            area2 < area1 and area2 < 100_000_000
                        ):  # 100 km² = 100,000,000 m²
                            feedback.pushInfo(
                                "DEBUG: Using interpretation 2 (reordered coordinates) - smaller area"
                            )
                            input_extent_rect = rect2
                        elif area1 < 100_000_000:
                            feedback.pushInfo(
                                "DEBUG: Using interpretation 1 (original order) - reasonable area"
                            )
                            input_extent_rect = rect1
                        else:
                            feedback.pushInfo(
                                "DEBUG: Both interpretations result in very large areas, using smaller one"
                            )
                            input_extent_rect = rect2 if area2 < area1 else rect1

                        feedback.pushInfo(
                            f"DEBUG: Final rectangle - xMin:{input_extent_rect.xMinimum()}, yMin:{input_extent_rect.yMinimum()}, xMax:{input_extent_rect.xMaximum()}, yMax:{input_extent_rect.yMaximum()}"
                        )
                        if not crs_part:
                            extent_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                        else:
                            code = crs_part.strip().rstrip("]")
                            extent_crs = QgsCoordinateReferenceSystem(code)
                except Exception:
                    pass
        timeout = self.parameterAsInt(parameters_alg, self.TIMEOUT, context)
        get_building_data = self.parameterAsBoolean(
            parameters_alg, self.GET_BUILDING_DATA, context
        )
        default_width = self.parameterAsDouble(
            parameters_alg, self.DEFAULT_WIDTH, context
        )
        min_width = self.parameterAsDouble(parameters_alg, self.MIN_WIDTH, context)
        max_width = self.parameterAsDouble(parameters_alg, self.MAX_WIDTH, context)

        # Street classes (indices from QgsProcessingParameterEnum)
        street_class_indices = self.parameterAsEnums(
            parameters_alg, self.STREET_CLASSES, context
        )
        # Convert indices back to string values based on the options defined in initAlgorithm
        street_options_list = self.parameterDefinition(self.STREET_CLASSES).options()
        street_classes_to_process = [
            street_options_list[i] for i in street_class_indices
        ]

        save_protoblocks_debug = self.parameterAsBoolean(
            parameters_alg, self.SAVE_PROTOBLOCKS_DEBUG, context
        )
        save_exclusion_zones_debug = self.parameterAsBoolean(
            parameters_alg, self.SAVE_EXCLUSION_ZONES_DEBUG, context
        )
        save_sure_zones_debug = self.parameterAsBoolean(
            parameters_alg, self.SAVE_SURE_ZONES_DEBUG, context
        )
        save_streets_width_adjusted_debug = self.parameterAsBoolean(
            parameters_alg, self.SAVE_STREETS_WIDTH_ADJUSTED_DEBUG, context
        )

        results = {}
        # --- 1. Convert input extent to a polygon layer ---
        if not input_extent_rect or input_extent_rect.isEmpty():
            feedback.reportError(self.tr("Invalid input extent."), True)
            return results

        feedback.pushInfo(
            self.tr(
                f"Input extent: {input_extent_rect.asWktPolygon()} (CRS: {extent_crs.authid()})"
            )
        )

        crs_4326 = qcore.QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent_crs != crs_4326:
            feedback.pushInfo(
                self.tr(
                    f"Transforming input extent from {extent_crs.authid()} to EPSG:4326..."
                )
            )
            transform = QgsCoordinateTransform(
                extent_crs, crs_4326, context.transformContext()
            )
            try:
                extent_4326 = transform.transform(input_extent_rect)
            except Exception:
                msg = self.tr(
                    "Failed to transform extent to EPSG:4326 or transformed extent is empty."
                )
                feedback.reportError(msg, True)
                raise QgsProcessingException(msg)
        else:
            extent_4326 = input_extent_rect

        extent_within_latlon = (
            -180 <= extent_4326.xMinimum() <= 180
            and -180 <= extent_4326.xMaximum() <= 180
            and -90 <= extent_4326.yMinimum() <= 90
            and -90 <= extent_4326.yMaximum() <= 90
        )
        if not extent_within_latlon:
            msg = self.tr(
                "Extent coordinates appear outside valid latitude/longitude bounds."
                " Please supply coordinates in EPSG:4326 or specify the CRS."
            )
            feedback.reportError(msg, True)
            raise QgsProcessingException(msg)

        # --- The rest of the logic is largely similar to FullSidewalkreatorPolygonAlgorithm ---
        # Use input_polygon_layer_for_processing as the 'actual_input_layer'

        # --- 2. Get Input Polygon Details and Define Local TM CRS ---
        # extent_4326 is now ensured to be in EPSG:4326

        # Recreate the in-memory polygon layer using the transformed extent (always in EPSG:4326)
        input_polygon_geom_4326 = QgsGeometry.fromRect(extent_4326)
        if not input_polygon_geom_4326 or input_polygon_geom_4326.isEmpty():
            feedback.reportError(
                self.tr("Failed to create polygon geometry from transformed extent."),
                True,
            )
            return results

        feedback.pushInfo(
            f"DEBUG: Created polygon geometry from extent: {input_polygon_geom_4326.asWkt()[:200]}..."
        )

        vl = QgsVectorLayer("Polygon?crs=epsg:4326", "input_extent_polygon", "memory")
        pr = vl.dataProvider()
        feat = QgsFeature()
        feat.setGeometry(input_polygon_geom_4326)
        pr.addFeatures([feat])
        vl.updateExtents()

        feedback.pushInfo(
            f"DEBUG: Memory layer extent after adding feature: {vl.extent().toString()}"
        )
        feedback.pushInfo(f"DEBUG: Memory layer CRS: {vl.crs().authid()}")
        feedback.pushInfo(f"DEBUG: Memory layer feature count: {vl.featureCount()}")

        if vl.featureCount() == 0:
            feedback.reportError(
                self.tr(
                    "Failed to create in-memory polygon layer from transformed extent."
                ),
                True,
            )
            return results

        input_polygon_layer_for_processing = vl
        feedback.pushInfo(
            self.tr(
                f"Created temporary polygon layer from extent with {input_polygon_layer_for_processing.featureCount()} feature."
            )
        )

        centroid_lon = extent_4326.center().x()
        centroid_lat = extent_4326.center().y()

        # Reproject the memory input polygon layer to local TM for internal processing
        # The reproject_layer_localTM function handles the creation of the CRS internally
        feedback.pushInfo(self.tr("Reprojecting input extent polygon to local TM..."))

        # Calculate UTM zone as primary approach (more reliable than custom TM)
        utm_zone = int((centroid_lon + 180) / 6) + 1
        hemisphere = "north" if centroid_lat >= 0 else "south"

        if hemisphere == "south":
            utm_epsg = 32700 + utm_zone  # UTM South zones
        else:
            utm_epsg = 32600 + utm_zone  # UTM North zones

        feedback.pushInfo(
            f"Using UTM Zone {utm_zone}{hemisphere[0].upper()} (EPSG:{utm_epsg}) for projection."
        )
        feedback.pushInfo(
            f"Centroid coordinates: {centroid_lon:.6f}, {centroid_lat:.6f}"
        )

        # Create UTM CRS
        local_tm_crs = qcore.QgsCoordinateReferenceSystem(f"EPSG:{utm_epsg}")

        if not local_tm_crs.isValid():
            feedback.reportError(
                self.tr(f"Could not create UTM CRS EPSG:{utm_epsg}"),
                True,
            )
            return results

        # Reproject using standard QGIS reprojection to UTM
        input_poly_local_tm_layer = reproject_layer(
            input_polygon_layer_for_processing,
            destination_crs=f"EPSG:{utm_epsg}",
            output_mode="memory:input_poly_utm",
        )

        if not input_poly_local_tm_layer:
            feedback.reportError(
                self.tr("Failed to reproject input polygon to UTM"),
                True,
            )
            return results
        feedback.pushInfo(
            self.tr(
                f"Successfully created UTM CRS: {local_tm_crs.authid()} - {local_tm_crs.description()}"
            )
        )
        if (
            not input_poly_local_tm_layer
            or input_poly_local_tm_layer.featureCount() == 0
        ):
            feedback.reportError(
                self.tr("Failed to reproject input extent polygon to local TM."), True
            )
            return results

        # Get the single polygon feature from the reprojected layer
        input_poly_local_tm_feat = next(input_poly_local_tm_layer.getFeatures(), None)
        if not input_poly_local_tm_feat:
            feedback.reportError(
                self.tr("No feature found in reprojected input extent polygon."), True
            )
            return results
        input_poly_local_tm_geom = input_poly_local_tm_feat.geometry()

        # --- 3. Fetch OSM Road Data ---
        feedback.pushInfo(self.tr("Fetching OSM road data..."))

        # Get bbox coordinates from extent
        # extent_4326 is a QgsRectangle with xMin,yMin,xMax,yMax
        x_min = extent_4326.xMinimum()  # longitude (west)
        y_min = extent_4326.yMinimum()  # latitude (south)
        x_max = extent_4326.xMaximum()  # longitude (east)
        y_max = extent_4326.yMaximum()  # latitude (north)

        # For geographic coordinates: x=longitude, y=latitude
        min_lon = x_min
        min_lat = y_min
        max_lon = x_max
        max_lat = y_max

        # Debug: Print the actual coordinate values
        feedback.pushInfo(
            f"DEBUG: QgsRectangle bounds: xMin={x_min}, yMin={y_min}, xMax={x_max}, yMax={y_max}"
        )
        feedback.pushInfo(
            f"DEBUG: Geographic coords: min_lon={min_lon}, min_lat={min_lat}, max_lon={max_lon}, max_lat={max_lat}"
        )
        feedback.pushInfo(
            f"DEBUG: Expected Overpass bbox (south,west,north,east): ({min_lat},{min_lon},{max_lat},{max_lon})"
        )

        # Build query string for roads
        # Build using positional args to avoid any name-mapping issues
        # osm_query_string_by_bbox expects (min_lat, min_lon, max_lat, max_lon)
        road_query_string = osm_query_string_by_bbox(
            min_lat,  # lat min (south)
            min_lon,  # lon min (west)
            max_lat,  # lat max (north)
            max_lon,  # lon max (east)
            interest_key="highway",
            way=True,
            node=False,
            relation=False,
        )
        feedback.pushInfo(f"Overpass API query for roads: {road_query_string}")

        # Use the original EPSG:4326 extent for fetching
        osm_road_data_filepath = get_osm_data(
            querystring=road_query_string,
            tempfilesname="osm_roads_raw_4326_bbox",
            geomtype="LineString",
            timeout=timeout,
        )
        osm_road_data_layer_4326 = QgsVectorLayer(
            osm_road_data_filepath, "osm_roads", "ogr"
        )
        if (
            osm_road_data_layer_4326 is None
            or not osm_road_data_layer_4326.isValid()
            or osm_road_data_layer_4326.featureCount() == 0
        ):
            feedback.reportError(
                self.tr(
                    "No OSM road data found or error during fetch for the given extent and street classes."
                ),
                True,
            )
            return results
        feedback.pushInfo(
            self.tr(
                f"Fetched {osm_road_data_layer_4326.featureCount()} raw road features."
            )
        )

        # --- 4. Clean and Reproject Road Data ---
        feedback.pushInfo(self.tr("Cleaning and reprojecting road data..."))
        # Clean (clip to precise input polygon in 4326, then reproject)
        cleaned_roads_local_tm = clean_street_network_data(
            osm_road_data_layer_4326,  # This is in 4326
            input_polygon_layer_for_processing,  # This is the memory layer from extent, in 4326
            local_tm_crs,
            "cleaned_roads_local_tm_bbox",
            feedback,
            context,
        )
        if not cleaned_roads_local_tm or cleaned_roads_local_tm.featureCount() == 0:
            feedback.reportError(
                self.tr("No road features after cleaning, or cleaning failed."), True
            )
            return results
        feedback.pushInfo(
            self.tr(
                f"Cleaned road network in local TM: {cleaned_roads_local_tm.featureCount()} features."
            )
        )

        # Assign default widths to streets that are missing the 'width' attribute
        feedback.pushInfo(self.tr("Assigning default street widths..."))
        streets_with_width = assign_street_widths(
            cleaned_roads_local_tm, "streets_with_width_bbox", feedback
        )
        if not streets_with_width or streets_with_width.featureCount() == 0:
            feedback.reportError(
                self.tr(
                    "No road features after assigning widths, or assignment failed."
                ),
                True,
            )
            return results

        # Optional: filter by selected street classes to reduce workload
        try:
            street_indices = self.parameterAsEnums(
                parameters_alg, self.STREET_CLASSES, context
            )
            street_options_list = self.parameterDefinition(
                self.STREET_CLASSES
            ).options()
            allowed_classes = set(street_options_list[i] for i in street_indices)
        except Exception:
            allowed_classes = set()
        if allowed_classes:
            highway_idx = streets_with_width.fields().lookupField(
                parameters.highway_tag
            )
            filtered = QgsVectorLayer(
                f"LineString?crs={local_tm_crs.authid()}",
                "filtered_streets_bbox",
                "memory",
            )
            fdp = filtered.dataProvider()
            fdp.addAttributes(streets_with_width.fields())
            filtered.updateFields()
            feats = []
            for f in streets_with_width.getFeatures():
                hval = f.attribute(highway_idx) if highway_idx != -1 else None
                if str(hval).lower() in allowed_classes:
                    feats.append(QgsFeature(f))
            if feats:
                fdp.addFeatures(feats)
                filtered.updateExtents()
                feedback.pushInfo(
                    self.tr(
                        f"Filtered streets by classes: {filtered.featureCount()} remain."
                    )
                )
                streets_with_width = filtered

        # --- 5. Generate Protoblocks (in local TM first, then reproject if saved) ---
        feedback.pushInfo(self.tr("Generating protoblocks..."))
        protoblocks_layer_local_tm = polygonize_lines(
            streets_with_width,
            outputlayer="memory:protoblocks_local_tm_bbox",
        )
        if (
            not protoblocks_layer_local_tm
            or protoblocks_layer_local_tm.featureCount() == 0
        ):
            feedback.pushWarning(
                self.tr(
                    "No protoblocks generated. This might be expected for the given road network (e.g., no enclosed areas)."
                )
            )
            # Allow to continue if sidewalk generation can proceed without protoblocks (e.g. if it mainly uses road lines)
            # However, if protoblocks are essential for subsequent steps, this should be an error.
            # For now, let's assume it can continue and subsequent steps handle empty protoblocks.
        else:
            feedback.pushInfo(
                self.tr(
                    f"Generated {protoblocks_layer_local_tm.featureCount()} protoblocks in local TM."
                )
            )

        if save_protoblocks_debug:
            feedback.pushInfo(
                self.tr("Reprojecting protoblocks to EPSG:4326 for debug output...")
            )
            protoblocks_layer_4326_debug = reproject_layer(
                protoblocks_layer_local_tm,
                destination_crs="EPSG:4326",
                output_mode="memory:protoblocks_4326_debug_bbox",
            )
            if (
                protoblocks_layer_4326_debug
                and protoblocks_layer_4326_debug.isValid()
                and protoblocks_layer_4326_debug.featureCount() > 0
            ):
                (sink_protoblocks_debug, dest_id_protoblocks_debug) = (
                    self.parameterAsSink(
                        parameters_alg,
                        self.OUTPUT_PROTOBLOCKS_DEBUG,
                        context,
                        protoblocks_layer_4326_debug.fields(),
                        protoblocks_layer_4326_debug.wkbType(),
                        qcore.QgsCoordinateReferenceSystem(CRS_LATLON_4326),
                    )
                )
                if sink_protoblocks_debug:
                    for feature in protoblocks_layer_4326_debug.getFeatures():
                        sink_protoblocks_debug.addFeature(
                            feature, QgsFeatureSink.FastInsert
                        )
                    results[self.OUTPUT_PROTOBLOCKS_DEBUG] = dest_id_protoblocks_debug
                else:
                    feedback.pushWarning(
                        self.tr("Failed to create sink for debug protoblocks layer.")
                    )
            else:
                feedback.pushWarning(
                    self.tr(
                        "Failed to reproject protoblocks to EPSG:4326 for debug output."
                    )
                )

        # --- 6. Fetch and Process Building Data (if requested) ---
        reproj_buildings_layer_local_tm = None
        if get_building_data:
            feedback.pushInfo(self.tr("Fetching OSM building data..."))

            # Build query string for buildings
            building_query_string = osm_query_string_by_bbox(
                min_lat,  # lat min
                min_lon,  # lon min
                max_lat,  # lat max
                max_lon,  # lon max
                interest_key="building",
                way=True,
                relation=True,  # For multipolygons
                interest_value=None,  # Fetch all building types
            )
            feedback.pushInfo(
                f"Overpass API query for buildings: {building_query_string}"
            )

            osm_buildings_filepath = get_osm_data(
                querystring=building_query_string,
                tempfilesname="osm_buildings_raw_4326_bbox",
                geomtype="Polygon",  # Expected geometry type
                timeout=timeout,
            )
            osm_buildings_layer_4326 = QgsVectorLayer(
                osm_buildings_filepath, "osm_buildings", "ogr"
            )

            if (
                osm_buildings_layer_4326
                and osm_buildings_layer_4326.isValid()
                and osm_buildings_layer_4326.featureCount() > 0
            ):
                feedback.pushInfo(
                    self.tr(
                        f"Fetched {osm_buildings_layer_4326.featureCount()} raw building features."
                    )
                )
                feedback.pushInfo(
                    self.tr("Clipping and reprojecting building data to local TM...")
                )

                # Clip buildings to the precise input polygon (in 4326) first
                clipped_buildings_4326 = cliplayer_v2(
                    osm_buildings_layer_4326,
                    input_polygon_layer_for_processing,  # Use the 4326 layer for clipping
                    "memory:clipped_bldgs_4326_bbox",
                )

                if (
                    clipped_buildings_4326
                    and clipped_buildings_4326.isValid()
                    and clipped_buildings_4326.featureCount() > 0
                ):
                    reproj_buildings_layer_local_tm = reproject_layer(
                        clipped_buildings_4326,
                        destination_crs=local_tm_crs.authid(),
                        output_mode="memory:bldgs_utm",
                    )
                    if (
                        not reproj_buildings_layer_local_tm
                        or not reproj_buildings_layer_local_tm.isValid()
                    ):
                        feedback.pushWarning(
                            self.tr(
                                "Failed to reproject building data, proceeding without it for overlap checks."
                            )
                        )
                        reproj_buildings_layer_local_tm = None
                    else:
                        # Ensure CRS is correctly set
                        reproj_buildings_layer_local_tm.setCrs(local_tm_crs)

                        feedback.pushInfo(
                            self.tr(
                                f"Buildings reprojected to local TM: {reproj_buildings_layer_local_tm.featureCount()} features."
                            )
                        )
                else:
                    feedback.pushInfo(
                        self.tr(
                            "No buildings after clipping to input extent, or clipping failed."
                        )
                    )
                    reproj_buildings_layer_local_tm = None
            else:
                feedback.pushInfo(self.tr("No building data found or fetch error."))
                reproj_buildings_layer_local_tm = None
        else:
            feedback.pushInfo(self.tr("Skipping building data fetch as per parameter."))

        # --- 7. Generate Sidewalk Geometries ---
        feedback.pushInfo(self.tr("Generating sidewalk geometries..."))

        # Prepare parameters for sidewalk generation logic
        sidewalk_params = {
            "default_width_m": default_width,
            "min_width_m": min_width,
            "max_width_m": max_width,
            "d_to_add_to_each_side": getattr(
                parameters, "d_to_add_to_each_side", 1.0
            ),  # Default 1m
            "curve_radius": getattr(
                parameters, "default_curve_radius", 3.0
            ),  # Default 3m
            "min_dist_to_building": getattr(
                parameters, "min_d_to_building", 1.0
            ),  # Default 1m
            "min_area_perimeter_ratio": getattr(
                parameters, "min_area_perimeter_ratio", 0.0008
            ),  # Default ratio
            # 'street_classes_to_draw': street_classes_to_process, # This is handled by input road filtering
            "debug_output_path": None,  # Not saving intermediate files from here for now
            "save_debug_layers": save_exclusion_zones_debug
            or save_sure_zones_debug
            or save_streets_width_adjusted_debug,
        }

        # Call the core logic function
        # Ensure cleaned_roads_local_tm and reproj_buildings_layer_local_tm are valid layers
        # input_poly_local_tm_geom is the geometry of the processing area in local TM

        generated_outputs = generate_sidewalk_geometries_and_zones(
            streets_with_width,
            processing_aoi_geom_local_tm=input_poly_local_tm_geom,  # geometry of the reprojected input extent
            building_footprints_layer_local_tm=reproj_buildings_layer_local_tm,
            protoblocks_layer_local_tm=protoblocks_layer_local_tm,  # Can be None or empty
            parameters=sidewalk_params,
            feedback=feedback,
            context=context,
            local_tm_crs=local_tm_crs,
        )

        sidewalk_lines_layer_local_tm = generated_outputs.get("sidewalk_lines")
        exclusion_zones_layer_local_tm = generated_outputs.get("exclusion_zones")
        sure_zones_layer_local_tm = generated_outputs.get("sure_zones")
        width_adjusted_streets_layer_local_tm = generated_outputs.get(
            "width_adjusted_streets"
        )

        if (
            not sidewalk_lines_layer_local_tm
            or sidewalk_lines_layer_local_tm.featureCount() == 0
        ):
            feedback.pushWarning(self.tr("No sidewalk lines were generated."))
            # Create an empty output layer so the user can see that the algorithm ran but produced no results
            empty_layer = QgsVectorLayer(
                f"LineString?crs=epsg:4326", "Empty Sidewalks", "memory"
            )
            (sink_empty, dest_id_empty) = self.parameterAsSink(
                parameters_alg,
                self.OUTPUT_SIDEWALKS,
                context,
                QgsFields(),  # Empty fields
                QgsWkbTypes.LineString,
                qcore.QgsCoordinateReferenceSystem(CRS_LATLON_4326),
            )
            if sink_empty:
                results[self.OUTPUT_SIDEWALKS] = dest_id_empty
        else:
            feedback.pushInfo(
                self.tr(
                    f"Generated {sidewalk_lines_layer_local_tm.featureCount()} sidewalk lines in local TM."
                )
            )

            # --- 8. Reproject Sidewalks to EPSG:4326 and Save Output ---
            feedback.pushInfo(
                self.tr("Reprojecting final sidewalk lines to EPSG:4326...")
            )

            # Debug: Check geometry validity before reprojection
            valid_geoms = 0
            invalid_geoms = 0
            for feat in sidewalk_lines_layer_local_tm.getFeatures():
                if feat.geometry().isGeosValid():
                    valid_geoms += 1
                else:
                    invalid_geoms += 1
            feedback.pushInfo(
                f"Geometry validation: {valid_geoms} valid, {invalid_geoms} invalid"
            )

            # Debug: Check bounds of local TM geometries
            extent = sidewalk_lines_layer_local_tm.extent()
            feedback.pushInfo(
                f"Local TM layer extent: {extent.xMinimum():.2f}, {extent.yMinimum():.2f} to {extent.xMaximum():.2f}, {extent.yMaximum():.2f}"
            )

            # Debug: Check CRS before reprojection
            source_crs = sidewalk_lines_layer_local_tm.crs()
            feedback.pushInfo(
                f"Source CRS: {source_crs.authid()} - {source_crs.description()}"
            )
            feedback.pushInfo(f"Source CRS is valid: {source_crs.isValid()}")

            # Test manual coordinate transformation
            dest_crs_4326 = qcore.QgsCoordinateReferenceSystem("EPSG:4326")
            transform = qcore.QgsCoordinateTransform(
                source_crs, dest_crs_4326, context.project()
            )

            # Sample a point from local TM and transform it manually
            for i, feat in enumerate(sidewalk_lines_layer_local_tm.getFeatures()):
                if i >= 1:  # Just test first feature
                    break
                geom = feat.geometry()
                if geom.isGeosValid():
                    # Get a point from the geometry
                    bbox = geom.boundingBox()
                    center_point = qcore.QgsPointXY(bbox.center())
                    feedback.pushInfo(
                        f"Original center point (Local TM): {center_point.x():.2f}, {center_point.y():.2f}"
                    )

                    # Transform manually
                    try:
                        transformed_point = transform.transform(center_point)
                        feedback.pushInfo(
                            f"Manually transformed point (4326): {transformed_point.x():.6f}, {transformed_point.y():.6f}"
                        )
                    except Exception as e:
                        feedback.pushWarning(f"Manual transformation failed: {e}")

            sidewalks_layer_4326 = reproject_layer(
                sidewalk_lines_layer_local_tm,
                destination_crs="EPSG:4326",
                output_mode="memory:sidewalks_final_4326_bbox",
            )

            # Check if reprojection worked correctly by examining coordinates
            reprojection_failed = False
            if sidewalks_layer_4326:
                extent_4326 = sidewalks_layer_4326.extent()
                # If coordinates are still in the range of the Local TM (hundreds of meters), reprojection failed
                if (
                    abs(extent_4326.xMinimum()) > 180
                    or abs(extent_4326.xMaximum()) > 180
                    or abs(extent_4326.yMinimum()) > 90
                    or abs(extent_4326.yMaximum()) > 90
                ):
                    feedback.pushWarning(
                        "Reprojection failed - coordinates are outside valid lat/lon range!"
                    )
                    reprojection_failed = True
                elif (
                    abs(extent_4326.xMinimum()) < 1 and abs(extent_4326.yMinimum()) < 1
                ):
                    # Coordinates are very small, likely still in meters
                    feedback.pushWarning(
                        "Reprojection may have failed - coordinates seem to still be in meters!"
                    )
                    reprojection_failed = True

            if reprojection_failed:
                feedback.pushInfo("Attempting manual coordinate transformation...")
                # Create a new layer with manually transformed coordinates
                dest_crs_4326 = qcore.QgsCoordinateReferenceSystem("EPSG:4326")
                transform = qcore.QgsCoordinateTransform(
                    source_crs, dest_crs_4326, context.project()
                )

                # Create a new memory layer
                sidewalks_layer_4326 = QgsVectorLayer(
                    f"LineString?crs=EPSG:4326",
                    "manually_reprojected_sidewalks",
                    "memory",
                )
                dp = sidewalks_layer_4326.dataProvider()
                dp.addAttributes(sidewalk_lines_layer_local_tm.fields())
                sidewalks_layer_4326.updateFields()

                # Transform features manually
                transformed_features = []
                for feat in sidewalk_lines_layer_local_tm.getFeatures():
                    new_feat = QgsFeature(sidewalks_layer_4326.fields())
                    new_feat.setAttributes(feat.attributes())

                    geom = feat.geometry()
                    if geom.isGeosValid():
                        # Transform the geometry
                        geom.transform(transform)
                        new_feat.setGeometry(geom)
                        transformed_features.append(new_feat)

                dp.addFeatures(transformed_features)
                sidewalks_layer_4326.updateExtents()
                feedback.pushInfo(
                    f"Manual transformation completed: {len(transformed_features)} features"
                )

            # Debug: Check reprojection results
            if sidewalks_layer_4326:
                dest_crs = sidewalks_layer_4326.crs()
                feedback.pushInfo(
                    f"Destination CRS: {dest_crs.authid()} - {dest_crs.description()}"
                )
                extent_4326 = sidewalks_layer_4326.extent()
                feedback.pushInfo(
                    f"EPSG:4326 layer extent: {extent_4326.xMinimum():.6f}, {extent_4326.yMinimum():.6f} to {extent_4326.xMaximum():.6f}, {extent_4326.yMaximum():.6f}"
                )

                # Sample a few coordinates to verify actual transformation
                sample_count = min(3, sidewalks_layer_4326.featureCount())
                for i, feat in enumerate(sidewalks_layer_4326.getFeatures()):
                    if i >= sample_count:
                        break
                    geom = feat.geometry()
                    if geom.isGeosValid():
                        bbox = geom.boundingBox()
                        feedback.pushInfo(
                            f"Sample feature {i+1} bbox: {bbox.xMinimum():.6f}, {bbox.yMinimum():.6f} to {bbox.xMaximum():.6f}, {bbox.yMaximum():.6f}"
                        )
            else:
                feedback.pushWarning(
                    "Reprojection failed - sidewalks_layer_4326 is None!"
                )
            if (
                sidewalks_layer_4326
                and sidewalks_layer_4326.isValid()
                and sidewalks_layer_4326.featureCount() > 0
            ):
                (sink_sidewalks, dest_id_sidewalks) = self.parameterAsSink(
                    parameters_alg,
                    self.OUTPUT_SIDEWALKS,
                    context,
                    sidewalks_layer_4326.fields(),
                    sidewalks_layer_4326.wkbType(),
                    qcore.QgsCoordinateReferenceSystem(CRS_LATLON_4326),
                )
                if sink_sidewalks:
                    for feature in sidewalks_layer_4326.getFeatures():
                        sink_sidewalks.addFeature(feature, QgsFeatureSink.FastInsert)
                    # Return an actual layer object for tests instead of an id string
                    # Map sink id to a layer object if possible, fallback to id
                    try:
                        layer_obj = QgsProcessingUtils.mapLayerFromString(
                            dest_id_sidewalks, context
                        )
                        if not layer_obj or not layer_obj.isValid():
                            results[self.OUTPUT_SIDEWALKS] = sidewalks_layer_4326
                        else:
                            results[self.OUTPUT_SIDEWALKS] = layer_obj
                    except Exception:
                        results[self.OUTPUT_SIDEWALKS] = sidewalks_layer_4326
                else:
                    feedback.reportError(
                        self.tr("Failed to create sink for final sidewalks layer."),
                        True,
                    )
            else:
                feedback.reportError(
                    self.tr(
                        "Failed to reproject sidewalks to EPSG:4326 or no sidewalks to reproject."
                    ),
                    True,
                )

        # --- 9. Save Optional Debug Outputs (already in local TM) ---
        if (
            save_exclusion_zones_debug
            and exclusion_zones_layer_local_tm
            and exclusion_zones_layer_local_tm.isValid()
            and exclusion_zones_layer_local_tm.featureCount() > 0
        ):
            (sink_exclusion, dest_id_exclusion) = self.parameterAsSink(
                parameters_alg,
                self.OUTPUT_EXCLUSION_ZONES_DEBUG,
                context,
                exclusion_zones_layer_local_tm.fields(),
                exclusion_zones_layer_local_tm.wkbType(),
                local_tm_crs,
            )
            if sink_exclusion:
                for feature in exclusion_zones_layer_local_tm.getFeatures():
                    sink_exclusion.addFeature(feature, QgsFeatureSink.FastInsert)
                results[self.OUTPUT_EXCLUSION_ZONES_DEBUG] = dest_id_exclusion
            else:
                feedback.pushWarning(
                    self.tr("Failed to create sink for exclusion zones debug layer.")
                )

        if (
            save_sure_zones_debug
            and sure_zones_layer_local_tm
            and sure_zones_layer_local_tm.isValid()
            and sure_zones_layer_local_tm.featureCount() > 0
        ):
            (sink_sure, dest_id_sure) = self.parameterAsSink(
                parameters_alg,
                self.OUTPUT_SURE_ZONES_DEBUG,
                context,
                sure_zones_layer_local_tm.fields(),
                sure_zones_layer_local_tm.wkbType(),
                local_tm_crs,
            )
            if sink_sure:
                for feature in sure_zones_layer_local_tm.getFeatures():
                    sink_sure.addFeature(feature, QgsFeatureSink.FastInsert)
                results[self.OUTPUT_SURE_ZONES_DEBUG] = dest_id_sure
            else:
                feedback.pushWarning(
                    self.tr("Failed to create sink for sure zones debug layer.")
                )

        if (
            save_streets_width_adjusted_debug
            and width_adjusted_streets_layer_local_tm
            and width_adjusted_streets_layer_local_tm.isValid()
            and width_adjusted_streets_layer_local_tm.featureCount() > 0
        ):
            (sink_adjusted_streets, dest_id_adjusted_streets) = self.parameterAsSink(
                parameters_alg,
                self.OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG,
                context,
                width_adjusted_streets_layer_local_tm.fields(),
                width_adjusted_streets_layer_local_tm.wkbType(),
                local_tm_crs,
            )
            if sink_adjusted_streets:
                for feature in width_adjusted_streets_layer_local_tm.getFeatures():
                    sink_adjusted_streets.addFeature(feature, QgsFeatureSink.FastInsert)
                results[self.OUTPUT_STREETS_WIDTH_ADJUSTED_DEBUG] = (
                    dest_id_adjusted_streets
                )
            else:
                feedback.pushWarning(
                    self.tr(
                        "Failed to create sink for width-adjusted streets debug layer."
                    )
                )

        feedback.pushInfo(self.tr("Processing finished."))
        return results

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return FullSidewalkreatorBboxAlgorithm()

    def name(self):
        return "osm_sidewalkreator_full_bbox"

    def displayName(self):
        return self.tr("Generate Full Sidewalk Network (from BBOX)")

    # def group(self):
    #     return self.tr('OSM Sidewalkreator')

    # def groupId(self):
    #     return 'osm_sidewalkreator'

    def shortHelpString(self):
        return self.tr(
            "Generates a full sidewalk network from OSM data within a specified bounding box (extent). Fetches roads and optional buildings, then applies sidewalk generation rules. Outputs sidewalk lines in EPSG:4326 and optional debug layers."
        )

    def icon(self):
        # Assuming you have an icon in your plugin's directory
        # __file__ is plugin_root/processing/full_sidewalkreator_bbox_algorithm.py
        # os.path.dirname(__file__) is plugin_root/processing/
        # os.path.dirname(os.path.dirname(__file__)) is plugin_root/
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def createInstance(self):
        try:
            print("[FullSidewalkreatorBboxAlgorithm] createInstance() called")
            return FullSidewalkreatorBboxAlgorithm()
        except Exception as e:
            try:
                QgsMessageLog.logMessage(
                    f"FullSidewalkreatorBboxAlgorithm createInstance failed: {e}",
                    "SidewalKreator",
                    Qgis.Critical,
                )
                import traceback

                traceback.print_exc()
            except Exception:
                pass
            raise
