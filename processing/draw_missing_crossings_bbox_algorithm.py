# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterExtent,
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
    QgsSpatialIndex,
    QgsFeatureRequest,
    QgsPointXY,
)
import math
import os

# Import necessary functions from other plugin modules
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data
from ..generic_functions import (
    reproject_layer_localTM,
    cliplayer_v2,
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
    DEFAULT_TIMEOUT_SECONDS,
    perc_draw_kerbs,
    default_curve_radius,
    d_to_add_to_each_side,
)


class DrawMissingCrossingsBBoxAlgorithm(QgsProcessingAlgorithm):
    """
    Draws missing pedestrian crossings inside a bounding box by:
    1. Generating protoblocks
    2. Identifying adjacent block pairs with sidewalks
    3. Checking for existing crossings in OSM
    4. Creating missing crossing geometries with kerb points
    """

    # Input parameters
    INPUT_EXTENT = "INPUT_EXTENT"
    TIMEOUT = "TIMEOUT"
    SEARCH_RADIUS_FACTOR = "SEARCH_RADIUS_FACTOR"
    
    # Output parameters
    OUTPUT_CROSSINGS = "OUTPUT_CROSSINGS"
    OUTPUT_KERBS = "OUTPUT_KERBS"
    OUTPUT_PROTOBLOCKS_DEBUG = "OUTPUT_PROTOBLOCKS_DEBUG"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return DrawMissingCrossingsBBoxAlgorithm()

    def name(self):
        return "draw_missing_crossings_bbox"

    def displayName(self):
        return self.tr("Draw Missing Crossings (BBOX)")

    def group(self):
        return self.tr("OSM Sidewalkreator")

    def groupId(self):
        return "osm_sidewalkreator"

    def shortHelpString(self):
        return self.tr(
            "Draws missing pedestrian crossings by analyzing adjacent protoblock pairs "
            "within a bounding box. The algorithm:\n\n"
            "1. Generates protoblocks from OSM street data\n"
            "2. Identifies pairs of adjacent blocks that both have sidewalks\n"
            "3. Searches for existing crossings in OSM data\n"
            "4. Creates crossing lines and kerb points for missing crossings\n\n"
            "Requires internet connection to fetch OSM data."
        )

    def initAlgorithm(self, config=None):
        # Input extent
        self.addParameter(
            QgsProcessingParameterExtent(
                self.INPUT_EXTENT,
                self.tr("Bounding box extent"),
                defaultValue=None
            )
        )

        # Timeout for OSM data fetching
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr("Timeout for OSM data requests (seconds)"),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=DEFAULT_TIMEOUT_SECONDS,
                minValue=10,
                maxValue=300
            )
        )
        
        # Search radius factor (multiplier for shared edge length)
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEARCH_RADIUS_FACTOR,
                self.tr("Search radius factor (x shared edge length)"),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                minValue=0.1,
                maxValue=2.0
            )
        )

        # Output layers
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_CROSSINGS,
                self.tr("Missing crossings"),
                type=QgsProcessing.TypeVectorLine
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_KERBS,
                self.tr("Kerb points"),
                type=QgsProcessing.TypeVectorPoint
            )
        )

        # Optional debug output
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS_DEBUG,
                self.tr("Protoblocks (debug)"),
                type=QgsProcessing.TypeVectorPolygon,
                createByDefault=False,
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """Main processing function."""
        
        # Get parameters
        extent = self.parameterAsExtent(parameters, self.INPUT_EXTENT, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT)
        search_radius_factor = self.parameterAsDouble(parameters, self.SEARCH_RADIUS_FACTOR)
        
        # Set up multi-step feedback
        feedback = QgsProcessingMultiStepFeedback(6, feedback)
        
        # Step 1: Generate protoblocks
        feedback.setCurrentStep(0)
        feedback.pushInfo("Step 1: Generating protoblocks from OSM data...")
        protoblocks_layer = self.generate_protoblocks(extent, timeout, feedback)
        
        if feedback.isCanceled():
            return {}
            
        # Step 2: Identify adjacent pairs
        feedback.setCurrentStep(1) 
        feedback.pushInfo("Step 2: Identifying adjacent protoblock pairs...")
        adjacent_pairs = self.find_adjacent_pairs(protoblocks_layer, feedback)
        
        if feedback.isCanceled():
            return {}
            
        # Step 3: Check for existing sidewalks
        feedback.setCurrentStep(2)
        feedback.pushInfo("Step 3: Checking sidewalk existence...")
        pairs_with_sidewalks = self.filter_pairs_with_sidewalks(adjacent_pairs, extent, timeout, feedback)
        
        if feedback.isCanceled():
            return {}
            
        # Step 4: Search for existing crossings
        feedback.setCurrentStep(3)
        feedback.pushInfo("Step 4: Searching for existing crossings...")
        pairs_missing_crossings = self.find_missing_crossings(pairs_with_sidewalks, extent, timeout, search_radius_factor, feedback)
        
        if feedback.isCanceled():
            return {}
            
        # Step 5: Generate crossing geometries
        feedback.setCurrentStep(4)
        feedback.pushInfo("Step 5: Generating crossing and kerb geometries...")
        crossings_layer, kerbs_layer = self.generate_crossing_geometries(pairs_missing_crossings, extent, feedback)
        
        if feedback.isCanceled():
            return {}
            
        # Step 6: Write outputs
        feedback.setCurrentStep(5)
        feedback.pushInfo("Step 6: Writing output layers...")
        
        # Determine CRS for outputs
        if extent.crs().isValid():
            output_crs = extent.crs()
        else:
            output_crs = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            
        # Write crossings
        (crossings_sink, crossings_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_CROSSINGS, context,
            crossings_layer.fields(), QgsWkbTypes.LineString, output_crs
        )
        
        for feature in crossings_layer.getFeatures():
            crossings_sink.addFeature(feature, QgsFeatureSink.FastInsert)
            
        # Write kerbs  
        (kerbs_sink, kerbs_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_KERBS, context,
            kerbs_layer.fields(), QgsWkbTypes.Point, output_crs
        )
        
        for feature in kerbs_layer.getFeatures():
            kerbs_sink.addFeature(feature, QgsFeatureSink.FastInsert)
            
        # Optional protoblocks debug output
        protoblocks_dest_id = None
        if self.OUTPUT_PROTOBLOCKS_DEBUG in parameters and parameters[self.OUTPUT_PROTOBLOCKS_DEBUG] is not None:
            (protoblocks_sink, protoblocks_dest_id) = self.parameterAsSink(
                parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context,
                protoblocks_layer.fields(), QgsWkbTypes.Polygon, output_crs
            )
            
            for feature in protoblocks_layer.getFeatures():
                protoblocks_sink.addFeature(feature, QgsFeatureSink.FastInsert)
        
        feedback.pushInfo(f"Generated {crossings_layer.featureCount()} crossing lines and {kerbs_layer.featureCount()} kerb points")
        
        results = {
            self.OUTPUT_CROSSINGS: crossings_dest_id,
            self.OUTPUT_KERBS: kerbs_dest_id,
        }
        
        if protoblocks_dest_id:
            results[self.OUTPUT_PROTOBLOCKS_DEBUG] = protoblocks_dest_id
            
        return results

    def generate_protoblocks(self, extent, timeout, feedback):
        """Generate protoblocks by reusing existing protoblock generation logic."""
        feedback.pushInfo("Fetching OSM street data...")
        
        # Transform extent to EPSG:4326 if necessary
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent.crs() != crs_epsg4326:
            transform = QgsCoordinateTransform(
                extent.crs(), crs_epsg4326, QgsCoordinateTransform.context()
            )
            extent_4326 = transform.transform(extent)
        else:
            extent_4326 = extent
            
        # Build OSM query for highway data  
        query_str = osm_query_string_by_bbox(
            min_lat=extent_4326.yMinimum(),
            min_lgt=extent_4326.xMinimum(),
            max_lat=extent_4326.yMaximum(),
            max_lgt=extent_4326.xMaximum(),
            interest_key=highway_tag,
            way=True,
        )
        
        feedback.pushInfo("Downloading OSM data...")
        
        # Get OSM data
        osm_data_file = get_osm_data(
            querystring=query_str,
            tempfilesname="missing_crossings_osm_data",
            geomtype="LineString",
            timeout=timeout,
            return_as_string=False,
        )
        
        if osm_data_file is None:
            raise QgsProcessingException("Failed to fetch OSM data")
            
        feedback.pushInfo("Processing OSM data...")
        
        # Load OSM data as vector layer
        osm_layer = QgsVectorLayer(osm_data_file, "osm_streets", "ogr")
        if not osm_layer.isValid():
            raise QgsProcessingException("Failed to load OSM data")
            
        feedback.pushInfo(f"Loaded {osm_layer.featureCount()} street features")
        
        # Clean up the data - remove unconnected lines
        feedback.pushInfo("Cleaning street network...")
        cleaned_layer = remove_unconnected_lines_v2(osm_layer)
        
        # Polygonize the street network to create protoblocks
        feedback.pushInfo("Creating protoblocks...")
        protoblocks_layer = polygonize_lines(cleaned_layer, keepfields=False)
        
        if not protoblocks_layer.isValid() or protoblocks_layer.featureCount() == 0:
            raise QgsProcessingException("Failed to generate protoblocks - no polygons created")
            
        # Add fields to track sidewalk existence
        protoblocks_dp = protoblocks_layer.dataProvider()
        protoblocks_dp.addAttributes([
            QgsField("id", QVariant.Int),
            QgsField("has_sidewalks", QVariant.Bool),
        ])
        protoblocks_layer.updateFields()
        
        # Add ID field values
        features_to_update = []
        for i, feature in enumerate(protoblocks_layer.getFeatures()):
            feature.setAttribute("id", i + 1)
            feature.setAttribute("has_sidewalks", False)  # Will be updated later
            features_to_update.append(feature)
            
        protoblocks_dp.changeAttributeValues({f.id(): {0: f.attribute("id"), 1: f.attribute("has_sidewalks")} for f in features_to_update})
        
        feedback.pushInfo(f"Generated {protoblocks_layer.featureCount()} protoblocks")
        
        return protoblocks_layer

    def find_adjacent_pairs(self, protoblocks_layer, feedback):
        """Find pairs of adjacent protoblock polygons."""
        feedback.pushInfo("Building spatial index for adjacency detection...")
        
        # Create spatial index for efficient adjacency queries
        spatial_index = QgsSpatialIndex(protoblocks_layer.getFeatures())
        
        adjacent_pairs = []
        features = list(protoblocks_layer.getFeatures())
        
        for i, feature_a in enumerate(features):
            if feedback.isCanceled():
                break
                
            geom_a = feature_a.geometry()
            if not geom_a.isValid():
                continue
                
            # Find potentially adjacent features using spatial index
            # Use a small buffer to catch touching polygons
            search_geom = geom_a.buffer(0.1, 5)  # 10cm buffer with 5 segments
            candidate_ids = spatial_index.intersects(search_geom.boundingBox())
            
            for candidate_id in candidate_ids:
                feature_b = protoblocks_layer.getFeature(candidate_id)
                
                # Skip self and already processed pairs
                if feature_b.id() <= feature_a.id():
                    continue
                    
                geom_b = feature_b.geometry()
                if not geom_b.isValid():
                    continue
                    
                # Check if geometries share a boundary (are adjacent)
                if geom_a.touches(geom_b):
                    # Calculate shared boundary
                    intersection = geom_a.intersection(geom_b)
                    if intersection.type() == QgsWkbTypes.LineGeometry and intersection.length() > 0.5:  # Minimum 50cm shared edge
                        adjacent_pairs.append({
                            'feature_a': feature_a,
                            'feature_b': feature_b,
                            'shared_boundary': intersection,
                            'shared_length': intersection.length()
                        })
                        
        feedback.pushInfo(f"Found {len(adjacent_pairs)} adjacent protoblock pairs")
        return adjacent_pairs

    def filter_pairs_with_sidewalks(self, adjacent_pairs, extent, timeout, feedback):
        """Filter pairs where both blocks have sidewalks along shared edge."""
        feedback.pushInfo("Fetching sidewalk data from OSM...")
        
        # Transform extent to EPSG:4326 if necessary
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent.crs() != crs_epsg4326:
            transform = QgsCoordinateTransform(
                extent.crs(), crs_epsg4326, QgsCoordinateTransform.context()
            )
            extent_4326 = transform.transform(extent)
        else:
            extent_4326 = extent
            
        # Build OSM query for sidewalk/footway data
        sidewalk_query = osm_query_string_by_bbox(
            min_lat=extent_4326.yMinimum(),
            min_lgt=extent_4326.xMinimum(),
            max_lat=extent_4326.yMaximum(),
            max_lgt=extent_4326.xMaximum(),
            interest_key="highway",
            interest_value="footway",
            way=True,
        )
        
        # Get sidewalk data
        sidewalk_data_file = get_osm_data(
            querystring=sidewalk_query,
            tempfilesname="missing_crossings_sidewalk_data",
            geomtype="LineString", 
            timeout=timeout,
            return_as_string=False,
        )
        
        sidewalk_layer = None
        if sidewalk_data_file:
            sidewalk_layer = QgsVectorLayer(sidewalk_data_file, "osm_sidewalks", "ogr")
            if sidewalk_layer.isValid():
                feedback.pushInfo(f"Loaded {sidewalk_layer.featureCount()} sidewalk features")
            else:
                sidewalk_layer = None
                
        if not sidewalk_layer or sidewalk_layer.featureCount() == 0:
            feedback.pushWarning("No sidewalk data found - assuming all blocks need sidewalks")
            # For now, assume all adjacent pairs need crossings
            return adjacent_pairs
            
        # Create spatial index for sidewalks
        sidewalk_index = QgsSpatialIndex(sidewalk_layer.getFeatures())
        
        pairs_with_sidewalks = []
        
        for pair in adjacent_pairs:
            if feedback.isCanceled():
                break
                
            feature_a = pair['feature_a']
            feature_b = pair['feature_b']
            shared_boundary = pair['shared_boundary']
            
            # Check if both polygons have sidewalks near the shared boundary
            # Use a buffer around the shared boundary to search for sidewalks
            search_buffer = shared_boundary.buffer(5.0, 5)  # 5m buffer
            
            # Find sidewalks intersecting the search area
            sidewalk_candidates = sidewalk_index.intersects(search_buffer.boundingBox())
            
            sidewalks_near_a = False
            sidewalks_near_b = False
            
            for sidewalk_id in sidewalk_candidates:
                sidewalk_feature = sidewalk_layer.getFeature(sidewalk_id)
                sidewalk_geom = sidewalk_feature.geometry()
                
                if sidewalk_geom.intersects(search_buffer):
                    # Check which protoblock this sidewalk is closer to
                    distance_to_a = feature_a.geometry().distance(sidewalk_geom)
                    distance_to_b = feature_b.geometry().distance(sidewalk_geom)
                    
                    if distance_to_a < 2.0:  # Within 2m of protoblock A
                        sidewalks_near_a = True
                    if distance_to_b < 2.0:  # Within 2m of protoblock B  
                        sidewalks_near_b = True
                        
            # Only keep pairs where both sides have sidewalks
            if sidewalks_near_a and sidewalks_near_b:
                pairs_with_sidewalks.append(pair)
                
        feedback.pushInfo(f"Found {len(pairs_with_sidewalks)} pairs with sidewalks on both sides")
        return pairs_with_sidewalks

    def find_missing_crossings(self, pairs_with_sidewalks, extent, timeout, search_radius_factor, feedback):
        """Search for existing crossings and identify missing ones."""
        feedback.pushInfo("Searching for existing crossings in OSM...")
        
        # Transform extent to EPSG:4326 if necessary
        crs_epsg4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        if extent.crs() != crs_epsg4326:
            transform = QgsCoordinateTransform(
                extent.crs(), crs_epsg4326, QgsCoordinateTransform.context()
            )
            extent_4326 = transform.transform(extent)
        else:
            extent_4326 = extent
            
        # Build OSM query for crossing data
        crossing_query = osm_query_string_by_bbox(
            min_lat=extent_4326.yMinimum(),
            min_lgt=extent_4326.xMinimum(),
            max_lat=extent_4326.yMaximum(),
            max_lgt=extent_4326.xMaximum(),
            interest_key="highway",
            interest_value="crossing",
            way=False,  # Crossings are typically nodes/points
        )
        
        # Get crossing data
        crossing_data_file = get_osm_data(
            querystring=crossing_query,
            tempfilesname="missing_crossings_crossing_data",
            geomtype="Point",
            timeout=timeout,
            return_as_string=False,
        )
        
        crossing_layer = None
        if crossing_data_file:
            crossing_layer = QgsVectorLayer(crossing_data_file, "osm_crossings", "ogr")
            if crossing_layer.isValid():
                feedback.pushInfo(f"Loaded {crossing_layer.featureCount()} existing crossing features")
            else:
                crossing_layer = None
                
        # Create spatial index for crossings if we have any
        crossing_index = None
        if crossing_layer and crossing_layer.featureCount() > 0:
            crossing_index = QgsSpatialIndex(crossing_layer.getFeatures())
        else:
            feedback.pushInfo("No existing crossings found - all pairs will be considered missing crossings")
            
        pairs_missing_crossings = []
        
        for pair in pairs_with_sidewalks:
            if feedback.isCanceled():
                break
                
            shared_boundary = pair['shared_boundary']
            shared_length = pair['shared_length']
            
            # Define search radius as factor of shared edge length
            search_radius = shared_length * search_radius_factor
            
            # Check if there are existing crossings near the shared boundary
            has_existing_crossing = False
            
            if crossing_index:
                # Get centroid of shared boundary for search
                boundary_centroid = shared_boundary.centroid()
                search_area = boundary_centroid.buffer(search_radius, 8)
                
                # Find crossings within search radius
                crossing_candidates = crossing_index.intersects(search_area.boundingBox())
                
                for crossing_id in crossing_candidates:
                    crossing_feature = crossing_layer.getFeature(crossing_id)
                    crossing_geom = crossing_feature.geometry()
                    
                    # Check actual distance
                    if boundary_centroid.distance(crossing_geom) <= search_radius:
                        has_existing_crossing = True
                        break
                        
            # If no existing crossing found, add to missing list
            if not has_existing_crossing:
                pairs_missing_crossings.append(pair)
                
        feedback.pushInfo(f"Found {len(pairs_missing_crossings)} pairs missing crossings")
        return pairs_missing_crossings

    def generate_crossing_geometries(self, pairs_missing_crossings, extent, feedback):
        """Generate crossing lines and kerb points."""
        feedback.pushInfo("Generating crossing and kerb geometries...")
        
        # Determine CRS
        if extent.crs().isValid():
            output_crs = extent.crs()
        else:
            output_crs = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
            
        # Create output layers
        crossings_layer = QgsVectorLayer(f"LineString?crs={output_crs.authid()}", "crossings", "memory")
        crossings_dp = crossings_layer.dataProvider()
        crossings_dp.addAttributes([
            QgsField("crossing_id", QVariant.Int),
            QgsField("length", QVariant.Double),
            QgsField("type", QVariant.String),
        ])
        crossings_layer.updateFields()
        
        kerbs_layer = QgsVectorLayer(f"Point?crs={output_crs.authid()}", "kerbs", "memory")
        kerbs_dp = kerbs_layer.dataProvider()
        kerbs_dp.addAttributes([
            QgsField("kerb_id", QVariant.Int),
            QgsField("crossing_id", QVariant.Int),
            QgsField("kerb_type", QVariant.String),
        ])
        kerbs_layer.updateFields()
        
        crossing_id = 1
        kerb_id = 1
        
        crossing_features = []
        kerb_features = []
        
        for pair in pairs_missing_crossings:
            if feedback.isCanceled():
                break
                
            shared_boundary = pair['shared_boundary']
            
            # For line geometries, create crossing perpendicular to the shared boundary
            if shared_boundary.type() == QgsWkbTypes.LineGeometry:
                # Get the centroid of the shared boundary
                boundary_centroid = shared_boundary.centroid().asPoint()
                
                # For simplicity, create a crossing line along the shared boundary
                # In a more sophisticated implementation, this would be perpendicular to the street
                crossing_geom = shared_boundary
                crossing_length = shared_boundary.length()
                
                # Create crossing feature
                crossing_feature = QgsFeature()
                crossing_feature.setGeometry(crossing_geom)
                crossing_feature.setAttributes([
                    crossing_id,
                    crossing_length,
                    "generated"
                ])
                crossing_features.append(crossing_feature)
                
                # Create kerb points at the ends of the crossing
                if crossing_geom.type() == QgsWkbTypes.LineGeometry:
                    # Get start and end points
                    line = crossing_geom.asPolyline()
                    if len(line) >= 2:
                        start_point = line[0]
                        end_point = line[-1]
                        
                        # Create kerb at start
                        kerb_start = QgsFeature()
                        kerb_start.setGeometry(QgsGeometry.fromPointXY(start_point))
                        kerb_start.setAttributes([
                            kerb_id,
                            crossing_id,
                            "lowered"
                        ])
                        kerb_features.append(kerb_start)
                        kerb_id += 1
                        
                        # Create kerb at end
                        kerb_end = QgsFeature()
                        kerb_end.setGeometry(QgsGeometry.fromPointXY(end_point))
                        kerb_end.setAttributes([
                            kerb_id,
                            crossing_id,
                            "lowered"
                        ])
                        kerb_features.append(kerb_end)
                        kerb_id += 1
                        
                crossing_id += 1
                
        # Add features to layers
        if crossing_features:
            crossings_dp.addFeatures(crossing_features)
        if kerb_features:
            kerbs_dp.addFeatures(kerb_features)
            
        feedback.pushInfo(f"Generated {len(crossing_features)} crossing lines and {len(kerb_features)} kerb points")
        
        return crossings_layer, kerbs_layer