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
    tags = {"highway": True, "building": True}
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
    if not polygons:
        return gpd.GeoDataFrame(geometry=[], crs=gdf.crs)
    return gpd.GeoDataFrame(geometry=polygons, crs=gdf.crs)

import ast
import pandas as pd

from shapely.ops import split
from shapely.geometry import MultiPoint

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
