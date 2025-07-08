# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterNumber, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsCoordinateReferenceSystem, QgsFields, QgsFeature, QgsWkbTypes,
    QgsProcessingException, QgsField
)

# Assuming parameters.py has the defaults we need
from ..parameters import (
    default_curve_radius, min_d_to_building, d_to_add_to_each_side, minimal_buffer,
    perc_draw_kerbs, perc_tol_crossings, d_to_add_interp_d, CRS_LATLON_4326
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
                self.FETCH_BUILDINGS_DATA, self.tr('Fetch OSM Buildings Data'),
                defaultValue=True,
                helpText=self.tr("Needed for building overlap checks and can be used for POI-based sidewalk splitting with Voronoi.")
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FETCH_ADDRESS_DATA, self.tr('Fetch OSM Address Data (addr:housenumber)'),
                defaultValue=True,
                helpText=self.tr("Can be used for POI-based sidewalk splitting with Voronoi.")
            )
        )

        # === Protoblock/Street Cleaning Stage ===
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEAD_END_ITERATIONS, self.tr('Iterations to Remove Dead-End Streets'),
                QgsProcessingParameterNumber.Integer, defaultValue=1, minValue=0, maxValue=10,
                helpText=self.tr("Applied during protoblock generation to clean the street network.")
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
                self.SIDEWALK_MIN_DIST_TO_BUILDING, self.tr('Min. Distance from Sidewalk to Buildings (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=min_d_to_building, minValue=0.0, maxValue=10.0,
                helpText=self.tr("Effective only if 'Adjust Sidewalk Width if Overlaps Buildings' is checked and building data is fetched.")
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIDEWALK_MIN_WIDTH_IF_NEAR_BUILDING, self.tr('Min. Generated Sidewalk Width if Near Buildings (meters, total width)'),
                QgsProcessingParameterNumber.Double, defaultValue=minimal_buffer * 2, minValue=0.1, maxValue=10.0,
                helpText=self.tr("Effective only if 'Adjust Sidewalk Width if Overlaps Buildings' is checked and building data is fetched.")
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
                self.SPLITTING_METHOD, self.tr('Sidewalk Splitting Method'),
                options=self.SPLITTING_METHOD_OPTIONS_ENUM, defaultValue=0, # None
                helpText=self.tr("Splitting occurs after initial generation by protoblock corners.")
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_VORONOI_MIN_POIS, self.tr('Splitting (Voronoi): Min. POIs per Cell'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1,
                helpText=self.tr("Effective only if Splitting Method is 'Voronoi' and POI data (buildings/addresses) is fetched.")
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_MAX_LENGTH_VALUE, self.tr('Splitting (Max Length): Value (meters)'),
                QgsProcessingParameterNumber.Double, defaultValue=50.0, minValue=1.0,
                helpText=self.tr("Effective only if Splitting Method is 'By Maximum Length'.")
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPLIT_SEGMENT_NUMBER_VALUE, self.tr('Splitting (By Number): Number of Segments'),
                QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1,
                helpText=self.tr("Effective only if Splitting Method is 'By Fixed Number of Segments'.")
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
        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Algorithm Started (Placeholder)..."))

        input_polygon_src_param_value = parameters[self.INPUT_POLYGON]
        timeout_val = self.parameterAsInt(parameters, self.TIMEOUT, context)
        curve_radius_val = self.parameterAsDouble(parameters, self.SIDEWALK_CURVE_RADIUS, context)

        feedback.pushInfo(f"Input Polygon Parameter Value: {input_polygon_src_param_value}")
        feedback.pushInfo(f"Timeout: {timeout_val}")
        feedback.pushInfo(f"Sidewalk Curve Radius: {curve_radius_val}")

        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)

        (sidewalks_sink, sidewalks_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_SIDEWALKS, context, QgsFields(),
            QgsWkbTypes.LineString, crs_4326)
        if sidewalks_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_SIDEWALKS))

        (crossings_sink, crossings_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_CROSSINGS, context, QgsFields(),
            QgsWkbTypes.LineString, crs_4326)
        if crossings_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_CROSSINGS))

        (kerbs_sink, kerbs_dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_KERBS, context, QgsFields(),
            QgsWkbTypes.Point, crs_4326)
        if kerbs_sink is None: raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT_KERBS))

        protoblocks_sink, protoblocks_dest_id = None, None
        debug_protoblocks_output_spec = parameters.get(self.OUTPUT_PROTOBLOCKS_DEBUG)

        if debug_protoblocks_output_spec:
            try:
                protoblocks_sink, protoblocks_dest_id = self.parameterAsSink(
                    parameters, self.OUTPUT_PROTOBLOCKS_DEBUG, context, QgsFields(),
                    QgsWkbTypes.Polygon, crs_4326 # Placeholder CRS, actual will be local_tm_crs
                )
                if protoblocks_sink is None:
                    feedback.pushInfo(self.tr("Debug protoblocks output was specified, but sink creation failed (returned None)."))
                    protoblocks_dest_id = None
            except Exception as e:
                feedback.pushInfo(self.tr(f"Could not prepare debug protoblocks sink: {e}. It will not be generated."))
                protoblocks_dest_id = None
        else:
            feedback.pushInfo(self.tr("Debug protoblocks output was not specified by the user."))

        feedback.pushInfo(self.tr("Full Sidewalkreator (Polygon) - Placeholder: Finished preparing empty outputs."))

        results = {
            self.OUTPUT_SIDEWALKS: sidewalks_dest_id,
            self.OUTPUT_CROSSINGS: crossings_dest_id,
            self.OUTPUT_KERBS: kerbs_dest_id
        }
        if protoblocks_dest_id:
            results[self.OUTPUT_PROTOBLOCKS_DEBUG] = protoblocks_dest_id
        return results

    def postProcessAlgorithm(self, context, feedback):
        return {}
