# -*- coding: utf-8 -*-
"""
This file contains generic functions for the headless prototype, using geopandas.
"""

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString
from osm_fetch import osm_query_string_by_bbox, get_osm_data

def read_input_polygon(filepath):
    """
    Reads an input polygon from a file and returns a GeoDataFrame.
    """
    return gpd.read_file(filepath)

def get_bbox_from_gdf(gdf):
    """
    Gets the bounding box from a GeoDataFrame.
    """
    return gdf.total_bounds

import osmnx as ox

def fetch_street_network_for_bbox(bbox):
    """
    Fetches the street network for a given bounding box using osmnx.
    """
    tags = {"highway": True, "building": True, "amenity": True, "shop": True}
    gdf = ox.features_from_bbox(bbox, tags)
    return gdf

def clip_gdf(gdf, clip_geom):
    """
    Clips a GeoDataFrame with a clipping geometry.
    """
    return gpd.clip(gdf, clip_geom)

def reproject_gdf(gdf, target_crs):
    """
    Reprojects a GeoDataFrame to a target CRS.
    """
    return gdf.to_crs(target_crs)

from shapely.ops import polygonize

def polygonize_lines_gdf(gdf):
    """
    Polygonizes lines in a GeoDataFrame.
    """
    lines = [geom for geom in gdf.geometry]
    print(f"Number of lines to polygonize: {len(lines)}")
    polygons = list(polygonize(lines))
    print(f"Number of polygons found: {len(polygons)}")

    gdf_poly = gpd.GeoDataFrame(geometry=polygons)
    gdf_poly = gdf_poly.set_crs(gdf.crs)
    return gdf_poly

import ast
import pandas as pd

from shapely.ops import split
from shapely.geometry import MultiPoint, Point

def split_lines_at_intersections(gdf):
    """
    Splits lines at their intersections.
    """
    # Find all intersections
    intersections = gdf.sindex.query(gdf.geometry, predicate='intersects')

    split_points = []
    print(f"Number of intersections found: {len(intersections[0])}")
    for i in range(len(intersections[0])):
        idx1 = intersections[0][i]
        idx2 = intersections[1][i]
        if idx1 >= idx2:
            continue
        line1 = gdf.geometry.iloc[idx1]
        line2 = gdf.geometry.iloc[idx2]
        intersection = line1.intersection(line2)
        if intersection.geom_type == 'Point':
            split_points.append(intersection)
        elif intersection.geom_type == 'MultiPoint':
            split_points.extend(list(intersection.geoms))

    # Split the lines
    new_lines = []
    for i, row in gdf.iterrows():
        line = row.geometry
        points_on_line = [p for p in split_points if line.intersects(p)]
        if points_on_line:
            new_line_parts = split(line, MultiPoint(points_on_line))
            for part in new_line_parts.geoms:
                new_lines.append(part)
        else:
            new_lines.append(line)

    return gpd.GeoDataFrame(geometry=new_lines, crs=gdf.crs)

from shapely.ops import nearest_points

def adjust_buffer_for_buildings(lines_gdf, buildings_gdf, default_buffer):
    """
    Adjusts the buffer distance for each line based on the distance to the nearest building.
    """
    if buildings_gdf.empty:
        lines_gdf['buffer_dist'] = default_buffer
        return lines_gdf

    # Create a spatial index for buildings
    buildings_sindex = buildings_gdf.sindex

    # For each line, find the nearest building and calculate the distance
    def get_dist_to_building(line):
        possible_matches_index = list(buildings_sindex.intersection(line.bounds))
        possible_matches = buildings_gdf.iloc[possible_matches_index]
        if possible_matches.empty:
            return default_buffer

        nearest_geom = nearest_points(line, possible_matches.unary_union)[1]
        return line.distance(nearest_geom)

    lines_gdf['dist_to_building'] = lines_gdf.geometry.apply(get_dist_to_building)

    # Adjust buffer distance
    lines_gdf['buffer_dist'] = lines_gdf['dist_to_building'] / 2
    lines_gdf.loc[lines_gdf['buffer_dist'] > default_buffer, 'buffer_dist'] = default_buffer

    return lines_gdf

