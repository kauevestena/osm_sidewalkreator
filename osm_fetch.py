'''
    osm_fetch.py created for import and convert the desired OSM data
'''


from tempfile import tempdir
import requests, os, time, json
# import codecs
# import geopandas as gpd
# from geopandas import read_file
import osm2geojson
from itertools import cycle
from qgis.core import QgsApplication

# doing some stuff again to avoid circular imports:
# homepath = os.path.expanduser('~')

profilepath = QgsApplication.qgisSettingsDirPath()
base_pluginpath_p2 = 'python/plugins/osm_sidewalkreator'
basepath = os.path.join(profilepath,base_pluginpath_p2)

'''
## MAJOR TODO: evaluate the use of "import gdal" to use gdal ogr api and osm driver to convert the .osm files, leaving zero external dependencies...
'''

def delete_filelist_that_exists(filepathlist):
    for filepath in filepathlist:
        if os.path.exists(filepath):
            os.remove(filepath)

def join_to_a_outfolder(filename,foldername='temporary'):
    outfolder = os.path.join(basepath,foldername)

    return os.path.join(outfolder,filename)



def osm_query_string_by_bbox(min_lat,min_lgt,max_lat,max_lgt,interest_key="highway",node=False,way=True,relation=False,print_querystring=False,interest_value = None,dump_path=None):

    node_part = way_part = relation_part = ''

    query_bbox = f'{min_lat},{min_lgt},{max_lat},{max_lgt}'

    interest_value_part = ''

    if interest_value:
        interest_value_part = f'="{interest_value}"'

    if node:
        node_part = f'node["{interest_key}"{interest_value_part}]({query_bbox});'
    if way:
        way_part = f'way["{interest_key}"{interest_value_part}]({query_bbox});'
    if relation:
        relation_part = f'relation["{interest_key}"{interest_value_part}]({query_bbox});'

    overpass_query = f"""
    (  
        {node_part}
        {way_part}
        {relation_part}
    );
    /*added by auto repair*/
    (._;>;);
    /*end of auto repair*/
    out;
    """

    if print_querystring:
        print(overpass_query)

    if dump_path:
        with open(dump_path,'w+') as querydumper:
            querydumper.write(overpass_query)

    return overpass_query

def filter_gjsonfeats_bygeomtype(geojson,geomtype='LineString',lvl1='features',include_feats_without_tags=False):
    '''
        Flexible function that can receives either a path to geojson file or geojson as a dictionary
    '''

    if type(geojson) == str:
        with open(geojson) as reader:
            data = reader.read()

        # print(data)
        as_dict = json.loads(data)
    else:
        as_dict = geojson

    feat_list =  as_dict[lvl1]

    new_list = []

    # in order to deal with relations
    allowed_types = [geomtype]

    if geomtype == 'Polygon':
        allowed_types.append('MultiPolygon')

    for entry in feat_list:
        # if entry['geometry']['type'] == geomtype:
        if any(entry['geometry']['type']==val for val in allowed_types):
            # fixing tags not appearing as fields
            # checking if tags in 'properties'
            if 'tags' in entry['properties']:
                tags_dict = entry['properties']['tags']

                for key in tags_dict:
                    entry['properties'][key] = entry['properties']['tags'][key]

                del entry['properties']['tags']

                new_list.append(entry)
            else:
                # so by default, features without tags will not be included
                if include_feats_without_tags:
                    new_list.append(entry)


    as_dict[lvl1] = new_list

    return as_dict

def get_osm_data(querystring,tempfilesname,geomtype='LineString',print_response=False,timeout=30,return_as_string=False,geojson_outpath=None):
    '''
        get the osmdata and stores in a geodataframe, also generates temporary files
    '''

    overpass_url_list = ["http://overpass-api.de/api/interpreter","https://lz4.overpass-api.de/api/interpreter","https://z.overpass-api.de/api/interpreter",'https://overpass.openstreetmap.ru/api/interpreter','https://overpass.openstreetmap.fr/api/interpreter','https://overpass.kumi.systems/api/interpreter']

    # to iterate circularly, thx: https://stackoverflow.com/a/23416519/4436950
    circular_iterator = cycle(overpass_url_list)

    overpass_url = next(circular_iterator)


    while True:
        # TODO: ensure sucess 
        #   (the try statement is an improvement already)
        try:
            response = requests.get(overpass_url,params={'data':querystring},timeout=timeout)

            if response.status_code == 200:
                break
        except:
            print('request not sucessful, retrying in 5 seconds... status:',response.status_code)
            time.sleep(5)
            overpass_url = next(circular_iterator)
            print('retrying with server',overpass_url)

            


    # TODO check the response, beyond terminal printing
    if print_response:
        print(response)

    if return_as_string or geojson_outpath:
        xml_filecontent = response.text

    else:
        if not geojson_outpath:
            # the outpaths for temporary files
            if tempfilesname:
                xmlfilepath = join_to_a_outfolder(tempfilesname+'_osm.xml')

                geojsonfilepath = join_to_a_outfolder(tempfilesname+'_osm.geojson')

            print('xml will be written to: ',xmlfilepath)



            # the xml file writing part:
            with open(xmlfilepath,'w+') as handle:
                handle.write(response.text)

            print('geojson will be written to: ',geojsonfilepath)

            # # # # # the command-line call
            # # # # # old method: using osmtogeojson app
            # # # # runstring = f'osmtogeojson "{xmlfilepath}" > "{geojsonfilepath}"'
            # # # # out = subprocess.run(runstring,shell=True)

            # # new method : osm2geojson library
            # codecs.
            with open(xmlfilepath, 'r', encoding='utf-8') as data:
                xml_filecontent = data.read()

    # converting OSM XML to Geojson:
    geojson_datadict = osm2geojson.xml2geojson(xml_filecontent, filter_used_refs=False, log_level='INFO')

    if not return_as_string and not geojson_outpath:
        with open(geojsonfilepath.replace('.geojson','_unfiltered.geojson'),'w+') as geojson_handle:
            json.dump(geojson_datadict,geojson_handle)

    filtered_geojson_dict = filter_gjsonfeats_bygeomtype(geojson_datadict,geomtype)




    print('conversion sucessfull!!')

    if return_as_string:
        return json.dumps(filtered_geojson_dict)

    else:
        # dumping geojson file:
        if geojson_outpath:
            geojsonfilepath = geojson_outpath
        
        with open(geojsonfilepath,'w+') as geojson_handle:
            json.dump(filtered_geojson_dict,geojson_handle)

        return geojsonfilepath



