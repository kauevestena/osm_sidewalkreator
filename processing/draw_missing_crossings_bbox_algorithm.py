# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterExtent,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingMultiStepFeedback,
    QgsFeatureSink,
    QgsVectorLayer,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsSpatialIndex,
    QgsFeatureRequest,
)
import math
import os

from qgis import processing

from ..parameters import (
    CRS_LATLON_4326,
    perc_draw_kerbs,
)
from ..generic_functions import (
    reproject_layer_localTM,
    layer_from_featlist,
)
from ..osm_fetch import osm_query_string_by_bbox, get_osm_data


class DrawMissingCrossingsBboxAlgorithm(QgsProcessingAlgorithm):
    """
    Detect adjacent protoblock pairs with existing sidewalks and draw missing crossings
    across their shared edges when no OSM crossing exists nearby.
    """

    INPUT_EXTENT = "INPUT_EXTENT"
    TIMEOUT = "TIMEOUT"
    CROSSING_LENGTH = "CROSSING_LENGTH"
    KERB_OFFSET_PERCENT = "KERB_OFFSET_PERCENT"
    MIN_SHARED_EDGE_LEN = "MIN_SHARED_EDGE_LEN"
    REQUIRE_INTERSECTION = "REQUIRE_INTERSECTION"
    ENDPOINT_MIN_BLOCKS = "ENDPOINT_MIN_BLOCKS"

    OUTPUT_CROSSINGS = "OUTPUT_CROSSINGS"
    OUTPUT_KERBS = "OUTPUT_KERBS"

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        try:
            return DrawMissingCrossingsBboxAlgorithm()
        except Exception as e:
            try:
                from qgis.core import QgsMessageLog, Qgis
                import traceback

                QgsMessageLog.logMessage(
                    f"DrawMissingCrossingsBboxAlgorithm createInstance failed: {e}",
                    "SidewalKreator",
                    Qgis.Critical,
                )
                traceback.print_exc()
            except Exception:
                pass
            raise

    def name(self):
        return "drawmissingcrossingsfrombbox"

    def displayName(self):
        return self.tr("Draw Missing Crossings (from BBOX)")

    def shortHelpString(self):
        return self.tr(
            "Find adjacent protoblocks with existing sidewalks and create crossings on shared edges without nearby OSM crossings. Outputs crossings and kerb points (EPSG:4326)."
        )

    def icon(self):
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        icon_path = os.path.join(plugin_dir, "icon.png")
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(
                self.INPUT_EXTENT,
                self.tr("Area of Interest (Bounding Box Extent)"),
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
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CROSSING_LENGTH,
                self.tr("Crossing nominal length (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=8.0,
                minValue=2.0,
                maxValue=50.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.KERB_OFFSET_PERCENT,
                self.tr("Kerb position along halves (%)"),
                QgsProcessingParameterNumber.Integer,
                defaultValue=int(perc_draw_kerbs),
                minValue=5,
                maxValue=45,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_SHARED_EDGE_LEN,
                self.tr("Minimum shared edge length to consider (m)"),
                QgsProcessingParameterNumber.Double,
                defaultValue=5.0,
                minValue=0.5,
                maxValue=500.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_CROSSINGS, self.tr("Generated Crossings (EPSG:4326)")
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_KERBS, self.tr("Generated Kerbs (EPSG:4326)")
            )
        )
        # Advanced filters to reduce false positives
        p_bool = QgsProcessingParameterBoolean(
            self.REQUIRE_INTERSECTION,
            self.tr("Require intersection at shared-edge endpoints (reduce mid-block)"),
            defaultValue=True,
        )
        p_bool.setFlags(p_bool.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(p_bool)

        p_int = QgsProcessingParameterNumber(
            self.ENDPOINT_MIN_BLOCKS,
            self.tr("Min. protoblocks at endpoint (intersection test)"),
            QgsProcessingParameterNumber.Integer,
            defaultValue=3,
            minValue=2,
            maxValue=6,
        )
        p_int.setFlags(p_int.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(p_int)

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        feedback.pushInfo(self.tr("Starting Draw Missing Crossings (BBOX)..."))

        # Extract and transform extent to EPSG:4326
        input_extent = self.parameterAsExtent(parameters, self.INPUT_EXTENT, context)
        extent_crs = self.parameterAsExtentCrs(parameters, self.INPUT_EXTENT, context)
        timeout = self.parameterAsInt(parameters, self.TIMEOUT, context)
        crossing_len_m = self.parameterAsDouble(parameters, self.CROSSING_LENGTH, context)
        kerb_perc = max(5, min(45, int(self.parameterAsInt(parameters, self.KERB_OFFSET_PERCENT, context))))
        min_shared_len = self.parameterAsDouble(parameters, self.MIN_SHARED_EDGE_LEN, context)
        require_intersection = self.parameterAsBool(parameters, self.REQUIRE_INTERSECTION, context)
        endpoint_min_blocks = int(self.parameterAsInt(parameters, self.ENDPOINT_MIN_BLOCKS, context))

        crs_4326 = QgsCoordinateReferenceSystem(CRS_LATLON_4326)
        def _looks_like_degrees(rect: QgsRectangle) -> bool:
            try:
                return (
                    -180.0 <= rect.xMinimum() <= 180.0
                    and -180.0 <= rect.xMaximum() <= 180.0
                    and -90.0 <= rect.yMinimum() <= 90.0
                    and -90.0 <= rect.yMaximum() <= 90.0
                )
            except Exception:
                return False

        if extent_crs != crs_4326:
            if _looks_like_degrees(input_extent):
                # Avoid double-transforming; treat values as already in degrees
                pass
            else:
                transform_ext = QgsCoordinateTransform(extent_crs, crs_4326, context.transformContext())
                input_extent = transform_ext.transform(input_extent)

        if input_extent.isEmpty():
            raise QgsProcessingException(self.tr("Provided extent is empty."))

        min_lon = input_extent.xMinimum()
        min_lat = input_extent.yMinimum()
        max_lon = input_extent.xMaximum()
        max_lat = input_extent.yMaximum()

        # Validate numeric rectangle bounds
        if not (min_lon < max_lon and min_lat < max_lat):
            raise QgsProcessingException(self.tr("Provided extent has invalid numeric bounds."))

        # Derive local TM lon_0 from bbox center
        center_lon = (min_lon + max_lon) / 2.0

        # 1) Generate protoblocks w/ sidewalk info via existing algorithm
        feedback.pushInfo(self.tr("Generating protoblocks with sidewalk info..."))
        proto_result = processing.run(
            "sidewalkreator_algorithms_provider:generateprotoblocksfrombbox",
            {
                "EXTENT": input_extent,  # already 4326
                "TIMEOUT": timeout,
                "OUTPUT_PROTOBLOCKS": "memory:protoblocks_from_bbox",
            },
            context=context,
            feedback=feedback,
        )

        protoblocks_4326 = proto_result.get("OUTPUT_PROTOBLOCKS")
        if not isinstance(protoblocks_4326, QgsVectorLayer):
            protoblocks_4326 = QgsVectorLayer(protoblocks_4326, "protoblocks", "ogr")

        if not protoblocks_4326 or not protoblocks_4326.isValid() or protoblocks_4326.featureCount() == 0:
            # Prepare empty outputs
            (sink_cross, out_id_cross) = self.parameterAsSink(
                parameters,
                self.OUTPUT_CROSSINGS,
                context,
                QgsFields([QgsField("crossing_id", QVariant.Int), QgsField("length", QVariant.Double), QgsField("type", QVariant.String)]),
                QgsWkbTypes.LineString,
                crs_4326,
            )
            (sink_kerb, out_id_kerb) = self.parameterAsSink(
                parameters,
                self.OUTPUT_KERBS,
                context,
                QgsFields([QgsField("kerb_id", QVariant.Int), QgsField("crossing_id", QVariant.Int), QgsField("type", QVariant.String)]),
                QgsWkbTypes.Point,
                crs_4326,
            )
            return {self.OUTPUT_CROSSINGS: out_id_cross, self.OUTPUT_KERBS: out_id_kerb}

        # Reproject protoblocks to local TM to work in meters
        protoblocks_local, local_tm_crs = reproject_layer_localTM(
            protoblocks_4326, None, "protoblocks_local_tm", lgt_0=center_lon
        )

        # Filter only protoblocks with existing sidewalks
        has_sw_idx = protoblocks_local.fields().indexOf("existing_sidewalks")
        if has_sw_idx < 0:
            raise QgsProcessingException(self.tr("Protoblocks layer missing 'existing_sidewalks' attribute."))

        # Build feature list and spatial index
        pblist = []
        for f in protoblocks_local.getFeatures():
            try:
                if bool(f[has_sw_idx]):
                    pblist.append(QgsFeature(f))
            except Exception:
                continue

        if not pblist:
            feedback.pushInfo(self.tr("No protoblocks with existing sidewalks found."))
        else:
            feedback.pushInfo(self.tr(f"Eligible protoblocks with sidewalks: {len(pblist)}"))

        # Build spatial index only for protoblocks that have existing sidewalks
        pb_by_id = {f.id(): f for f in pblist}
        req = QgsFeatureRequest()
        req.setFilterFids(list(pb_by_id.keys()))
        idx = QgsSpatialIndex(protoblocks_local.getFeatures(req))

        # 2) Fetch all OSM crossings in bbox (once)
        feedback.pushInfo(self.tr("Fetching OSM crossings in BBOX..."))
        query_str = osm_query_string_by_bbox(
            min_lat, min_lon, max_lat, max_lon, interest_key="highway", node=True, way=False, relation=False, interest_value="crossing"
        )
        crossings_geojson_path = get_osm_data(
            query_str, "osm_crossings_bbox_algo", geomtype="Point", timeout=timeout, return_as_string=False
        )
        crossings_pts_4326 = None
        if crossings_geojson_path:
            crossings_pts_4326 = QgsVectorLayer(crossings_geojson_path, "osm_crossings_4326", "ogr")

        # Reproject crossings to local TM for proximity tests
        crossings_pts_local = None
        if crossings_pts_4326 and crossings_pts_4326.isValid() and crossings_pts_4326.featureCount() > 0:
            crossings_pts_local, _ = reproject_layer_localTM(
                crossings_pts_4326, None, "osm_crossings_local", lgt_0=center_lon
            )

        crossings_index = None
        if crossings_pts_local and crossings_pts_local.isValid() and crossings_pts_local.featureCount() > 0:
            crossings_index = QgsSpatialIndex(crossings_pts_local.getFeatures())

        # 2b) Fetch existing sidewalks (OSM ways: highway=footway AND footway=sidewalk)
        sidewalks_query = osm_query_string_by_bbox(
            min_lat, min_lon, max_lat, max_lon, interest_key="highway", node=False, way=True, relation=False, interest_value="footway"
        )
        sidewalks_path = get_osm_data(
            sidewalks_query, "osm_sidewalks_bbox_algo", geomtype="LineString", timeout=timeout, return_as_string=False
        )
        sidewalks_lines_local = None
        if sidewalks_path:
            sw_4326 = QgsVectorLayer(sidewalks_path, "osm_sidewalks_4326", "ogr")
            if sw_4326 and sw_4326.isValid() and sw_4326.featureCount() > 0:
                # Filter to footway=sidewalk
                footway_idx = sw_4326.fields().lookupField("footway")
                highway_idx = sw_4326.fields().lookupField("highway")
                filtered = QgsVectorLayer(f"LineString?crs=EPSG:4326", "filtered_sidewalks", "memory")
                fdp = filtered.dataProvider()
                fdp.addAttributes(sw_4326.fields())
                filtered.updateFields()
                feats = []
                for f in sw_4326.getFeatures():
                    try:
                        if (
                            (highway_idx == -1 or str(f[highway_idx]).lower() == "footway")
                            and footway_idx != -1
                            and str(f[footway_idx]).lower() == "sidewalk"
                        ):
                            nf = QgsFeature(filtered.fields())
                            nf.setGeometry(f.geometry())
                            nf.setAttributes(f.attributes())
                            feats.append(nf)
                    except Exception:
                        continue
                if feats:
                    fdp.addFeatures(feats)
                    filtered.updateExtents()
                    sidewalks_lines_local, _ = reproject_layer_localTM(
                        filtered, None, "osm_sidewalks_local", lgt_0=center_lon
                    )
        # Build a spatial index for sidewalks
        sidewalks_index = None
        if sidewalks_lines_local and sidewalks_lines_local.isValid() and sidewalks_lines_local.featureCount() > 0:
            sidewalks_index = QgsSpatialIndex(sidewalks_lines_local.getFeatures())

        # Prepare working layers in local TM
        crossings_local = QgsVectorLayer(
            f"LineString?crs={local_tm_crs.authid()}", "generated_crossings_local_tm", "memory"
        )
        kerbs_local = QgsVectorLayer(
            f"Point?crs={local_tm_crs.authid()}", "generated_kerbs_local_tm", "memory"
        )
        # Ensure CRS is set even if authid() is empty (custom local TM)
        if not crossings_local.crs().isValid() or crossings_local.crs().authid() == "":
            crossings_local.setCrs(local_tm_crs)
        if not kerbs_local.crs().isValid() or kerbs_local.crs().authid() == "":
            kerbs_local.setCrs(local_tm_crs)
        cross_dp = crossings_local.dataProvider()
        kerb_dp = kerbs_local.dataProvider()
        cross_dp.addAttributes(
            [
                QgsField("crossing_id", QVariant.Int),
                QgsField("length", QVariant.Double),
                QgsField("type", QVariant.String),
            ]
        )
        kerb_dp.addAttributes(
            [
                QgsField("kerb_id", QVariant.Int),
                QgsField("crossing_id", QVariant.Int),
                QgsField("type", QVariant.String),
            ]
        )
        crossings_local.updateFields()
        kerbs_local.updateFields()

        # Build index of all protoblocks for endpoint intersection checks
        all_pb_index = QgsSpatialIndex(protoblocks_local.getFeatures())

        # Helper to extract shared edge line geometries between two polygons
        def shared_line_geoms(geom_a: QgsGeometry, geom_b: QgsGeometry):
            def _collect_lines(g: QgsGeometry):
                lines = []
                if not g or g.isEmpty():
                    return lines
                try:
                    if g.type() == QgsWkbTypes.LineGeometry:
                        if g.isMultipart():
                            for pl in g.asMultiPolyline():
                                if pl:
                                    lines.append(QgsGeometry.fromPolylineXY(pl))
                        else:
                            pl = g.asPolyline()
                            if pl:
                                lines.append(QgsGeometry.fromPolylineXY(pl))
                        return lines
                    # Geometry collections: iterate parts and harvest line parts
                    try:
                        for part in g.constParts():
                            if part.type() == QgsWkbTypes.LineGeometry:
                                if part.isMultipart():
                                    for pl in part.asMultiPolyline():
                                        if pl:
                                            lines.append(QgsGeometry.fromPolylineXY(pl))
                                else:
                                    pl = part.asPolyline()
                                    if pl:
                                        lines.append(QgsGeometry.fromPolylineXY(pl))
                    except Exception:
                        pass
                except Exception:
                    return lines
                return lines

            # First, intersect boundaries (preferred)
            try:
                inter = geom_a.boundary().intersection(geom_b.boundary())
                lines = _collect_lines(inter)
                if lines:
                    return lines
            except Exception:
                pass

            # Fallback: intersect full polygons and extract any line parts (shared edges)
            try:
                inter2 = geom_a.intersection(geom_b)
                lines = _collect_lines(inter2)
                return lines
            except Exception:
                return []

        def proto_count_at_point(pt: QgsPointXY, buffer_radius=0.75) -> int:
            # Count distinct protoblocks whose geometry intersects a small buffer around pt
            gbuf = QgsGeometry.fromPointXY(pt).buffer(buffer_radius, 8)
            rect = gbuf.boundingBox()
            cand = all_pb_index.intersects(rect)
            if not cand:
                return 0
            req = QgsFeatureRequest()
            req.setFilterFids(cand)
            seen = set()
            for f in protoblocks_local.getFeatures(req):
                if f.id() in seen:
                    continue
                try:
                    if f.geometry().intersects(gbuf):
                        seen.add(f.id())
                except Exception:
                    continue
            return len(seen)

        crossing_id = 1
        kerb_id = 1
        processed_pairs = 0
        created_crossings = 0
        skipped_existing = 0

        # Iterate pairs via spatial index
        for pa in pblist:
            if feedback.isCanceled():
                break
            geom_a = pa.geometry()
            if not geom_a or geom_a.isEmpty():
                continue
            # Candidate neighbors
            rect = geom_a.boundingBox()
            cand_ids = idx.intersects(rect)
            for fid in cand_ids:
                if fid == pa.id():
                    continue
                pb = pb_by_id.get(fid)
                if pb is None:
                    continue
                # Ensure single processing per unordered pair (use id order)
                if pa.id() > pb.id():
                    continue
                geom_b = pb.geometry()
                if not geom_b or geom_b.isEmpty():
                    continue

                for sh in shared_line_geoms(geom_a, geom_b):
                    if not sh or sh.isEmpty():
                        continue
                    seg_len = sh.length()
                    if seg_len < min_shared_len:
                        continue
                    processed_pairs += 1

                    # Determine center point and local tangent — prefer shared-edge endpoint near an intersection
                    eps = min(1.0, seg_len * 0.01)
                    use_t = seg_len / 2.0
                    if require_intersection:
                        p0 = sh.interpolate(0.0).asPoint()
                        p1 = sh.interpolate(seg_len).asPoint()
                        c0 = proto_count_at_point(p0)
                        c1 = proto_count_at_point(p1)
                        use_t = 0.0 if c0 >= c1 else seg_len
                    mid_point = sh.interpolate(use_t)
                    if not mid_point or mid_point.isEmpty():
                        continue
                    mid_pt = mid_point.asPoint()

                    # Estimate direction around use_t on the shared edge
                    p_before = sh.interpolate(max(0.0, use_t - eps)).asPoint()
                    p_after = sh.interpolate(min(seg_len, use_t + eps)).asPoint()
                    dx = p_after.x() - p_before.x()
                    dy = p_after.y() - p_before.y()
                    if dx == 0 and dy == 0:
                        continue
                    # Normal vector (perpendicular)
                    nx, ny = -dy, dx
                    norm = math.hypot(nx, ny)
                    if norm == 0:
                        continue
                    nx /= norm
                    ny /= norm

                    # Optional: require intersection-like topology at endpoints
                    if require_intersection:
                        p0 = sh.interpolate(0.0).asPoint()
                        p1 = sh.interpolate(seg_len).asPoint()
                        c0 = proto_count_at_point(p0)
                        c1 = proto_count_at_point(p1)
                        if c0 < endpoint_min_blocks or c1 < endpoint_min_blocks:
                            # Likely a mid-block shared edge; skip to reduce false positives
                            continue

                    # Check for existing crossing near shared edge using OSM nodes
                    found_existing = False
                    if crossings_index and crossings_pts_local and crossings_pts_local.isValid():
                        radius = max(2.0, seg_len / 2.0)
                        search_rect = QgsRectangle(
                            mid_pt.x() - radius, mid_pt.y() - radius, mid_pt.x() + radius, mid_pt.y() + radius
                        )
                        cand_cross_ids = crossings_index.intersects(search_rect)
                        if cand_cross_ids:
                            # Distance to shared line threshold (m)
                            for cf in crossings_pts_local.getFeatures():
                                if cf.id() not in cand_cross_ids:
                                    continue
                                d = sh.distance(cf.geometry())
                                if d <= 2.0:  # within 2m from shared edge
                                    found_existing = True
                                    break
                    if found_existing:
                        skipped_existing += 1
                        continue

                    # Build a longer probe line to intersect sidewalks on both sides
                    probe_len = max(crossing_len_m * 4.0, 30.0)
                    p_neg_far = QgsPointXY(mid_pt.x() - nx * probe_len, mid_pt.y() - ny * probe_len)
                    p_pos_far = QgsPointXY(mid_pt.x() + nx * probe_len, mid_pt.y() + ny * probe_len)
                    probe_line = QgsGeometry.fromPolylineXY([p_neg_far, mid_pt, p_pos_far])

                    # Find intersection with sidewalks on both sides of mid_pt
                    def pick_side_intersection(side_sign):
                        # side_sign: -1 for negative, 1 for positive side
                        best = None
                        best_d = None
                        if not sidewalks_lines_local or not sidewalks_index:
                            return None
                        rect = probe_line.boundingBox()
                        cand = sidewalks_index.intersects(rect)
                        if not cand:
                            return None
                        req = QgsFeatureRequest(); req.setFilterFids(cand)
                        for sw in sidewalks_lines_local.getFeatures(req):
                            try:
                                inter = probe_line.intersection(sw.geometry())
                                if not inter or inter.isEmpty():
                                    continue
                                pts = []
                                if inter.type() == QgsWkbTypes.PointGeometry:
                                    if inter.isMultipart():
                                        pts = inter.asMultiPoint()
                                    else:
                                        pts = [inter.asPoint()]
                                # If overlapping (line result), skip to avoid degenerate cases
                                for pt in pts:
                                    vx = pt.x() - mid_pt.x(); vy = pt.y() - mid_pt.y()
                                    # Projection along normal
                                    proj = vx * nx + vy * ny
                                    if side_sign < 0 and proj >= 0:
                                        continue
                                    if side_sign > 0 and proj <= 0:
                                        continue
                                    d = abs(proj)
                                    if best is None or d < best_d:
                                        best = pt; best_d = d
                            except Exception:
                                continue
                        return best

                    pt_neg = pick_side_intersection(-1)
                    pt_pos = pick_side_intersection(1)

                    # If missing any side intersection, fallback to nominal length
                    if pt_neg is None or pt_pos is None:
                        half_len = crossing_len_m / 2.0
                        pA = QgsPointXY(mid_pt.x() - nx * half_len, mid_pt.y() - ny * half_len)
                        pE = QgsPointXY(mid_pt.x() + nx * half_len, mid_pt.y() + ny * half_len)
                    else:
                        pA = QgsPointXY(pt_neg.x(), pt_neg.y())
                        pE = QgsPointXY(pt_pos.x(), pt_pos.y())

                    # Kerb points B and D along halves towards center
                    def interp_point(p1: QgsPointXY, p2: QgsPointXY, t: float) -> QgsPointXY:
                        return QgsPointXY(p1.x() + (p2.x() - p1.x()) * t, p1.y() + (p2.y() - p1.y()) * t)

                    kerb_t = kerb_perc / 100.0
                    pC = QgsPointXY(mid_pt.x(), mid_pt.y())
                    pB = interp_point(pA, pC, kerb_t)
                    pD = interp_point(pE, pC, kerb_t)

                    # Validate that endpoints fall within opposite protoblocks (tolerant)
                    pA_g = QgsGeometry.fromPointXY(pA)
                    pE_g = QgsGeometry.fromPointXY(pE)
                    tol = 0.25
                    a_buf = geom_a.buffer(tol, 8)
                    b_buf = geom_b.buffer(tol, 8)
                    pair_ok = (a_buf.contains(pA_g) and b_buf.contains(pE_g)) or (b_buf.contains(pA_g) and a_buf.contains(pE_g))
                    if not pair_ok:
                        continue

                    crossing_geom = QgsGeometry.fromPolylineXY([pA, pB, pC, pD, pE])
                    crossing_feat = QgsFeature(crossings_local.fields())
                    crossing_feat.setGeometry(crossing_geom)
                    crossing_feat.setAttributes([crossing_id, crossing_geom.length(), "missing_inferred"])
                    cross_dp.addFeatures([crossing_feat])

                    kerbB_feat = QgsFeature(kerbs_local.fields())
                    kerbB_feat.setGeometry(QgsGeometry.fromPointXY(pB))
                    kerbB_feat.setAttributes([kerb_id, crossing_id, "crossing_kerb"])
                    kerb_id += 1
                    kerbD_feat = QgsFeature(kerbs_local.fields())
                    kerbD_feat.setGeometry(QgsGeometry.fromPointXY(pD))
                    kerbD_feat.setAttributes([kerb_id, crossing_id, "crossing_kerb"])
                    kerb_id += 1
                    kerb_dp.addFeatures([kerbB_feat, kerbD_feat])

                    crossing_id += 1
                    created_crossings += 1

        feedback.pushInfo(self.tr(f"Processed shared edges: {processed_pairs}, created crossings: {created_crossings}, skipped (existing): {skipped_existing}"))

        # Reproject outputs to EPSG:4326
        feedback.pushInfo(self.tr("Reprojecting outputs to EPSG:4326..."))
        crossings_4326 = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": crossings_local,
                "TARGET_CRS": crs_4326,
                "OUTPUT": "memory:crossings_4326",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]
        kerbs_4326 = processing.run(
            "native:reprojectlayer",
            {
                "INPUT": kerbs_local,
                "TARGET_CRS": crs_4326,
                "OUTPUT": "memory:kerbs_4326",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # Prepare sinks
        (sink_cross, out_id_cross) = self.parameterAsSink(
            parameters,
            self.OUTPUT_CROSSINGS,
            context,
            crossings_4326.fields(),
            crossings_4326.wkbType(),
            crossings_4326.crs(),
        )
        if sink_cross and crossings_4326 and crossings_4326.isValid():
            for f in crossings_4326.getFeatures():
                sink_cross.addFeature(f, QgsFeatureSink.FastInsert)

        (sink_kerb, out_id_kerb) = self.parameterAsSink(
            parameters,
            self.OUTPUT_KERBS,
            context,
            kerbs_4326.fields(),
            kerbs_4326.wkbType(),
            kerbs_4326.crs(),
        )
        if sink_kerb and kerbs_4326 and kerbs_4326.isValid():
            for f in kerbs_4326.getFeatures():
                sink_kerb.addFeature(f, QgsFeatureSink.FastInsert)

        return {self.OUTPUT_CROSSINGS: out_id_cross, self.OUTPUT_KERBS: out_id_kerb}

    def postProcessAlgorithm(self, context, feedback):
        return {}
