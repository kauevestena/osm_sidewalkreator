# -*- coding: utf-8 -*-

"""
File intended to store "hyperparameters"


ALL DISTANCES MUST BE IN METERS, no feets nor yards
"""


CRS_LATLON_4326 = "EPSG:4326"

# to look for adresses:
addr_tag = "addr:housenumber"

highway_tag = "highway"

sidewalk_tag_value = "footway"

widths_fieldname = "width"

# control
use_buildings = True
draw_buildings = True
# to control whether must download relations in buildings
include_relations = True


# buffer that defines the curvature radius is defined in GUI, max and min are in the .ui file
default_curve_radius = 3

# minimal distance that a sidewalk must be from a building
min_d_to_building = (
    1  # 1 m defined in gui, along with max an min allowed values at .ui file
)

osm_higway_layer_finalname = "osm_clipped_highways"
buildings_layername = "osm_buildings"
roads_layername = "osm_road_data"

# big buffer distance
big_buffer_d = 10000

# min buffer size for the worst case (building intersecting road)
minimal_buffer = 3  # 2m

# distance to add to distance to interpolate inner_points, should be a small distance, 0.5 or 1 m, generally
d_to_add_interp_d = 2

# percent of middle-crossing segment to draw Kerbs
perc_draw_kerbs = 30

# percent of tolerance to drive a point innerly in segment
perc_tol_crossings = 25

# percent of length to interpolate if passes half the length
perc_to_interpolate = 0.4

# distance to add to each side, as we are creating sidewalk axis, not kerbs
d_to_add_to_each_side = 1  # 1m

# Default timeout for network requests in seconds
DEFAULT_TIMEOUT_SECONDS = 60


# for values that must be ignored one must use "0" as value
default_widths = {
    # loosely based on https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio/regulamentacao-atual/normas-para-o-projeto-das-estradas-de-rodagem (Brazilian DNIT specifications)
    # most common:
    "motorway": 22.0,
    "trunk": 18.0,
    "primary": 12.0,
    "residential": 6.0,
    "secondary": 10.0,
    "tertiary": 8.0,
    "unclassified": 4.0,
    # unclear/uncanny/rare cases:
    "road": 6.0,
    "living_street": 0.0,
    # links:
    "trunk_link": 0,
    "motorway_link": 0,
    "secondary_link": 0,
    "tertiary_link": 0,
    "primary_link": 0,
    # values that must be ignored:
    "sidewalk": 0,
    "crossing": 0,
    "path": 0,
    "service": 0,
    "pedestrian": 0,
    "escape": 0,
    "raceway": 0,
    "cycleway": 0,
    "proposed": 0,
    "construction": 0,
    "platform": 0,
    "services": 0,
    "footway": 0,
    "track": 0,
    "corridor": 0,
    "steps": 0,
    "street_lamp": 0,
    # '' : ,
}

# for case(s) of an unexpected value:
fallback_default_width = 6.0

# ASSETS:
# names of the assets filenames:
sidewalks_stylefilename = "sidewalkstyles.qml"
inputpolygons_stylefilename = "polygonstyles.qml"
crossings_stylefilename = "crossings.qml"
kerbs_stylefilename = "kerbs.qml"
splitting_pois_stylefilename = "addrs_centroids2.qml"
buildings_stylefilename = "buildings.qml"
road_intersections_stylefilename = "road_intersections.qml"

exclusion_stylefilename = "exclusion_zones.qml"
sure_stylefilename = "sure_zones.qml"

roads_p1_stylefilename = "roads_p1.qml"
roads_p2_stylefilename = "roads_p2_main.qml"
roads_p3_stylefilename = "roads_p3.qml"


osm_basemap_str = "crs=EPSG:3857&format&type=xyz&url=http://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0"

bing_baseimg_str = "crs=EPSG:3857&format&type=xyz&url=http://ak.t0.tiles.virtualearth.net/tiles/a%7Bq%7D.jpeg?n%3Dz%26g%3D5880&zmax=19&zmin=0"


crossing_centers_layername = "crossing_points"

crossings_layer_name = "CROSSINGS"

kerbs_layer_name = "KERBS"

# little buffer for dissolved protoblocks "within" condition eligibility in all cases (as long as I know)
protoblocks_buffer = 0.5  # 50 cm

# value to exclude "tiny segments"
tiny_segments_tol = 0.1

# (draw_crossings context) increment in meters if the length of the crossing is bigger than the max len
increment_inward = 0.5
# max iterations in the
max_crossings_iterations = 20

# max distance for distance search in knn
knn_max_dist = 50

# cutoff percent to say that a protoblock contains an already drawn sidewalk:
cutoff_percent_protoblock = 40

# for duplicate points (m):
duplicate_points_tol = 0.1

# snap tolerance for disjointed (m):
snap_disjointed_tol = 0.5

# minimum length that a sidewalk stretch should have (m):
min_stretch_size = 7

# absolute max crossing len (m):
abs_max_crossing_len = 100  # 100 m could be a very large crossing
