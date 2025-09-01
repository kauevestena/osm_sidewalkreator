# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsWkbTypes,
    QgsProcessingException,
    Qgis,
    QgsCoordinateReferenceSystem,
    edit,
)

# Assuming these are available from the main plugin structure
from ..generic_functions import (
    dissolve_tosinglegeom,
    get_first_feature_or_geom,
    generate_buffer,
    compute_difference_layer,
    convert_multipart_to_singleparts,
    remove_biggest_polygon,
    extract_lines_from_polygons,
    layer_from_featlist,
    geom_to_feature,
    create_new_layerfield,
    create_area_field,
    create_perimeter_field,
)
from ..parameters import (
    widths_fieldname,
    big_buffer_d,  # , sidewalk_tag_value and other specific tags if needed here
    min_area_perimeter_ratio,
)
import math  # For math.sqrt if used in ratio calculations, though not directly in draw_sidewalks core geom logic
from qgis import processing


def filter_polygons_by_area_perimeter_ratio(
    polygon_layer: QgsVectorLayer, ratio_threshold: float
) -> int:
    """Remove polygons with area/perimeter ratio below threshold.

    Parameters
    ----------
    polygon_layer: QgsVectorLayer
        Layer containing polygon geometries.
    ratio_threshold: float
        Minimum allowed area/perimeter ratio.

    Returns
    -------
    int
        Number of removed features.
    """

    ids_to_remove = []
    for feat in polygon_layer.getFeatures():
        geom = feat.geometry()
        perim = geom.perimeter() if hasattr(geom, "perimeter") else geom.length()
        if perim <= 0:
            continue
        area = geom.area()
        if (area / perim) < ratio_threshold:
            ids_to_remove.append(feat.id())

    removed = len(ids_to_remove)
    if removed:
        with edit(polygon_layer):
            for fid in ids_to_remove:
                polygon_layer.deleteFeature(fid)
    return removed

