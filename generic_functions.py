# -*- coding: utf-8 -*-

from typing import Protocol
from PyQt5.QtCore import QVariant
# from qgis.PyQt.QtCore import QVariant
from qgis import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer, QgsProject, edit, QgsGeometry, QgsProperty, QgsField, QgsFeature, QgsRasterLayer, QgsSpatialIndex, QgsFeatureRequest
import os
from math import isclose



crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")

def create_dir_ifnotexists(folderpath):
    if not os.path.exists(folderpath):
        os.makedirs(folderpath)


def generate_buffer(inputlayer,distance,segments=10,dissolve=True,cap_style='FLAT',join_style='ROUND',outputlayer='TEMPORARY_OUTPUT'):

    '''
        interfacing qgis processing operation

        one can specify variable length with an QGIS expression like the defalt value in 'distance' parameter 
        someting like: '( "width" /2)+1.5'
    '''

    parameter_dict = {'INPUT': inputlayer, 'DISTANCE': distance,'OUTPUT': outputlayer,'DISSOLVE':dissolve,'SEGMENTS':segments}

    if type(distance) == str:
        parameter_dict['DISTANCE'] = QgsProperty.fromExpression(distance)

    cap_styles = {"FLAT":1,"ROUND":0,'SQUARE':2}

    if cap_style.upper() in cap_styles:
        parameter_dict['END_CAP_STYLE'] = cap_styles[cap_style.upper()]

    join_styles = {'ROUND':0,'MITER':1,'BEVEL':2}

    if join_style.upper() in join_styles:
        parameter_dict['JOIN_STYLE'] = join_styles[join_style.upper()]

    

    return processing.run('native:buffer',parameter_dict)['OUTPUT']


def remove_duplicate_geometries(inputlayer,outputlayer):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:deleteduplicategeometries',parameter_dict)['OUTPUT']

def compute_difference_layer(inputlayer,overlaylayer,outputlayer='TEMPORARY_OUTPUT'):

    parameter_dict = {'INPUT': inputlayer,'OVERLAY':overlaylayer, 'OUTPUT': outputlayer}

    return processing.run('qgis:difference',parameter_dict)['OUTPUT']


def convert_multipart_to_singleparts(inputlayer,outputlayer='TEMPORARY_OUTPUT'):

    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:multiparttosingleparts',parameter_dict)['OUTPUT']


def mergelayers(inputlayerlist,dest_crs,outputlayer='TEMPORARY_OUTPUT'):
    '''
        Will only work for layers of the same geometry type
    '''

    parameter_dict = {'LAYERS': inputlayerlist,'CRS':dest_crs, 'OUTPUT': outputlayer}

    return processing.run('native:mergevectorlayers',parameter_dict)['OUTPUT']


# # # def check_distances_layers(layer_many_features,layer_one_feature,idx=0):


