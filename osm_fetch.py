import requests, os
import geopandas as gpd
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

def get_osm_data(querystring,tempfilesname,print_response=True,delete_temp_files=False,interest_geom_type='Polygon'):
    '''
        get the osmdata and stores in a geodataframe, also generates temporary files
    '''

    # the requests part:
    overpass_url = "http://overpass-api.de/api/interpreter" # there are also other options
    response = requests.get(overpass_url,params={'data':querystring})

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
        xml = data.read()

    geojson = osm2geojson.xml2geojson(xml, filter_used_refs=False, log_level='INFO')

    print('conversion sucessfull!!')
    # reading as a geodataframe
    as_gdf = gpd.read_file(geojsonfilepath)

    # cleaning up, if wanted
    if delete_temp_files:
        delete_filelist_that_exists([xmlfilepath,geojsonfilepath])

    # return only polygons, we have no interest on broken features
    if interest_geom_type:
        new_gdf = as_gdf[as_gdf['geometry'].geom_type == interest_geom_type]

        #overwrite file with only selected features

        print('saving subset with only ',interest_geom_type)
        new_gdf.to_file(geojsonfilepath,driver='GeoJSON')

        return new_gdf
    else:
        return as_gdf