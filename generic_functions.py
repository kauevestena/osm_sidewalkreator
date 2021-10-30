from typing import Protocol
from qgis import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer, QgsProject, edit
import os



crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")


def reproject_layer(inputlayer,destination_crs='EPSG:4326',output_mode='memory:Reprojected'):
    parameter_dict = {'INPUT': inputlayer, 'TARGET_CRS': destination_crs,
                 'OUTPUT': output_mode}

    return processing.run('native:reprojectlayer', parameter_dict)['OUTPUT']


def split_lines(inputlayer,splitterlayer,outputlayer):

    parameter_dict = {'INPUT': inputlayer, 'LINES': splitterlayer, 'OUTPUT': outputlayer}

    return processing.run('qgis:splitwithlines',parameter_dict)['OUTPUT']


def cliplayer(inlayerpath,cliplayerpath,outputpath):
    '''
        clip a layer

        all inputs are paths!!!

        will be generated clipped layer as a file in outputpath

        source: https://opensourceoptions.com/blog/pyqgis-clip-vector-layers/ (thx!!)
    '''
    #run the clip tool
    processing.run("native:clip", {'INPUT':inlayerpath,'OVERLAY':cliplayerpath,'OUTPUT':outputpath})


def path_from_layer(inputlayer,splitcharacter='|',splitposition=0):
    return inputlayer.dataProvider().dataSourceUri().split(splitcharacter)[splitposition]

def custom_local_projection(lgt_0,lat_0=0,mode='TM',return_wkt=False):

    as_wkt = f"""PROJCRS["unknown",
    BASEGEOGCRS["WGS 84",
        DATUM["World Geodetic System 1984",
            ELLIPSOID["WGS 84",6378137,298.257223563,
                LENGTHUNIT["metre",1]],
            ID["EPSG",6326]],
        PRIMEM["Greenwich",0,
            ANGLEUNIT["degree",0.0174532925199433],
            ID["EPSG",8901]]],
    CONVERSION["unknown",
        METHOD["Transverse Mercator",
            ID["EPSG",9807]],
        PARAMETER["Latitude of natural origin",{lat_0},
            ANGLEUNIT["degree",0.0174532925199433],
            ID["EPSG",8801]],
        PARAMETER["Longitude of natural origin",{lgt_0},
            ANGLEUNIT["degree",0.0174532925199433],
            ID["EPSG",8802]],
        PARAMETER["Scale factor at natural origin",1,
            SCALEUNIT["unity",1],
            ID["EPSG",8805]],
        PARAMETER["False easting",0,
            LENGTHUNIT["metre",1],
            ID["EPSG",8806]],
        PARAMETER["False northing",0,
            LENGTHUNIT["metre",1],
            ID["EPSG",8807]]],
    CS[Cartesian,2],
        AXIS["(E)",east,
            ORDER[1],
            LENGTHUNIT["metre",1,
                ID["EPSG",9001]]],
        AXIS["(N)",north,
            ORDER[2],
            LENGTHUNIT["metre",1,
                ID["EPSG",9001]]]]
    """

    # TODO: if mode != 'TM' and lat_0 != 0:
    # define as_wkt as a stereographic projection

    custom_crs = QgsCoordinateReferenceSystem()

    custom_crs.createFromWkt(as_wkt)

    if return_wkt:
        return as_wkt
    else:
        return custom_crs

def reproject_layer_localTM(inputlayer,outputpath,layername,lgt_0,lat_0=0):

    # https://docs.qgis.org/3.16/en/docs/user_manual/processing_algs/qgis/vectorgeneral.html#reproject-layer

    operation = f'+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad +step +proj=tmerc +lat_0={lat_0} +lon_0={lgt_0} +k=1 +x_0=0 +y_0=0 +ellps=WGS84'


    parameter_dict = { 'INPUT' : inputlayer, 'OPERATION' : operation, 'OUTPUT' : outputpath }

    # option 1: creating from wkt
    # proj_wkt = custom_local_projection(lgt_0,return_wkt=True)
    # parameter_dict['TARGET_CRS'] = QgsCoordinateReferenceSystem(proj_wkt)

    # option 2: as a crs object, directly
    new_crs = custom_local_projection(lgt_0,lat_0=lat_0)
    parameter_dict['TARGET_CRS'] = new_crs


    processing.run('native:reprojectlayer', parameter_dict)

    # fixing no set layer crs:

    ret_lyr = QgsVectorLayer(outputpath,layername,'ogr')

    ret_lyr.setCrs(new_crs)

    return ret_lyr, new_crs

# def retrieve_att(layer,att_id,row_id):
#     iterr = layer.getFeatures()
#     attrs = []
#     for feature in iterr:
#         attrs.append(feature.attributes())
#     return attrs[row_id][att_id]

# def retrieve_attrs(layer):
#     iterr = layer.getFeatures()
#     attrs = []
#     for feature in iterr:
#         attrs.append(feature.attributes())
#     return attrs

# def column(matrixList, i):
#     return [row[i] for row in matrixList]

def check_empty_layer(inputlayer):
    feat_count = 0

    for feature in inputlayer.getFeatures():
        feat_count += 1

    return (feat_count == 0)

def get_column_names(inputlayer):
    return inputlayer.fields().names()

def get_layercolumn_byname(inputlayer,columname):

    input_table = get_layer_att_table(inputlayer)

    column_id = inputlayer.fields().lookupField(columname)

    return [sublist[column_id] for sublist in input_table]

def get_layer_att_table(inputlayer):
    att_lists = []

    for feature in inputlayer.getFeatures():
        
        att_lists.append(feature.attributes())

    return att_lists


def wipe_folder_files(inputfolderpath):
    for filename in os.listdir(inputfolderpath):
        filepath = os.path.join(inputfolderpath,filename)

        os.remove(filepath)

# def remove_layer(layername):
#     # thx https://gis.stackexchange.com/a/310590/49900
#     # but deprecated
#     layerinstance = QgsProject.instance()
    
#     lyref = layerinstance.mapLayersByName(layername)

#     if lyref:
#         layerinstance.removeMapLayer(lyref[0].id())

def remove_layerlist(listoflayer_alias):
    # thx https://gis.stackexchange.com/a/310590/49900

    project_instance = QgsProject.instance()


    for layerfullname in project_instance.mapLayers():
        if any(alias in layerfullname for alias in listoflayer_alias):
            project_instance.removeMapLayer(layerfullname)


def remove_unconnected_lines(inputlayer):
    #thx: https://gis.stackexchange.com/a/316058/49900
    with edit(inputlayer):
        for i,feature_A in enumerate(inputlayer.getFeatures()):
            is_disjointed = True
            # disjointed_features = 0
            for j,feature_B in enumerate(inputlayer.getFeatures()):
                if not i == j:
                    if not feature_A.geometry().disjoint(feature_B.geometry()):
                        # print('not disjointed!!',i,j)
                        is_disjointed=False

            if is_disjointed:
                # print(is_disjointed)

                inputlayer.deleteFeature(feature_A.id())

    # # # # it works inplace =D ()
    # # # # return inputlayer


def remove_features_byattr(inputlayer,attrname,attrvalue):

    column_values = get_layercolumn_byname(inputlayer,attrname)

    with edit(inputlayer):
        for i,feature in enumerate(inputlayer.getFeatures()):
            if column_values[i] == attrvalue:
                inputlayer.deleteFeature(feature.id())
                


            




