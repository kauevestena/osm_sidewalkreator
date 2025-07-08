# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterNumber, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum, QgsProcessingParameterString,
    QgsCoordinateReferenceSystem, QgsFields, QgsFeature, QgsWkbTypes,
    QgsProcessingException, QgsField
)

# Assuming parameters.py has the defaults we need
from ..parameters import (
    default_curve_radius, min_d_to_building, d_to_add_to_each_side, minimal_buffer,
    perc_draw_kerbs, perc_tol_crossings, d_to_add_interp_d, CRS_LATLON_4326 # Added CRS_LATLON_4326
    # default_widths will be used internally for now
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
    FETCH_ADDRESS_DATA = 'FETCH_ADDRESS_DATA' # For POI splitting with Voronoi

    DEAD_END_ITERATIONS = 'DEAD_END_ITERATIONS'

    # Sidewalk Generation Parameters (from draw_sidewalks)
    CHECK_OVERLAPS_BUILDINGS = 'CHECK_OVERLAPS_BUILDINGS' # Only if FETCH_BUILDINGS_DATA is true
    MIN_DIST_TO_BUILDINGS = 'MIN_DIST_TO_BUILDINGS'
    CURVE_RADIUS = 'CURVE_RADIUS'
    DIST_TO_ADD_TO_WIDTH_TOTAL = 'DIST_TO_ADD_TO_WIDTH_TOTAL' # This is total for both sides
    MIN_GENERATED_SIDEWALK_WIDTH = 'MIN_GENERATED_SIDEWALK_WIDTH' # This is total width

    # Crossing Generation Parameters (from draw_crossings)
    CROSSING_METHOD = 'CROSSING_METHOD' # Enum: Parallel, Perpendicular
    CROSSING_KERB_PERCENT = 'CROSSING_KERB_PERCENT'
    CROSSING_LENGTH_TOLERANCE_PERCENT = 'CROSSING_LENGTH_TOLERANCE_PERCENT'
    CROSSING_INWARD_INTERPOLATION_DIST = 'CROSSING_INWARD_INTERPOLATION_DIST'
    CROSSING_MIN_ROAD_SEGMENT_LENGTH = 'CROSSING_MIN_ROAD_SEGMENT_LENGTH'
    CROSSING_REMOVE_ABOVE_TOLERANCE = 'CROSSING_REMOVE_ABOVE_TOLERANCE'

    # Splitting Parameters (from sidewalks_splitting)
    # Simplified: Main choice, then specific value if that choice is made.
    # More complex UI interactions (like enabling/disabling based on alongside_vor_checkbox) are hard here.
    # We can have a primary split_method (Enum: None, Voronoi, MaxLength, SegmentsByNumber)
    # And then conditional parameters or just provide all and user fills relevant one.
    # Let's provide all and user must use them logically.
    SPLIT_DONT = 'SPLIT_DONT' # If true, no splitting beyond protoblock corners
    SPLIT_USE_VORONOI = 'SPLIT_USE_VORONOI' # If true, uses Voronoi
    SPLIT_VORONOI_MIN_POIS = 'SPLIT_VORONOI_MIN_POIS' # Needs FETCH_ADDRESS_DATA and/or FETCH_BUILDINGS_DATA
    # SPLIT_VORONOI_ALONGSIDE_OTHER is too complex for now, implies conditional logic flow
    SPLIT_BY_MAX_LENGTH = 'SPLIT_BY_MAX_LENGTH'
    SPLIT_MAX_LENGTH_VAL = 'SPLIT_MAX_LENGTH_VAL'
    SPLIT_BY_SEGMENT_NUMBER = 'SPLIT_BY_SEGMENT_NUMBER'
    SPLIT_SEGMENT_NUMBER_VAL = 'SPLIT_SEGMENT_NUMBER_VAL'
    # SPLIT_ONLY_FACADES not directly translated for now, part of specific checkbox logic

    # OUTPUTS
    OUTPUT_SIDEWALKS = 'OUTPUT_SIDEWALKS'
    OUTPUT_CROSSINGS = 'OUTPUT_CROSSINGS'
    OUTPUT_KERBS = 'OUTPUT_KERBS'
    OUTPUT_PROTOBLOCKS_DEBUG = 'OUTPUT_PROTOBLOCKS_DEBUG' # Optional debug output

    # Crossing method enum values
    CROSSING_METHOD_OPTIONS = ['Parallel to Transversal', 'Perpendicular to Road']


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
                       "Outputs are in EPSG:4326.")

    def initAlgorithm(self, config=None):
        # Input Polygon
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGON,
                self.tr('Input Area Polygon Layer (EPSG:4326 recommended)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        # Timeout
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIMEOUT,
                self.tr('OSM Download Timeout (seconds)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=60, minValue=10, maxValue=300
            )
        )
        # Data Fetching Options
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FETCH_BUILDINGS_DATA,
                self.tr('Fetch OSM Buildings Data (for overlap checks & POI splitting)'),
                defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FETCH_ADDRESS_DATA,
                self.tr('Fetch OSM Address Data (for POI splitting with Voronoi)'),
                defaultValue=True
            )
        )

        # Data Cleaning Parameters
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEAD_END_ITERATIONS,
                self.tr('Iterations to Remove Dead-End Streets (for protoblocks)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=1, minValue=0, maxValue=10
            )
        )

        # Sidewalk Generation Parameters
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CHECK_OVERLAPS_BUILDINGS,
                self.tr('Adjust Sidewalk Width if Overlaps Buildings (slower)'),
                defaultValue=True # Only effective if FETCH_BUILDINGS_DATA is true
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_DIST_TO_BUILDINGS,
                self.tr('Min. Distance from Sidewalk to Buildings (meters)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=min_d_to_building, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CURVE_RADIUS,
                self.tr('Sidewalk Corner Curve Radius (meters)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=default_curve_radius, minValue=0.0, maxValue=20.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DIST_TO_ADD_TO_WIDTH_TOTAL, # This is the dialog's "Distance to add to Width"
                self.tr('Total Added Width to Road for Sidewalk Axis (meters, both sides)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=d_to_add_to_each_side * 2, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_GENERATED_SIDEWALK_WIDTH, # This is the dialog's "Min Width" for sidewalks near buildings
                self.tr('Min. Generated Sidewalk Width if Near Buildings (meters, total)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=minimal_buffer * 2, minValue=0.1, maxValue=10.0
            )
        )

        # Crossing Generation Parameters
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CROSSING_METHOD,
                self.tr('Crossing Generation Method'),
                options=self.CROSSING_METHOD_OPTIONS,
                defaultValue=0, # Parallel
                optional=False
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_KERB_PERCENT,
                self.tr('Crossing: Kerb Position (% of half-crossing length from center)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=int(perc_draw_kerbs), minValue=0, maxValue=100
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_LENGTH_TOLERANCE_PERCENT,
                self.tr('Crossing: Max Length Tolerance (%)'),
                QgsProcessingParameterNumber.Integer,
                defaultValue=int(perc_tol_crossings), minValue=0, maxValue=100
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_INWARD_INTERPOLATION_DIST,
                self.tr('Crossing: Inward Interpolation Distance from Intersection (meters)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=d_to_add_interp_d, minValue=0.0, maxValue=10.0
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_MIN_ROAD_SEGMENT_LENGTH,
                self.tr('Crossing: Min. Road Segment Length to Generate Crossing (meters)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=20.0, minValue=0.0
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CROSSING_REMOVE_ABOVE_TOLERANCE,
                self.tr('Crossing: Remove Crossings Longer Than Tolerance'),
                defaultValue=False
            )
        )

        # Sidewalk Splitting Parameters
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_DONT, self.tr('Splitting: Do Not Split Sidewalks Further'),
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_USE_VORONOI, self.tr('Splitting: Use Voronoi (needs POI data)'),
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_VORONOI_MIN_POIS, self.tr('Splitting: Min. POIs for Voronoi Cell'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_BY_MAX_LENGTH, self.tr('Splitting: Split by Max Length'),
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_MAX_LENGTH_VAL, self.tr('Splitting: Max Length Value (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=50.0, minValue=1.0
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SPLIT_BY_SEGMENT_NUMBER, self.tr('Splitting: Split into Fixed Number of Segments'),
                defaultValue=False
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_SEGMENT_NUMBER_VAL, self.tr('Splitting: Number of Segments'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1
            )
        )

        # Outputs
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_SIDEWALKS, self.tr('Output Sidewalks (EPSG:4326)'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_CROSSINGS, self.tr('Output Crossings (EPSG:4326)'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT_KERBS, self.tr('Output Kerbs (EPSG:4326)'))
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_PROTOBLOCKS_DEBUG,
                self.tr('Output Protoblocks (Debug, Local TM CRS)'),
                optional=True # Make this optional
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Placeholder: Retrieving parameters..."))

        # Retrieve all parameters (example for a few)
        input_polygon_src_param_value = parameters[self.INPUT_POLYGON] # Get the raw parameter value (string)
        timeout_val = self.parameterAsInt(parameters, self.TIMEOUT, context)
        curve_radius_val = self.parameterAsDouble(parameters, self.CURVE_RADIUS, context)

        feedback.pushInfo(f"Input Polygon Parameter Value: {input_polygon_src_param_value}")
        feedback.pushInfo(f"Timeout: {timeout_val}")
        feedback.pushInfo(f"Curve Radius: {curve_radius_val}")
        # ... log other retrieved parameters for testing ...

        # Placeholder: Prepare empty sinks for all outputs
        # Sidewalks
        (sidewalks_sink, sidewalks_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(),
            QgsWkbTypes.LineString, QgsCoordinateReferenceSystem(CRS_LATLON_4326))
        if sidewalks_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_SIDEWALKS))

        # Crossings
        (crossings_sink, crossings_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_CROSSINGS, context, QgsFields(),
            QgsWkbTypes.LineString, QgsCoordinateReferenceSystem(CRS_LATLON_4326))
        if crossings_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_CROSSINGS))

        # Kerbs
        (kerbs_sink, kerbs_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_KERBS, context, QgsFields(),
            QgsWkbTypes.Point, QgsCoordinateReferenceSystem(CRS_LATLON_4326)) # Kerbs are points
        if kerbs_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_KERBS))

        # Protoblocks (Debug) - check if output is requested
        protoblocks_sink, protoblocks_dest_id = None, None

        # Check if the user actually provided a path for the optional sink
        # The parameter value for a FeatureSink is the output path or 'TEMPORARY_OUTPUT' etc.
        # If it's optional and not filled by user, it might be None or an empty string.
        debug_protoblocks_output_spec = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)

        if debug_protoblocks_output_spec: # If user specified something (not None, not empty string)
            try:
                # Attempt to get the sink. If this fails (e.g., invalid path), it will raise.
                # If it succeeds, sink will be valid.
                # For an optional output, if no value is provided by the user in the UI,
                # parameterAsSink might return None or raise if called on an empty parameter.
                # It's safer to check parameter value first.
                protoblocks_sink, protoblocks_dest_id = self.parameterAsSink(
                    parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, QgsFields(),
                    QgsWkbTypes.Polygon, QgsCoordinateReferenceSystem(CRS_LATLON_4326) # Placeholder CRS
                )
                if protoblocks_sink is None: # Should not happen if parameters[key] was non-empty and valid path
                    feedback.pushInfo(self.tr("Debug protoblocks output was specified, but sink creation failed (returned None)."))
                    protoblocks_dest_id = None
            except Exception as e:
                feedback.pushInfo(self.tr(f"Could not prepare debug protoblocks sink: {e}. It will not be generated."))
                protoblocks_dest_id = None
        else:
            feedback.pushInfo(self.tr("Debug protoblocks output was not specified by the user."))

        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Placeholder: Finished."))

        results = {
            self.OUTPUT_SIDEWALKS: sidewalks_dest_id,
            self.OUTPUT_CROSSINGS: crossings_dest_id,
            self.OUTPUT_KERBS: kerbs_dest_id
        }
        if protoblocks_dest_id: # Only add to results if successfully prepared
            results[self.OUTPUT_PROTOBLOCKS_DEBUG] = protoblocks_dest_id
        return results

    def postProcessAlgorithm(self, context, feedback):
        return {}