def handle_exclusion_zones(sidewalks_gdf, streets_gdf):
    """
    Removes exclusion zones from the sidewalks.
    """
    if 'sidewalk' not in streets_gdf.columns:
        return sidewalks_gdf

    exclusion_zones = streets_gdf[streets_gdf['sidewalk'] == 'no'].copy()
    if exclusion_zones.empty:
        return sidewalks_gdf

    exclusion_buffer = exclusion_zones.buffer(exclusion_zones['width'] / 2 + 1)
    return sidewalks_gdf.difference(exclusion_buffer.unary_union)

import networkx as nx

def remove_lines_from_no_block_gdf(gdf):
    """
    Removes lines that do not form a block.
    """
    G = ox.graph_from_gdfs(gpd.GeoDataFrame(), gdf, graph_attrs={'crs': gdf.crs})

    # remove dead-end streets
    while True:
        dead_ends = [node for node, degree in G.degree() if degree == 1]
        if not dead_ends:
            break
        G.remove_nodes_from(dead_ends)

    return ox.graph_to_gdfs(G, nodes=False, edges=True)

def filter_and_buffer_protoblocks_gdf(protoblocks_gdf, sidewalks_gdf, cutoff_percent=50):
    """
    Filters and buffers the protoblocks.
    """
    if sidewalks_gdf.empty:
        return protoblocks_gdf.dissolve().buffer(0.1)

    # Spatial join
    joined_gdf = gpd.sjoin(protoblocks_gdf, sidewalks_gdf, how="inner", predicate="intersects")

    # Calculate sidewalk area per protoblock
    joined_gdf['sidewalk_area'] = joined_gdf.geometry.area
    sidewalk_area_per_protoblock = joined_gdf.groupby(joined_gdf.index).sidewalk_area.sum()

    # Calculate protoblock area
    protoblocks_gdf['protoblock_area'] = protoblocks_gdf.geometry.area

    # Join the two series
    protoblocks_gdf = protoblocks_gdf.join(sidewalk_area_per_protoblock)
    protoblocks_gdf['sidewalk_area'] = protoblocks_gdf['sidewalk_area'].fillna(0)

    # Calculate ratio and filter
    protoblocks_gdf['ratio'] = (protoblocks_gdf['sidewalk_area'] / protoblocks_gdf['protoblock_area']) * 100
    filtered_protoblocks = protoblocks_gdf[protoblocks_gdf['ratio'] <= cutoff_percent]

    # Dissolve and buffer
    dissolved_protoblocks = filtered_protoblocks.dissolve()
    buffered_protoblocks = dissolved_protoblocks.buffer(0.1)

    return buffered_protoblocks

import math

def calculate_crossing_direction(point, lines):
    """
    Calculates the direction vector of the crossing.
    """
    if len(lines) < 2:
        return None

    angles = []
    for i, row in lines.iterrows():
        line = row.geometry
        coords = list(line.coords)
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i+1]
            if Point(p1).equals(point) or Point(p2).equals(point):
                angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
                angles.append(angle)

    if len(angles) < 2:
        return None

    # Find the two angles with the smallest difference
    min_diff = 2 * math.pi
    best_pair = (0, 0)
    for i in range(len(angles)):
        for j in range(i + 1, len(angles)):
            diff = abs(angles[i] - angles[j])
            if diff > math.pi:
                diff = 2 * math.pi - diff
            if diff < min_diff:
                min_diff = diff
                best_pair = (angles[i], angles[j])

    # The direction of the crossing is the bisection of the angle
    angle = (best_pair[0] + best_pair[1]) / 2

    return Point(math.cos(angle), math.sin(angle))

def draw_crossings_gdf(streets_gdf):
    """
    Generates crossings at the intersections of the street lines.
    """
    # Find all intersection points
    intersections = streets_gdf.sindex.query(streets_gdf.geometry, predicate='intersects')

    eligible_points = []
    for i in range(len(intersections[0])):
        idx1 = intersections[0][i]
        idx2 = intersections[1][i]
        if idx1 >= idx2:
            continue
        line1 = streets_gdf.geometry.iloc[idx1]
        line2 = streets_gdf.geometry.iloc[idx2]
        intersection = line1.intersection(line2)
        if intersection.geom_type == 'Point':
            eligible_points.append(intersection)
        elif intersection.geom_type == 'MultiPoint':
            eligible_points.extend(list(intersection.geoms))

    # Create crossings
    crossing_lines = []
    for p in eligible_points:
        # Get the intersecting lines at the point
        intersecting_lines = streets_gdf[streets_gdf.geometry.intersects(p)]
        direction = calculate_crossing_direction(p, intersecting_lines)
        if direction:
            line = LineString([(p.x - direction.x, p.y - direction.y), (p.x + direction.x, p.y + direction.y)])
            crossing_lines.append(line)
        else:
            line = LineString([(p.x - 2, p.y - 2), (p.x + 2, p.y + 2)])
            crossing_lines.append(line)

    gdf = gpd.GeoDataFrame(geometry=crossing_lines)
    if not gdf.empty:
        gdf = gdf.set_crs(streets_gdf.crs)
    return gdf

