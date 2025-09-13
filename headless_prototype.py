# -*- coding: utf-8 -*-
"""
Headless prototype for OSM Sidewalkreator.

This module contains the core logic of the OSM Sidewalkreator plugin,
refactored to be runnable without the QGIS GUI.
"""

import os
import json
import geopandas as gpd
from generic_functions_headless import (
    read_input_polygon,
    get_bbox_from_gdf,
    fetch_street_network_for_bbox,
    clip_gdf,
    reproject_gdf,
    polygonize_lines_gdf,
    data_clean_gdf,
    split_lines_at_intersections,
    draw_sidewalks_gdf,
)
from parameters import *

def run_headless(input_polygon_path, output_directory, parameters_path=None):
    """
    Main function for the headless execution of the sidewalk generation process.

    :param input_polygon_path: Path to the GeoJSON file containing the input polygon.
    :param output_directory: Directory where the output files will be saved.
    :param parameters_path: Optional path to a JSON file with parameters.
    """

    # Load parameters or use defaults
    if parameters_path and os.path.exists(parameters_path):
        with open(parameters_path, 'r') as f:
            params = json.load(f)
    else:
        params = {
            "timeout": 60,
        }

    # Create output directory if it doesn't exist
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # 1. Load input polygon
    input_gdf = read_input_polygon(input_polygon_path)

    # 2. Get bounding box
    bbox = get_bbox_from_gdf(input_gdf)

    # 3. Fetch OSM Data
    osm_gdf = fetch_street_network_for_bbox(bbox)

    print(f"Number of features in osm_gdf: {len(osm_gdf)}")
    print(f"Columns in osm_gdf: {osm_gdf.columns}")
    print(f"CRS of osm_gdf: {osm_gdf.crs}")
    print(f"Bbox of osm_gdf: {osm_gdf.total_bounds}")
    print(f"CRS of input_gdf: {input_gdf.crs}")
    print(f"Bbox of input_gdf: {input_gdf.total_bounds}")

    # 4. Clip data
    clipped_gdf = clip_gdf(osm_gdf, input_gdf)

    # 5. Reproject to a local TM
    # A simple approach is to use a UTM projection based on the centroid of the input polygon
    lon, lat = input_gdf.unary_union.centroid.x, input_gdf.unary_union.centroid.y
    utm_crs = f"+proj=utm +zone={int((lon + 180) / 6)} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
    clipped_reproj_gdf = reproject_gdf(clipped_gdf, utm_crs)

    print(f"Number of features in clipped_reproj_gdf: {len(clipped_reproj_gdf)}")
    # 6. Clean data
    cleaned_gdf, existing_sidewalks, existing_crossings = data_clean_gdf(clipped_reproj_gdf, default_widths, fallback_default_width)

    # 7. Split lines at intersections
    lines_gdf = cleaned_gdf[cleaned_gdf.geometry.type == 'LineString'].copy()
    splitted_gdf = split_lines_at_intersections(lines_gdf)

    # 8. Polygonize to create protoblocks
    protoblocks_gdf = polygonize_lines_gdf(splitted_gdf)

    # 9. Separate buildings
    buildings_gdf = osm_gdf[osm_gdf['building'].notna()].copy()

    # 10. Draw sidewalks
    sidewalks_gdf = draw_sidewalks_gdf(splitted_gdf, buildings_gdf, cleaned_gdf, 2)

    # 10. Output results
    output_path = os.path.join(output_directory, "protoblocks_output.geojson")
    if not protoblocks_gdf.empty:
        protoblocks_gdf.to_crs("EPSG:4326").to_file(output_path, driver='GeoJSON')

    sidewalks_output_path = os.path.join(output_directory, "sidewalks_output.geojson")
    if not sidewalks_gdf.empty:
        sidewalks_gdf.to_crs("EPSG:4326").to_file(sidewalks_output_path, driver='GeoJSON')

    sidewalks_output_path = os.path.join(output_directory, "existing_sidewalks.geojson")
    if not existing_sidewalks.empty:
        existing_sidewalks.to_crs("EPSG:4326").to_file(sidewalks_output_path, driver='GeoJSON')

    crossings_output_path = os.path.join(output_directory, "existing_crossings.geojson")
    if not existing_crossings.empty:
        existing_crossings.to_crs("EPSG:4326").to_file(crossings_output_path, driver='GeoJSON')

    print(f"Process complete. Output saved to {output_path}")

if __name__ == '__main__':
    # This part allows running the script from the command line for testing
    # Example usage:
    # python headless_prototype.py /path/to/input.geojson /path/to/output_dir

    import sys
    if len(sys.argv) != 3:
        print("Usage: python headless_prototype.py <input_geojson_path> <output_directory_path>")
        sys.exit(1)

    input_geojson = sys.argv[1]
    output_dir = sys.argv[2]

    run_headless(input_geojson, output_dir)
