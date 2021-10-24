"""
 File intended to store "hyperparameters"
"""

highway_tag = 'highway'


# control
use_buildings = True
draw_buildings = True
# to control wheter must dowload relations in buildings
include_relations = True




# for values that must be ignored one must use "0" as value
default_widths = {
    # loosely based on https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio/regulamentacao-atual/normas-para-o-projeto-das-estradas-de-rodagem (Brazilian DNIT specifications)


    # most common:
    'motorway' : 22,
    'trunk' :  18,
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
    'cicleway' : 0,
    'proposed' :0,
    'construction' : 0,
    'platform' : 0,
    'services' : 0,

    }