from scipy.spatial import Voronoi

def split_sidewalks_by_voronoi(sidewalks_gdf, pois_gdf):
    """
    Splits the sidewalks by Voronoi polygons created from the POIs.
    """
    if pois_gdf.empty:
        return sidewalks_gdf

    # Create Voronoi polygons
    points = pois_gdf.geometry.apply(lambda p: (p.x, p.y)).tolist()
    vor = Voronoi(points)

    # Convert Voronoi polygons to shapely Polygons
    lines = [
        LineString(vor.vertices[line])
        for line in vor.ridge_vertices
        if -1 not in line
    ]

    # Create a GeoDataFrame of the Voronoi lines
    voronoi_lines_gdf = gpd.GeoDataFrame(geometry=lines, crs=sidewalks_gdf.crs)

    # Split the sidewalks by the Voronoi lines
    new_sidewalks = []
    for i, row in sidewalks_gdf.iterrows():
        sidewalk = row.geometry.boundary
        new_sidewalk_parts = split(sidewalk, voronoi_lines_gdf.unary_union)
        for part in new_sidewalk_parts.geoms:
            new_sidewalks.append(part)

    gdf = gpd.GeoDataFrame(geometry=new_sidewalks)
    gdf = gdf.set_crs(sidewalks_gdf.crs)
    return gdf

def split_sidewalks_by_protoblock_corners(sidewalks_gdf, protoblocks_gdf):
    """
    Splits the sidewalks by the corners of the protoblocks.
    """
    if protoblocks_gdf.empty:
        return sidewalks_gdf

    # Get all protoblock corners
    corners = []
    for i, row in protoblocks_gdf.iterrows():
        protoblock = row.geometry
        corners.extend(list(protoblock.exterior.coords))

    # Create a single MultiPoint geometry of all the corners
    splitter = MultiPoint(corners)

    # Split the sidewalks
    new_sidewalks = []
    for i, row in sidewalks_gdf.iterrows():
        sidewalk = row.geometry.boundary
        new_sidewalk_parts = split(sidewalk, splitter)
        for part in new_sidewalk_parts.geoms:
            new_sidewalks.append(part)

    gdf = gpd.GeoDataFrame(geometry=new_sidewalks)
    gdf = gdf.set_crs(sidewalks_gdf.crs)
    return gdf

