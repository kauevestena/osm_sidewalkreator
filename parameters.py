"""
 File intended to store "hyperparameters"


 ALL DISTANCES MUST BE IN METERS, no feets nor yards
"""

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


# safe distance for dissolved buffer to assert that should be continuous
safe_buffer_minimal_continuous = 10 # 10 cm



# minimal distance that a sidewalk must be from a building
min_d_to_building = 1 # 1 m

osm_higway_layer_finalname = 'osm_clipped_highways'
buildings_layername = 'osm_buildings'


# min buffer size for the worst case (building intersecting road)
minimal_buffer = 2 # 2m

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