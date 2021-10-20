import json

geojson_path = '/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator/temporary/osm_download_data_osm.geojson'


with open(geojson_path) as reader:
    data = reader.read()

    # print(data)
    as_dict = json.loads(data)


# for key in as_dict['features']:
#     print(key,'\n')

print(as_dict['features'][-1])