def split_sidewalks_by_max_length(sidewalks_gdf, max_length):
    """
    Splits the sidewalks by a maximum length.
    """
    new_sidewalks = []
    for i, row in sidewalks_gdf.iterrows():
        sidewalk = row.geometry
        if sidewalk.length > max_length:
            num_splits = int(sidewalk.length // max_length)
            splitter_points = [sidewalk.interpolate((i + 1) * max_length) for i in range(num_splits)]
            new_sidewalk_parts = split(sidewalk, MultiPoint(splitter_points))
            for part in new_sidewalk_parts.geoms:
                new_sidewalks.append(part)
        else:
            new_sidewalks.append(sidewalk)

    gdf = gpd.GeoDataFrame(geometry=new_sidewalks)
    gdf = gdf.set_crs(sidewalks_gdf.crs)
    return gdf

def split_sidewalks_by_num_segments(sidewalks_gdf, num_segments):
    """
    Splits the sidewalks into a number of segments.
    """
    new_sidewalks = []
    for i, row in sidewalks_gdf.iterrows():
        sidewalk = row.geometry
        segment_length = sidewalk.length / num_segments
        splitter_points = [sidewalk.interpolate((i + 1) * segment_length) for i in range(num_segments - 1)]
        new_sidewalk_parts = split(sidewalk, MultiPoint(splitter_points))
        for part in new_sidewalk_parts.geoms:
            new_sidewalks.append(part)

    gdf = gpd.GeoDataFrame(geometry=new_sidewalks)
    gdf = gdf.set_crs(sidewalks_gdf.crs)
    return gdf

def split_sidewalks_gdf(sidewalks_gdf, intersection_points_gdf, protoblocks_gdf, pois_gdf, max_length=None, num_segments=None):
    """
    Splits the sidewalks at the intersection points.
    """
    sidewalks_gdf = split_sidewalks_by_protoblock_corners(sidewalks_gdf, protoblocks_gdf)
    sidewalks_gdf = split_sidewalks_by_voronoi(sidewalks_gdf, pois_gdf)

    if max_length:
        sidewalks_gdf = split_sidewalks_by_max_length(sidewalks_gdf, max_length)

    if num_segments:
        sidewalks_gdf = split_sidewalks_by_num_segments(sidewalks_gdf, num_segments)

    if intersection_points_gdf.empty:
        return sidewalks_gdf

    # Create a single MultiPoint geometry of all intersection points
    splitter = MultiPoint(intersection_points_gdf.geometry.tolist())

    # Split the sidewalks
    new_sidewalks = []
    for i, row in sidewalks_gdf.iterrows():
        sidewalk = row.geometry.boundary
        new_sidewalk_parts = split(sidewalk, splitter)
        for part in new_sidewalk_parts.geoms:
            new_sidewalks.append(part)

    gdf = gpd.GeoDataFrame(geometry=new_sidewalks)
    gdf = gdf.set_crs(sidewalks_gdf.crs)
    return gdf

def calculate_sidewalk_properties(sidewalks_gdf):
    """
    Calculates properties for the sidewalks, such as area and perimeter.
    """
    sidewalks_gdf['area'] = sidewalks_gdf.geometry.area
    sidewalks_gdf['perimeter'] = sidewalks_gdf.geometry.length
    return sidewalks_gdf

def draw_sidewalks_gdf(gdf, buildings_gdf, streets_gdf, buffer_dist):
    """
    Generates sidewalks by buffering the street lines.
    """
    # Adjust buffer distance for buildings
    gdf = adjust_buffer_for_buildings(gdf, buildings_gdf, buffer_dist)

    # Buffer the lines to create polygons
    sidewalks_polygons = gdf.buffer(gdf['buffer_dist'])
    sidewalks_gdf = gpd.GeoDataFrame(geometry=sidewalks_polygons, crs=gdf.crs)

    # Handle exclusion zones
    sidewalks_gdf = handle_exclusion_zones(sidewalks_gdf, streets_gdf)

    # Calculate properties
    sidewalks_gdf = calculate_sidewalk_properties(sidewalks_gdf)

    return sidewalks_gdf

def data_clean_gdf(gdf, default_widths, fallback_default_width):
    """
    Cleans the OSM data in a GeoDataFrame.
    """
    # Parse other_tags
    def parse_tags(tags):
        if not tags or tags == 'nan':
            return {}
        try:
            return ast.literal_eval(tags)
        except (ValueError, SyntaxError):
            return {}

    if 'other_tags' in gdf.columns:
        tags_df = gdf['other_tags'].apply(parse_tags).apply(pd.Series)
        gdf = gdf.drop(columns=['other_tags']).join(tags_df)

    # Filter by highway tag
    highway_values = gdf['highway'].unique()
    widths = {val: default_widths.get(val, fallback_default_width) for val in highway_values}

    # Create layers of existing sidewalks and crossings
    existing_sidewalks = gpd.GeoDataFrame()
    if 'footway' in gdf.columns:
        existing_sidewalks = gdf[(gdf['highway'] == 'footway') & (gdf['footway'] == 'sidewalk')].copy()

    existing_crossings = gpd.GeoDataFrame()
    if 'footway' in gdf.columns:
        existing_crossings = gdf[(gdf['highway'] == 'footway') & (gdf['footway'] == 'crossing')].copy()

    print(f"Number of features before filtering: {len(gdf)}")

    # Remove features with width < 0.5
    gdf['width'] = gdf['highway'].map(widths)
    gdf = gdf[gdf['width'] >= 0.5].copy()

    print(f"Number of features after filtering: {len(gdf)}")

    return gdf, existing_sidewalks, existing_crossings
