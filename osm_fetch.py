import requests, os, codecs, time, json
# import geopandas as gpd
# from geopandas import read_file
import osm2geojson

# doing some stuff again to avoid circular imports:
homepath = os.path.expanduser('~')

user_profile = 'default' #TODO: read from session

basepathp1 = '.local/share/QGIS/QGIS3/profiles'
basepathp2 = 'python/plugins/osm_sidewalkreator'
basepath = os.path.join(homepath,basepathp1,user_profile,basepathp2)


def delete_filelist_that_exists(filepathlist):
    for filepath in filepathlist:
        if os.path.exists(filepath):
            os.remove(filepath)

def join_to_default_outfolder(filename):
    outfolder = os.path.join(basepath,'temporary')

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


def get_osm_data(querystring,tempfilesname,print_response=False):
    '''
        get the osmdata and stores in a geodataframe, also generates temporary files
    '''

    # the requests part:
    overpass_url = "http://overpass-api.de/api/interpreter" # there are also other options


    while True:
        # TODO: ensure sucess
        response = requests.get(overpass_url,params={'data':querystring})

        if response.status_code == 200:
            break

        time.sleep(5)

    # TODO check the response, beyond terminal printing
    if print_response:
        print(response)


    # the outpaths for temporary files
    xmlfilepath = join_to_default_outfolder(tempfilesname+'_osm.xml')
    geojsonfilepath = join_to_default_outfolder(tempfilesname+'_osm.geojson')

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
    with codecs.open(xmlfilepath, 'r', encoding='utf-8') as data:
        xml_filecontent = data.read()

    geojson_datadict = osm2geojson.xml2geojson(xml_filecontent, filter_used_refs=False, log_level='INFO')

    # dumping geojson file:
    with open(geojsonfilepath,'w+') as geojson_handle:
        json.dump(geojson_datadict,geojson_handle)


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


default_widths = {
    
}