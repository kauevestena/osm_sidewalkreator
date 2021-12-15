# -*- coding: utf-8 -*-

"""
 File intended to store "hyperparameters"


 ALL DISTANCES MUST BE IN METERS, no feets nor yards
"""


CRS_LATLON_4326 = "EPSG:4326"

# to look for adresses:
addr_tag = 'addr:housenumber'

highway_tag = 'highway'

sidewalk_tag_value = 'footway'

widths_fieldname = 'width'

# control
use_buildings = True
draw_buildings = True
# to control wheter must dowload relations in buildings
include_relations = True


# buffer that defines the curvature radius is defined in GUI, max and min are in the .ui file
default_curve_radius = 5

# minimal distance that a sidewalk must be from a building
min_d_to_building = 1 # 1 m defined in gui, along with max an min allowed values at .ui file

osm_higway_layer_finalname = 'osm_clipped_highways'
buildings_layername = 'osm_buildings'

# big buffer distance
big_buffer_d = 3000

# min buffer size for the worst case (building intersecting road)
minimal_buffer = 3 # 2m

# distance to add to distance to interpolate inner_points, should be a small distance, 0.5 or 1 m, generally
d_to_add_interp_d = 2

# percent of middle-crossing segment to draw Kerbs
perc_draw_kerbs = 30

# percent of length to interpolate if passes half the length
perc_to_interpolate = 0.4

# distance to add to each side, as we are creating sidewalk axis, not kerbs
d_to_add_to_each_side = 1 # 1m


# for values that must be ignored one must use "0" as value
default_widths = {
    # loosely based on https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio/regulamentacao-atual/normas-para-o-projeto-das-estradas-de-rodagem (Brazilian DNIT specifications)


    # most common:
    'motorway' : 22,
    'trunk' :  18,
    'primary' : 12,
    'residential': 6,
    'secondary' : 10,
    'tertiary' : 8,
    'unclassified': 4,

    # unclear/uncanny/rare cases:
    'road' : 6,
    'living_street': 4,


    # values that must be igored:
    'sidewalk' : 0,
    'crossing' : 0,
    'path' : 0,
    'service' : 0,
    'pedestrian' : 0,
    'escape' : 0,
    'raceway' : 0,
    'cycleway' : 0,
    'proposed' :0,
    'construction' : 0,
    'platform' : 0,
    'services' : 0,
    'footway' : 0,
    'track' : 0,
    
    # '' : ,
    }

# ASSETS:
# names of the assets filenames:
sidewalks_stylefilename = 'sidewalkstyles.qml'
inputpolygons_stylefilename = 'polygonstyles.qml'
crossings_stylefilename = 'crossings.qml'



osm_basemap_str = "crs=EPSG:3857&format&type=xyz&url=http://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0"

bing_baseimg_str = 'crs=EPSG:3857&format&type=xyz&url=http://ak.t0.tiles.virtualearth.net/tiles/a%7Bq%7D.jpeg?n%3Dz%26g%3D5880&zmax=19&zmin=0'


crossing_centers_layername = 'crossing_points'

crossings_layer_name = 'CROSSINGS'

# little buffer for dissolved protoblocks "within" condition elegibility in all cases (as long as I know)
protoblocks_buffer = 0.5 # 50 cm