def dissolve_tosinglepart(inputlayer,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:dissolve',parameter_dict)['OUTPUT']

def poligonize_lines(inputlines,outputlayer='TEMPORARY_OUTPUT',keepfields=True):
    parameter_dict = {'INPUT': inputlines, 'OUTPUT': outputlayer,'KEEP_FIELDS':keepfields}

    return processing.run('native:polygonize',parameter_dict)['OUTPUT']

def extract_lines_from_polygons(input_polygons,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': input_polygons, 'OUTPUT': outputlayer}

    return processing.run('native:polygonstolines',parameter_dict)['OUTPUT']

def gen_centroids_layer(inputlayer,outputlayer='TEMPORARY_OUTPUT',for_allparts=False):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer,'ALL_PARTS':for_allparts}

    return processing.run('native:centroids',parameter_dict)['OUTPUT']

def get_intersections(inputlayer,intersect_layer,outputlayer):
    parameter_dict = {'INPUT': inputlayer, 'INTERSECT': intersect_layer, 'OUTPUT': outputlayer}

    return processing.run('qgis:lineintersections',parameter_dict)['OUTPUT']


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


def remove_biggest_polygon(inputlayer,record_area=False,area_fieldname='area'):
    areas = []
    ids = []

    
    # if one extracts only boundaries, one can still use the area value
    if record_area:
        create_new_layerfield(inputlayer,area_fieldname)
        area_idx = inputlayer.fields().indexOf(area_fieldname)

    with edit(inputlayer):
        for feature in inputlayer.getFeatures():
            area_val = feature.geometry().area()
            areas.append(area_val)
            ids.append(feature.id())

            if record_area:
                inputlayer.changeAttributeValue(feature.id(),area_idx,area_val)


        max_area_idx = areas.index(max(areas))
        inputlayer.deleteFeature(ids[max_area_idx])


        





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


def get_first_feature_or_geom(inputlayer,return_geom=False):

    first_feature = QgsFeature()

    # filling first feature:
    inputlayer.getFeatures().nextFeature(first_feature)

    if return_geom:
        return first_feature.geometry()

    else:
        return first_feature


def check_empty_layer(inputlayer):
    feat_count = 0

    for feature in inputlayer.getFeatures():
        feat_count += 1

    return (feat_count == 0)

def get_column_names(inputlayer):
    return inputlayer.fields().names()

def create_new_layerfield(inputlayer,fieldname,datatype=QVariant.Double):
    '''
        create a new field for the layer, and also can return the index of the new field
    '''

    with edit(inputlayer):
        new_field = QgsField(fieldname,datatype)
        inputlayer.dataProvider().addAttributes([new_field])
        inputlayer.updateFields()

    return inputlayer.fields().indexOf(fieldname)


def create_filled_newlayerfield(inputlayer,fieldname,fieldvalue,datatype):
    # creating field
    field_index = create_new_layerfield(inputlayer,fieldname,datatype)

    # then filling:
    with edit(inputlayer):
        for feature in inputlayer.getFeatures():
            inputlayer.changeAttributeValue(feature.id(),field_index,fieldvalue)


def remove_layerfields(inputlayer,fieldlist):

    # to assert if the field name really exists in 'fieldlist'
    layer_fields = get_column_names(inputlayer)

    with edit(inputlayer):
        for field_name in fieldlist:
            if field_name in layer_fields:
                f_idx = inputlayer.fields().indexOf(field_name)
                inputlayer.deleteAttribute(f_idx)



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

def qgs_point_geom_from_line_at(inputlinefeature,index=0):
    return QgsGeometry.fromPointXY(inputlinefeature.geometry().asPolyline()[index])

def remove_lines_from_no_block(inputlayer,layer_to_check_culdesac=None):
    '''
        remove lines in wich one of its ends 
        are not connected to any other segment

        the "layer_to_check_culdesac" is a whole layer (dissolved) that should be checked for 'within' condition
    '''

    # TODO: check if will work with multilinestrings

    check_for_culdesacs = False

    if layer_to_check_culdesac:
        check_for_culdesacs = True
        checker_geom = get_first_feature_or_geom(layer_to_check_culdesac,True)

    feature_ids_to_be_removed = []


    for i,feature_A in enumerate(inputlayer.getFeatures()):

        P0 = qgs_point_geom_from_line_at(feature_A)    # first point
        PF = qgs_point_geom_from_line_at(feature_A,-1) # last point

        P0_count = 0
        PF_count = 0


        for j,feature_B in enumerate(inputlayer.getFeatures()):
            # if not i == j:
            if P0.intersects(feature_B.geometry()):
                P0_count += 1
            if PF.intersects(feature_B.geometry()):
                PF_count += 1
                
        
        # print(P0_count,PF_count)


        if any(count == 1 for count in [P0_count,PF_count]):
            # after checking, only add if its not a "culdesac" 
            if check_for_culdesacs:
                if not feature_A.geometry().within(checker_geom):
                    feature_ids_to_be_removed.append(feature_A.id())

            # if no "checker geometry", then just add directly
            else:
                feature_ids_to_be_removed.append(feature_A.id())

    with edit(inputlayer):
        for feature_id in feature_ids_to_be_removed:
            inputlayer.deleteFeature(feature_id)


def remove_features_byattr(inputlayer,attrname,attrvalue):

    column_values = get_layercolumn_byname(inputlayer,attrname)

    with edit(inputlayer):
        for i,feature in enumerate(inputlayer.getFeatures()):
            if column_values[i] == attrvalue:
                inputlayer.deleteFeature(feature.id())
                

def add_tms_layer(qms_string,layername):
    # mostly for user add basemaps buttons
    QgsProject.instance().addMapLayer(QgsRasterLayer(qms_string,layername, 'wms'))

def distance_geom_another_layer(inputgeom,inputlayer,as_list=False,to_sort=False,input_spatial_index=None,max_dist=100,nn_feat_num=5):
    ret_dict = {}
    '''
        one passes a geometry and a layer anf get dict/list of distances
    '''

    feat_request = QgsFeatureRequest()

    if input_spatial_index:
        # thx, pt 2 https://gis.stackexchange.com/a/59185/49900 
        nearest_ids = input_spatial_index.nearestNeighbor(inputgeom,nn_feat_num,max_dist)

        feat_request.setFilterFids(nearest_ids)



    for feature in inputlayer.getFeatures(feat_request):
        ret_dict[feature.id()] = inputgeom.distance(feature.geometry())

    if as_list:
        if to_sort:
            return sorted(list(ret_dict.values()))
        else:
            return list(ret_dict.values())

    else:
        return ret_dict

def gen_layer_spatial_index(inputlayer,use_fullgeom_flag=True):
    '''
        return a spatial index filled with all of the layer's features
    '''
    # thx: https://gis.stackexchange.com/a/59185/49900 (part 1)



    feat_iterator = inputlayer.dataProvider().getFeatures()


    if use_fullgeom_flag:
        # thx: https://gis.stackexchange.com/a/374282/49900
        ret_spatial_index = QgsSpatialIndex(feat_iterator,flags=QgsSpatialIndex.FlagStoreFeatureGeometries)
    else:
        ret_spatial_index = QgsSpatialIndex(feat_iterator)


    # temp_feat = QgsFeature() # just to store temporarily
    # # filling:
    # while feat_iterator.nextFeature(temp_feat): # so ellegant
    #     ret_spatial_index.insertFeature(temp_feat)

    return ret_spatial_index

# def distances_anotherlyr_unsingNN(inputPTgeom,inputspatialindex,inputlayer,max_dist=100,nn_feat_num=5):





def get_major_dif_signed(inputval,inputlist,tol=0.5,print_diffs=False):
    '''
        in spite of finding a simple way to obtain the 'orthogonal' distance 
    '''
    
    diffs = []

    for value in inputlist:
        # always avoid to compare floats equally
        if not isclose(inputval,value,abs_tol=tol):
            diffs.append(value-inputval)

    if print_diffs:
        print(diffs)

    if diffs:
        if len(diffs) > 1:
            return inputval+max(diffs)
        else:
            return inputval+diffs[0]
    else:
        return inputval



def layer_from_featlist(featlist,layername=None,geomtype="Point",attrs_dict=None):
    '''
        creating a layer from a list of features (not geometries)
    '''

    lname = 'temp'

    if layername:
        lname = layername

    ret_layer =  QgsVectorLayer(geomtype, lname, "memory")

    with edit(ret_layer):
        if attrs_dict:
            attrs_list = []

            for key in attrs_dict:
                attrs_list.append(QgsField(key,attrs_dict[key]))

            ret_layer.dataProvider().addAttributes(attrs_list)
            
            ret_layer.updateFields()

        for feature in featlist:
            ret_layer.dataProvider().addFeature(feature)

        ret_layer.updateExtents()

    return ret_layer

def items_minor_than_inlist(value,inpulist):
    # thx: https://stackoverflow.com/a/10543316/4436950
    return sum(entry < value for entry in inpulist)