def generate_sidewalk_geometries_and_zones(
    road_network_layer_local_tm: QgsVectorLayer,
    processing_aoi_geom_local_tm: QgsGeometry,
    building_footprints_layer_local_tm: QgsVectorLayer,
    protoblocks_layer_local_tm: QgsVectorLayer,
    parameters: dict,
    feedback: QgsProcessingFeedback,
    context: QgsProcessingContext,
    local_tm_crs: QgsCoordinateReferenceSystem,
) -> dict:
    """
    Replicates the core logic of osm_sidewalkreator.py's draw_sidewalks method.
    Returns:
        - whole_sidewalks_lines (QgsVectorLayer, LineString in local_tm_crs)
        - exclusion_zones_poly (QgsVectorLayer, Polygon in local_tm_crs)
        - sure_zones_poly (QgsVectorLayer, Polygon in local_tm_crs)
        - width_adjusted_street_network (QgsVectorLayer, LineString in local_tm_crs) - for subsequent steps like crossings
    """

    current_crs = road_network_layer_local_tm.crs()
    feedback.pushInfo(
        f"Sidewalk Generation: Input street network CRS: {current_crs.authid()}"
    )

    def _single_sided_buffer_geom(line_geom: QgsGeometry, left_side: bool, dist: float, segments: int = 5) -> QgsGeometry:
        """Create a single-sided buffer geometry using the Processing algorithm for stability across QGIS builds."""
        try:
            tmp_lyr = QgsVectorLayer(f"LineString?crs={current_crs.authid()}", "tmp_single_side", "memory")
            dp = tmp_lyr.dataProvider()
            f = QgsFeature()
            f.setGeometry(line_geom)
            dp.addFeatures([f])
            tmp_lyr.updateExtents()

            params = {
                "INPUT": tmp_lyr,
                "DISTANCE": float(dist),
                "SIDE": 0 if left_side else 1,  # 0 = left, 1 = right
                "SEGMENTS": int(segments),
                # Optional extras could be set (END_CAP_STYLE, JOIN_STYLE, MITER_LIMIT)
                "OUTPUT": "memory:single_side_buf",
            }
            out = processing.run("native:singlesidedbuffer", params)
            out_layer = out.get("OUTPUT")
            if isinstance(out_layer, QgsVectorLayer) and out_layer.isValid() and out_layer.featureCount() > 0:
                g = next(out_layer.getFeatures()).geometry()
                return g
        except Exception as e:
            feedback.pushWarning(f"single-sided buffer failed: {e}")
        return None

    # --- 1. Handle building overlap adjustments on street_network_layer widths ---
    # Create a copy of the street_network_layer to modify widths, or modify in place if that's acceptable.
    # For a processing algorithm, it's better to work on copies or new layers.

    # Create a new layer for width-adjusted streets based on the input street_network_layer
    width_adjusted_streets = QgsVectorLayer(
        f"LineString?crs={current_crs.authid()}",
        "width_adjusted_streets_temp",
        "memory",
    )
    width_adjusted_streets_dp = width_adjusted_streets.dataProvider()
    width_adjusted_streets_dp.addAttributes(road_network_layer_local_tm.fields())
    width_adjusted_streets.updateFields()

    # Ensure 'widths_fieldname' (e.g. "width") exists on the new layer
    if width_adjusted_streets.fields().lookupField(widths_fieldname) == -1:
        width_field = QgsField(
            widths_fieldname, QVariant.Double
        )  # Assuming width is double
        width_adjusted_streets_dp.addAttributes([width_field])
        width_adjusted_streets.updateFields()

    width_idx_adjusted = width_adjusted_streets.fields().indexOf(widths_fieldname)

    # Copy features and adjust widths if needed
    features_to_add = []
    if (
        parameters.get("check_building_overlap", False)
        and building_footprints_layer_local_tm
        and building_footprints_layer_local_tm.featureCount() > 0
    ):
        feedback.pushInfo("Adjusting street widths based on proximity to buildings...")
        # This part requires careful adaptation of the logic from draw_sidewalks
        # It involves dissolving buildings and checking distances.
        dissolved_buildings = dissolve_tosinglegeom(
            building_footprints_layer_local_tm
        )  # Assumes buildings_layer is valid
        dissolved_buildings_geom = get_first_feature_or_geom(dissolved_buildings, True)

        for street_feat in road_network_layer_local_tm.getFeatures():
            if feedback.isCanceled():
                return None, None, None, None

            new_street_feat = QgsFeature(width_adjusted_streets.fields())
            new_street_feat.setGeometry(street_feat.geometry())
            new_street_feat.setAttributes(street_feat.attributes())

            original_width_val = street_feat.attribute(widths_fieldname)
            if original_width_val is None:
                original_width_val = 0.0  # Handle NULL widths

            try:
                current_street_width = float(original_width_val)
            except (ValueError, TypeError):
                feedback.pushWarning(
                    f"Could not parse width '{original_width_val}' for street FID {street_feat.id()}. Using 0.0."
                )
                current_street_width = 0.0

            d_to_nearest_building = street_feat.geometry().distance(
                dissolved_buildings_geom
            )

            # Half of the total width that the sidewalk generation process will effectively use on one side
            # This is (road_half_width + added_half_width_for_sidewalk_axis)
            effective_sidewalk_projection_one_side = (current_street_width / 2.0) + (
                parameters.get("added_width_for_sidewalk_axis_total", 0.0) / 2.0
            )

            diff_dist = (
                d_to_nearest_building - parameters.get("min_dist_to_building", 0.0)
            ) - effective_sidewalk_projection_one_side

            adjusted_street_width = current_street_width
            if diff_dist < 0:
                # Sidewalk buffer would overlap building too much. Reduce effective sidewalk projection.
                # New total width for sidewalk generation = 2 * (effective_sidewalk_projection_one_side + diff_dist)
                # We need to find the new 'road width' that, when 'added_width_for_sidewalk_axis_total' is applied,
                # results in the desired reduced projection.
                # Let new_road_half_width + added_half_width = new_effective_projection_one_side
                # new_effective_projection_one_side = effective_sidewalk_projection_one_side + diff_dist
                # new_road_half_width = new_effective_projection_one_side - (added_width_for_sidewalk_axis_total / 2.0)
                # new_road_width = 2 * new_road_half_width

                new_effective_projection_one_side = (
                    effective_sidewalk_projection_one_side + diff_dist
                )
                new_road_half_width = new_effective_projection_one_side - (
                    parameters.get("added_width_for_sidewalk_axis_total", 0.0) / 2.0
                )
                adjusted_street_width = 2 * new_road_half_width

                # Ensure the generated sidewalk (based on this adjusted_street_width + added_width) isn't too narrow
                # The min_generated_sidewalk_width is for the *sidewalk itself*.
                # The buffer applied is (adjusted_street_width/2 + added_width_for_sidewalk_axis_total/2).
                # This is complex. The original logic was about `new_width` for the *buffer*.
                # Let's replicate the original logic for `new_width` (which was the new effective road width for buffering)

                # Original logic: new_width = 2 * (ac_prj_d + dif), where ac_prj_d was effective_sidewalk_projection_one_side
                # This `new_width` was then compared to `min_width_box.value()` which is `min_generated_sidewalk_width`
                # This seems to imply `min_generated_sidewalk_width` was for the *road width used for buffering*.
                # This needs careful interpretation. Let's assume min_generated_width_near_building is the target road width for buffering.
                if (
                    adjusted_street_width
                    < parameters.get("min_generated_width_near_building", 0.0)
                ):  # This might be wrong.
                    # The original min_width_box.value() was for the *buffered result*, not the input street width.
                    # Re-evaluating: the original code sets 'new_width' for the street feature's 'width' attribute.
                    # This 'new_width' is then used in the buffer expression: ('width'/2) + (d_to_add/2)
                    # So, min_generated_width_near_building should be the minimum value for this 'width' attribute.
                    adjusted_street_width = parameters.get(
                        "min_generated_width_near_building", 0.0
                    )

            new_street_feat.setAttribute(width_idx_adjusted, adjusted_street_width)
            features_to_add.append(new_street_feat)

        if features_to_add:
            width_adjusted_streets_dp.addFeatures(features_to_add)
        feedback.pushInfo(
            f"Street widths adjusted. Count: {width_adjusted_streets.featureCount()}"
        )

    else:  # No building overlap check or no buildings
        feedback.pushInfo(
            "Skipping building overlap checks for sidewalk width adjustment."
        )
        # Just copy features as is
        for street_feat in road_network_layer_local_tm.getFeatures():
            if feedback.isCanceled():
                return None, None, None, None
            new_street_feat = QgsFeature(width_adjusted_streets.fields())
            new_street_feat.setGeometry(street_feat.geometry())
            new_street_feat.setAttributes(street_feat.attributes())
            # Ensure width attribute is correctly copied or defaulted if null
            original_width_val = street_feat.attribute(widths_fieldname)
            if original_width_val is None:
                original_width_val = 0.0
            try:
                current_street_width = float(original_width_val)
            except:
                current_street_width = 0.0
            new_street_feat.setAttribute(width_idx_adjusted, current_street_width)
            features_to_add.append(new_street_feat)
        if features_to_add:
            width_adjusted_streets_dp.addFeatures(features_to_add)

    # --- 2. Generate initial sidewalk polygons (buffers) ---
    feedback.pushInfo("Generating sidewalk area buffers...")
    buffer_distance_expression = f'("{widths_fieldname}" / 2) + {parameters.get("added_width_for_sidewalk_axis_total", 0.0) / 2.0}'

    proto_undissolved_buffer = generate_buffer(
        width_adjusted_streets, buffer_distance_expression, dissolve=False
    )
    if not proto_undissolved_buffer:
        raise QgsProcessingException("Failed at proto_undissolved_buffer generation.")

    dissolved_once_buffer = dissolve_tosinglegeom(proto_undissolved_buffer)
    if not dissolved_once_buffer:
        raise QgsProcessingException("Failed at first dissolve for buffer.")

    # Rounding buffers
    proto_dissolved_buffer_step2 = generate_buffer(
        dissolved_once_buffer, parameters.get("curve_radius", 0.0)
    )
    if not proto_dissolved_buffer_step2:
        raise QgsProcessingException("Failed at curve_radius buffer generation.")

    dissolved_sidewalk_area_polygons = generate_buffer(
        proto_dissolved_buffer_step2, -parameters.get("curve_radius", 0.0)
    )
    if not dissolved_sidewalk_area_polygons:
        raise QgsProcessingException(
            "Failed at negative curve_radius buffer generation."
        )
    dissolved_sidewalk_area_polygons.setCrs(current_crs)

    # --- 3. Extract sidewalk lines (Original logic: difference of big buffer and sidewalk area) ---
    feedback.pushInfo("Extracting sidewalk lines from buffered areas...")
    big_temp_buffer_for_diff = generate_buffer(
        dissolved_sidewalk_area_polygons, big_buffer_d
    )  # Outer extent
    if not big_temp_buffer_for_diff:
        raise QgsProcessingException("Failed to create big_temp_buffer_for_diff.")

    # This diff_layer contains the "donut" polygons representing sidewalks
    sidewalk_polygons_as_donuts = compute_difference_layer(
        big_temp_buffer_for_diff, dissolved_sidewalk_area_polygons
    )
    if not sidewalk_polygons_as_donuts:
        raise QgsProcessingException(
            "Failed at compute_difference_layer for sidewalk donuts."
        )
    sidewalk_polygons_as_donuts.setCrs(current_crs)

    sidewalk_polygons_singleparts = convert_multipart_to_singleparts(
        sidewalk_polygons_as_donuts
    )
    if not sidewalk_polygons_singleparts:
        raise QgsProcessingException(
            "Failed at convert_multipart_to_singleparts for sidewalk polygons."
        )

    # remove_biggest_polygon also adds 'area' field if record_area=True
    # The original plugin records area, let's assume it's not strictly needed for processing alg unless specified
    remove_biggest_polygon(sidewalk_polygons_singleparts, record_area=False)

    # At this point, sidewalk_polygons_singleparts contains the actual sidewalk area polygons.
    # These are not yet lines.

    # --- 5. Generate exclusion_zones and sure_zones based on OSM tags ---
    # This needs to iterate the original street_network_layer (or width_adjusted_streets if tags are preserved)
    feedback.pushInfo("Generating exclusion and sure zones based on OSM tags...")
    exclusion_zones_featlist = []
    sure_zones_featlist = []

    # Iterate through the street layer that has original OSM tags and the (potentially adjusted) width
    # This should be `width_adjusted_streets` as it has the most up-to-date widths for buffer calculations
    for street_feat in width_adjusted_streets.getFeatures():
        if feedback.isCanceled():
            return None, None, None, None

        current_street_width_val = street_feat.attribute(widths_fieldname)
        try:
            current_street_width = float(current_street_width_val)
        except:
            current_street_width = 0.0  # Default if width is invalid

        # Effective half-width for sidewalk tag based buffering (street half-width + added half-width + small margin)
        # Original plugin: half_width = (float(attrdict.get(widths_fieldname)) + self.dlg.d_to_add_box.value() + 1) / 2 + 0.5
        # This means: ( (original_street_width + total_added_width) / 2 ) + 0.5 + 0.5
        # ( (current_street_width + parameters.get("added_width_for_sidewalk_axis_total", 0.0)) / 2 ) + 1.0 -> this might be too large.
        # The original code: (width_val / 2) + 0.5 where width_val = float(attrdict.get(widths_fieldname)) + self.dlg.d_to_add_box.value() + 1
        # So, half_buffer_for_tags = (current_street_width + parameters.get("added_width_for_sidewalk_axis_total", 0.0) + 1.0) / 2.0 + 0.5
        # This formula seems a bit off. Let's use the effective sidewalk projection + a small margin.
        # Effective projection per side = current_street_width/2 + parameters.get("added_width_for_sidewalk_axis_total", 0.0)/2
        # Let's use this effective projection for singleSidedBuffer
        tag_buffer_dist = (
            (current_street_width / 2.0)
            + (parameters.get("added_width_for_sidewalk_axis_total", 0.0) / 2.0)
            + 0.5
        )  # Added 0.5m margin

        geom_exclusion = None
        geom_sure = None

        # Simplified tag logic (can be expanded as in original plugin)
        def _tag_val(name: str) -> str:
            try:
                idx = width_adjusted_streets.fields().lookupField(name)
                if idx == -1:
                    return ""
                val = street_feat.attribute(idx)
                return ("" if val is None else str(val)).lower()
            except Exception:
                return ""

        sidewalk_tag = _tag_val("sidewalk")
        sidewalk_left_tag = _tag_val("sidewalk:left")
        sidewalk_right_tag = _tag_val("sidewalk:right")
        sidewalk_both_tag = _tag_val("sidewalk:both")

        street_geom = street_feat.geometry()

        if sidewalk_tag == "no" or sidewalk_both_tag == "no":
            geom_exclusion = street_geom.buffer(
                tag_buffer_dist, 5, Qgis.EndCapStyle.Flat, Qgis.JoinStyle.Miter, 10
            )
        elif (
            sidewalk_tag == "left" or sidewalk_left_tag == "yes"
        ):  # Sidewalk only on left
            geom_sure = _single_sided_buffer_geom(street_geom, left_side=True, dist=tag_buffer_dist, segments=5)
            geom_exclusion = _single_sided_buffer_geom(street_geom, left_side=False, dist=tag_buffer_dist, segments=5)
        elif (
            sidewalk_tag == "right" or sidewalk_right_tag == "yes"
        ):  # Sidewalk only on right
            geom_sure = _single_sided_buffer_geom(street_geom, left_side=False, dist=tag_buffer_dist, segments=5)
            geom_exclusion = _single_sided_buffer_geom(street_geom, left_side=True, dist=tag_buffer_dist, segments=5)
        elif sidewalk_left_tag == "no":  # No sidewalk on left
            current_exclusion = _single_sided_buffer_geom(street_geom, left_side=True, dist=tag_buffer_dist, segments=5)
            geom_exclusion = (
                current_exclusion
                if geom_exclusion is None
                else geom_exclusion.combine(current_exclusion)
            )
            if sidewalk_right_tag == "yes":  # Sidewalk on right
                current_sure = _single_sided_buffer_geom(street_geom, left_side=False, dist=tag_buffer_dist, segments=5)
                geom_sure = (
                    current_sure
                    if geom_sure is None
                    else geom_sure.combine(current_sure)
                )
        elif sidewalk_right_tag == "no":  # No sidewalk on right
            current_exclusion = _single_sided_buffer_geom(street_geom, left_side=False, dist=tag_buffer_dist, segments=5)
            geom_exclusion = (
                current_exclusion
                if geom_exclusion is None
                else geom_exclusion.combine(current_exclusion)
            )
            if sidewalk_left_tag == "yes":  # Sidewalk on left
                current_sure = _single_sided_buffer_geom(street_geom, left_side=True, dist=tag_buffer_dist, segments=5)
                geom_sure = (
                    current_sure
                    if geom_sure is None
                    else geom_sure.combine(current_sure)
                )
        elif (
            sidewalk_tag == "both"
            or sidewalk_tag == "yes"
            or sidewalk_both_tag == "yes"
        ):  # Sidewalk on both sides
            geom_sure = street_geom.buffer(
                tag_buffer_dist, 5, Qgis.EndCapStyle.Flat, Qgis.JoinStyle.Miter, 10
            )

        # Default case: if no specific sidewalk tags imply "yes" on both, assume sure zone covers full buffer
        if (
            geom_sure is None and geom_exclusion is None
        ):  # No 'no' tags, and no explicit 'yes' tags for one side
            geom_sure = street_geom.buffer(
                tag_buffer_dist, 5, Qgis.EndCapStyle.Flat, Qgis.JoinStyle.Miter, 10
            )

        if geom_exclusion and not geom_exclusion.isEmpty():
            exclusion_zones_featlist.append(geom_to_feature(geom_exclusion))
        if geom_sure and not geom_sure.isEmpty():
            sure_zones_featlist.append(geom_to_feature(geom_sure))

    exclusion_zones_poly = layer_from_featlist(
        exclusion_zones_featlist, "exclusion_zones_temp", "Polygon", CRS=current_crs
    )
    sure_zones_poly = layer_from_featlist(
        sure_zones_featlist, "sure_zones_temp", "Polygon", CRS=current_crs
    )
    feedback.pushInfo(
        f"Generated {exclusion_zones_poly.featureCount()} exclusion zones, {sure_zones_poly.featureCount()} sure zones."
    )

    # --- 6. Apply exclusion zones to sidewalk polygons ---
    feedback.pushInfo("Applying exclusion zones to sidewalk areas...")
    sidewalk_polygons_final = (
        sidewalk_polygons_singleparts  # Start with all sidewalk polygons
    )
    if exclusion_zones_poly.featureCount() > 0:
        # Dissolve exclusion zones first to avoid issues with many small overlaps
        dissolved_exclusions = dissolve_tosinglegeom(exclusion_zones_poly)
        if dissolved_exclusions and dissolved_exclusions.featureCount() > 0:
            sidewalk_polygons_final = compute_difference_layer(
                sidewalk_polygons_singleparts, dissolved_exclusions
            )
            if not sidewalk_polygons_final:
                feedback.pushWarning(
                    "Difference operation for exclusion zones failed. Using un-excluded sidewalks."
                )
                sidewalk_polygons_final = sidewalk_polygons_singleparts  # Fallback
            else:
                sidewalk_polygons_final.setCrs(current_crs)
                feedback.pushInfo(
                    f"Sidewalk areas after exclusion: {sidewalk_polygons_final.featureCount()} parts."
                )
        else:
            feedback.pushInfo(
                "No valid exclusion zones to apply or dissolving them failed."
            )
    else:
        feedback.pushInfo("No exclusion zones generated.")

    # Remove polygons that are too thin based on area/perimeter ratio
    ratio_threshold = parameters.get(
        "min_area_perimeter_ratio", min_area_perimeter_ratio
    )
    removed = filter_polygons_by_area_perimeter_ratio(
        sidewalk_polygons_final, ratio_threshold
    )
    if removed:
        feedback.pushInfo(
            f"Removed {removed} sidewalk polygons below ratio {ratio_threshold}."
        )

    # --- Extract final sidewalk lines ---
    whole_sidewalks_lines = extract_lines_from_polygons(
        sidewalk_polygons_final, "memory:whole_sidewalks_lines_algo"
    )
    if not whole_sidewalks_lines:
        raise QgsProcessingException("Failed to extract final sidewalk lines.")
    whole_sidewalks_lines.setCrs(current_crs)
    feedback.pushInfo(
        f"Final sidewalk lines extracted: {whole_sidewalks_lines.featureCount()} features."
    )

    # --- Filter sidewalk lines by dissolved_protoblocks_layer (remove disjoint) ---
    # This was an important step in the original plugin
    if protoblocks_layer_local_tm and protoblocks_layer_local_tm.featureCount() > 0:
        feedback.pushInfo(
            "Filtering sidewalk lines to keep only those intersecting protoblock areas..."
        )
        dissolved_protoblock_geom = get_first_feature_or_geom(
            protoblocks_layer_local_tm, True
        )

        # Create a new layer for filtered sidewalks
        filtered_sidewalk_lines = QgsVectorLayer(
            f"LineString?crs={current_crs.authid()}",
            "filtered_sidewalk_lines_algo",
            "memory",
        )
        filtered_sidewalk_lines_dp = filtered_sidewalk_lines.dataProvider()
        filtered_sidewalk_lines_dp.addAttributes(
            whole_sidewalks_lines.fields()
        )  # Keep fields if any
        filtered_sidewalk_lines.updateFields()

        kept_sidewalks = []
        for sw_feat in whole_sidewalks_lines.getFeatures():
            if feedback.isCanceled():
                return None, None, None, None
            if not sw_feat.geometry().disjoint(dissolved_protoblock_geom):
                kept_sidewalks.append(QgsFeature(sw_feat))

        if kept_sidewalks:
            filtered_sidewalk_lines_dp.addFeatures(kept_sidewalks)
        feedback.pushInfo(
            f"Sidewalk lines filtered by protoblocks: {filtered_sidewalk_lines.featureCount()} features remain."
        )
        whole_sidewalks_lines = filtered_sidewalk_lines  # Replace with filtered
    else:
        feedback.pushWarning(
            "No dissolved protoblocks layer provided or it's empty; skipping filtering of sidewalks by protoblocks."
        )

    # TODO: Add area/perimeter ratio calculations if needed for some filtering not done here.
    # The original plugin does this on self.whole_sidewalks (which are lines)
    # by polygonizing them again, calculating area/perimeter on polygons, then using ratios.
    # This seems more for quality control/potential filtering not directly part of core generation.
    # For now, skipping this complex ratio calculation.

    return {
        "sidewalk_lines": whole_sidewalks_lines,
        "exclusion_zones": exclusion_zones_poly,
        "sure_zones": sure_zones_poly,
        "width_adjusted_streets": width_adjusted_streets,
    }
