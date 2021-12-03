import requests, os, time, json
# import codecs
# import geopandas as gpd
# from geopandas import read_file
import osm2geojson
from itertools import cycle
from qgis.core import QgsApplication

# doing some stuff again to avoid circular imports:
# homepath = os.path.expanduser('~')

# user_profile = 'default' #TODO: read from session

# basepathp1 = '.local/share/QGIS/QGIS3/profiles'
# basepath = os.path.join(homepath,basepathp1,user_profile,basepathp2)

profilepath = QgsApplication.qgisSettingsDirPath()
base_pluginpath_p2 = 'python/plugins/osm_sidewalkreator'
basepath = os.path.join(profilepath,base_pluginpath_p2)



def delete_filelist_that_exists(filepathlist):
    for filepath in filepathlist:
        if os.path.exists(filepath):
            os.remove(filepath)

def join_to_a_outfolder(filename,foldername='temporary'):
    outfolder = os.path.join(basepath,foldername)

    return os.path.join(outfolder,filename)



def osm_query_string_by_bbox(min_lat,min_lgt,max_lat,max_lgt,interest_tag="highway",node=False,way=True,relation=False,print_querystring=False):

    node_part = way_part = relation_part = ''

    query_bbox = f'{min_lat},{min_lgt},{max_lat},{max_lgt}'

    if node:
        node_part = f'node["{interest_tag}"]({query_bbox});'
    if way:
        way_part = f'way["{interest_tag}"]({query_bbox});'
    if relation:
        relation_part = f'relation["{interest_tag}"]({query_bbox});'

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

def get_osm_data(querystring,tempfilesname,geomtype='LineString',print_response=False):
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
            response = requests.get(overpass_url,params={'data':querystring},timeout=30)

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


    # the outpaths for temporary files
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

    geojson_datadict = osm2geojson.xml2geojson(xml_filecontent, filter_used_refs=False, log_level='INFO')
    with open(geojsonfilepath.replace('.geojson','_unfiltered.geojson'),'w+') as geojson_handle:
        json.dump(geojson_datadict,geojson_handle)

    filtered_geojson_dict = filter_gjsonfeats_bygeomtype(geojson_datadict,geomtype)

    # dumping geojson file:
    with open(geojsonfilepath,'w+') as geojson_handle:
        json.dump(filtered_geojson_dict,geojson_handle)


    print('conversion sucessfull!!')
    # reading as a geodataframe
    # as_gdf = gpd.read_file(geojsonfilepath)

    # cleaning up, if wanted
    # if delete_temp_files:
    #     delete_filelist_that_exists([xmlfilepath,geojsonfilepath])

    return geojsonfilepath

    # # return only polygons, we have no interest on broken features
    # if interest_geom_type:
    #     new_gdf = as_gdf[as_gdf['geometry'].geom_type == interest_geom_type]

    #     #overwrite file with only selected features

    #     print('saving subset with only ',interest_geom_type)
    #     new_gdf.to_file(geojsonfilepath,driver='GeoJSON')

    #     return new_gdf
    # else:
    #     return as_gdf


