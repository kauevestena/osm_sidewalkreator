import json

geojson_path = '/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator/temporary/osm_download_data_osm.geojson'




def filter_gjsonfeats_bygeomtype(geojson_path,geomtype='LineString',lvl1='features'):

    with open(geojson_path) as reader:
        data = reader.read()

    # print(data)
    as_dict = json.loads(data)

    feat_list =  as_dict[lvl1]

    new_list = []

    for entry in feat_list:
        if entry['geometry']['type'] == geomtype:
            # fixing tags not appearing as fields
            tags_dict = entry['properties']['tags']

            for key in tags_dict:
                entry['properties'][key] = entry['properties']['tags'][key]

            del entry['properties']['tags']
            new_list.append(entry)

    as_dict[lvl1] = new_list

    return as_dict



print(filter_gjsonfeats_bygeomtype(geojson_path))