# -*- coding: utf-8 -*-

from typing import Protocol
from PyQt5.QtCore import QVariant
# from qgis.PyQt.QtCore import QVariant
from qgis import processing
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer, QgsProject, edit, QgsGeometry, QgsProperty, QgsField, QgsFeature, QgsRasterLayer, QgsSpatialIndex, QgsFeatureRequest, QgsGeometryUtils, QgsVector, QgsCoordinateTransform, QgsMultiPoint, QgsPoint, QgsPointXY, QgsProperty
import os, json
from math import isclose,pi



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


def split_lines_by_max_len(inputlayer,len_val_or_expression,outputlayer='TEMPORARY_OUTPUT'):



    parameter_dict = {'INPUT': inputlayer,'LENGTH':len_val_or_expression, 'OUTPUT': outputlayer}

    if type(len_val_or_expression) == str:
        parameter_dict['LENGTH'] = QgsProperty.fromExpression(len_val_or_expression)

    return processing.run('native:splitlinesbylength',parameter_dict)['OUTPUT']


def vec_layers_intersection(inputlayer,overlay_layer,outputlayer='TEMPORARY_OUTPUT'):

    parameter_dict = {'INPUT': inputlayer,'OVERLAY':overlay_layer, 'OUTPUT': outputlayer}

    return processing.run('qgis:intersection',parameter_dict)['OUTPUT']


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


def dissolve_tosinglegeom(inputlayer,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:dissolve',parameter_dict)['OUTPUT']


def merge_touching_lines(inputlayer,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:mergelines',parameter_dict)['OUTPUT']


def polygonize_lines(inputlines,outputlayer='TEMPORARY_OUTPUT',keepfields=True):
    parameter_dict = {'INPUT': inputlines, 'OUTPUT': outputlayer}

    return processing.run('native:polygonize',parameter_dict)['OUTPUT']


def convex_hulls(inputlayer,outputlayer='TEMPORARY_OUTPUT',keepfields=True):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer,'KEEP_FIELDS':keepfields}

    return processing.run('native:convexhull',parameter_dict)['OUTPUT']

def snap_layers(inputlayer,snap_layer,behavior_code=1,tolerance=0.1,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer,'REFERENCE_LAYER':snap_layer,'TOLERANCE':tolerance,'BEHAVIOR':behavior_code}

    return processing.run('native:snapgeometries',parameter_dict)['OUTPUT']

def extract_lines_from_polygons(input_polygons,outputlayer='TEMPORARY_OUTPUT'):
    parameter_dict = {'INPUT': input_polygons, 'OUTPUT': outputlayer}

    return processing.run('native:polygonstolines',parameter_dict)['OUTPUT']

def collected_geoms_layer(inputlayer,outputlayer='TEMPORARY_OUTPUT'):
    '''
    interface to 
    https://docs.qgis.org/3.22/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html#qgiscollect
    '''
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer}

    return processing.run('native:collect',parameter_dict)['OUTPUT']

def gen_centroids_layer(inputlayer,outputlayer='TEMPORARY_OUTPUT',for_allparts=False):
    parameter_dict = {'INPUT': inputlayer, 'OUTPUT': outputlayer,'ALL_PARTS':for_allparts}

    return processing.run('native:centroids',parameter_dict)['OUTPUT']

def get_intersections(inputlayer,intersect_layer,outputlayer):
    parameter_dict = {'INPUT': inputlayer, 'INTERSECT': intersect_layer, 'OUTPUT': outputlayer}

    return processing.run('qgis:lineintersections',parameter_dict)['OUTPUT']

def cliplayer_v2(inputlayer,overlay_lyr,outputlayer):
    """
        the first one was intended for datafiles, not memeory layers
    """
    parameter_dict = {'INPUT': inputlayer, 'OVERLAY': overlay_lyr, 'OUTPUT': outputlayer}

    return processing.run('qgis:clip',parameter_dict)['OUTPUT']

def reproject_layer(inputlayer,destination_crs='EPSG:4326',output_mode='memory:Reprojected'):
    parameter_dict = {'INPUT': inputlayer, 'TARGET_CRS': destination_crs,'OUTPUT': output_mode}

    return processing.run('native:reprojectlayer', parameter_dict)['OUTPUT']


def split_lines(inputlayer,splitterlayer,outputlayer='TEMPORARY_OUTPUT'):

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
        create a new field for the layer, and also return the index of the new field 
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

def create_fill_id_field(inputlayer,fieldname = 'id_on_layer'):

    created_field_index = create_new_layerfield(inputlayer,fieldname,QVariant.Int)

    with edit(inputlayer):
        for feature in inputlayer.getFeatures():
            inputlayer.changeAttributeValue(feature.id(),created_field_index,feature.id())



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





def get_major_dif_signed(inputval,inputdict,tol=0.5,print_diffs=False):
    '''
        in spite of finding a simple way to obtain the 'orthogonal' distance and ID of the orthonogal feature
    '''

    diffs = {} # []

    for key in inputdict:
        # always avoid to compare floats equally
        if not isclose(inputval,inputdict[key],abs_tol=tol):
            diffs[key] = inputdict[key]-inputval #.append(inputdict[key]-inputval)
        else:
            refused_key = key

    if print_diffs:
        print(diffs)

    if diffs:
        if len(diffs) > 1:
            key_maxdif = max(diffs,key=diffs.get)
            return inputval+diffs[key_maxdif],key_maxdif
        else:
            # dict with only one key:
            only_key = next(iter(diffs)) # thx: https://stackoverflow.com/a/46042617/4436950
            return inputval+diffs[only_key],only_key
    else:
        return inputval,refused_key

def geom_to_feature(inputgeom,attrs_list=None):
    # remember that inplace methods generally have a return that isn't the object itself #lessons

    ret_feat = QgsFeature()

    ret_feat.setGeometry(inputgeom)

    if attrs_list:
        ret_feat.setAttributes(attrs_list)

    return ret_feat

def layer_from_featlist(featlist,layername=None,geomtype="Point",attrs_dict=None,output_type = 'memory'):
    '''
        creating a layer from a list of features (not geometries)

        geomtype must be one of:
        [“point”, “linestring”, “polygon”, “multipoint”,”multilinestring”,”multipolygon”]
    '''

    lname = 'temp'

    if layername:
        lname = layername

    ret_layer =  QgsVectorLayer(geomtype, lname, output_type)

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

def keep_only_contained_within(inputlayer,geomlayer):

    geomtocheck = get_first_feature_or_geom(geomlayer,True)

    with edit(inputlayer):
        for feature in inputlayer.getFeatures():
            if not feature.geometry().within(geomtocheck):
                inputlayer.deleteFeature(feature.id())

def feature_from_fid(inputlayer,fid):
    """
        could be a little less burocratic, but...
    """

    # thx: https://gis.stackexchange.com/a/59185/49900

    feat_iterator = inputlayer.getFeatures(QgsFeatureRequest().setFilterFid(fid))

    ret_feat = QgsFeature()

    feat_iterator.nextFeature(ret_feat)

    return ret_feat


def points_intersecting_buffer_boundary(input_point,inputlayer,featlist=None,buffersize=1,segments=5):
    '''
        inputlayer must have geometries of Line type
    '''

    boundary = input_point.buffer(buffersize,segments).convertToType(1) # 1 is the value for "LineGeometry" in https://qgis.org/api/classQgsWkbTypes.html

    # list storing the points that shall be returned:
    ret_list = []


    feat_request = QgsFeatureRequest()

    if featlist:
        feat_request.setFilterFids(featlist)



    for feature in inputlayer.getFeatures(feat_request):
        # ret_list.append(boundary.intersection(feature.geometry()))
        ret_list.append(feature.geometry().intersection(boundary))




    return ret_list


def qgsgeom_to_pointuple(inputgeom):
    # TODO (if needed): consider Z or M

    p = inputgeom.asPoint()

    return p.x(),p.y()

def point_forms_minor_angle_w2(fixedpoint_A,centerpoint_B,pointlist,return_index=False,max_instead=False,print_angles=False):
    '''
        that is: the point that will forms the minor angle, compared to other angles spawn by the other points.

        All angles are formed in conjunction with fixed points A and B
    '''

    if len(pointlist) == 0:
        if return_index:
            return 0
        else:
            return(pointlist[0])

    else:
        anglelist = []

        pA = qgsgeom_to_pointuple(fixedpoint_A)

        pB = qgsgeom_to_pointuple(centerpoint_B)


        for point in pointlist:
            pC = qgsgeom_to_pointuple(point)


            angle = QgsGeometryUtils.angleBetweenThreePoints(*pA,*pB,*pC) * (180/pi)

            if angle > 180:
                angle = 360 - angle

            anglelist.append(angle)

        if print_angles:
            print(anglelist)

        index = anglelist.index(min(anglelist))

        if return_index:
            return index
        else:
            return pointlist[index]


def vector_from_2_pts(point_A,point_B,desiredLen = None,normalized=False):

    pA = qgsgeom_to_pointuple(point_A)

    pB = qgsgeom_to_pointuple(point_B)

    dx = pB[0] - pA[0]

    dy = pB[1] - pA[1]

    ret_vec = QgsVector(dx,dy)

    if desiredLen:
        return ret_vec.normalized() * desiredLen
    else:
        if normalized:
            return ret_vec.normalized()
        else:
            return ret_vec

def check_sidewalk_intersection(intersectiongeom,referencepoint):
    if not intersectiongeom.isEmpty():
        if not intersectiongeom.isMultipart():
            return True,intersectiongeom
        else:
            # if it returns Multipart geometry, it was because there are 2 points of intersection, so we chose the nearer to "referencepoint"
            as_geomcollection = intersectiongeom.asGeometryCollection()


            distances = [referencepoint.distance(point.asPoint()) for point in as_geomcollection]

            return True,as_geomcollection[distances.index(min(distances))]


    else:
        # if there's no intersection point it's because the vector length isn't enough in order to make it, so we need to enlarge that vector
        return False,None

def interpolate_by_percent(inputline,percent):
    len = inputline.length()

    len_at_perc = (len/100) * percent

    return inputline.interpolate(len_at_perc)

def get_bbox4326_currCRS(inputbbox,current_crs):
    # thx: https://kartoza.com/en/blog/how-to-quickly-transform-a-bounding-box-from-one-crs-to-another-using-qgis/
    dest_crs = QgsCoordinateReferenceSystem(current_crs)
    source_crs = QgsCoordinateReferenceSystem('EPSG:4326')

    transformer = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())

    return transformer.transformBoundingBox(inputbbox)

def select_vertex_pol_nodes(inputpolygonfeature,minC_angle=160,maxC_angle=200):
    # there are some points at protoblocks that are irrelevant, i.e. they're not actual corners

    polygon_vertex_list = inputpolygonfeature.geometry().asPolygon()[0]
    del polygon_vertex_list[-1] # as the polygon list repeats the first node

    centroid = inputpolygonfeature.geometry().centroid() #.asPoint()
    # print(centroid)
    prev_size = len(polygon_vertex_list)

    # anglelist = []

    idx_to_remove = []


    for i,node in enumerate(polygon_vertex_list):

        prev = i-1
        next = i+1

        if i == len(polygon_vertex_list)-1:
            next = 0


        pA = polygon_vertex_list[prev]
        pB = node
        pC = polygon_vertex_list[next]

        angle = QgsGeometryUtils.angleBetweenThreePoints(*pA,*pB,*pC) * (180/pi)

        # print(pA,pB,pC)

        if angle > minC_angle and angle < maxC_angle:
            idx_to_remove.append(i)

        # anglelist.append(int(angle))

    for idx in sorted(idx_to_remove,reverse=True):
        # TODO: a missing thx here!!!
        del  polygon_vertex_list[idx]

    return polygon_vertex_list

    # print(prev_size,len(polygon_vertex_list))


    # for i,node in enumerate(polygon_vertex_list):

    #     prev = i-1
    #     next = i+1

    #     if i == len(polygon_vertex_list)-1:
    #         next = 0


    #     pA = polygon_vertex_list[prev]
    #     pB = node
    #     pC = polygon_vertex_list[next]

    #     angle = QgsGeometryUtils.angleBetweenThreePoints(*pA,*pB,*pC) * (180/pi)

    #     print(angle)


def create_incidence_field_layers_A_B(inputlayer,incident_layer,fieldname='incident'):

    field_id = create_new_layerfield(inputlayer,fieldname,QVariant.String)

    with edit(inputlayer):

        for feature in inputlayer.getFeatures():

            contained_ids = []
            for tested_feature in incident_layer.getFeatures():
                if feature.geometry().contains(tested_feature.geometry()):
                    contained_ids.append(str(tested_feature.id()))

            inputlayer.changeAttributeValue(feature.id(),field_id,' '.join(contained_ids))

def pointlist_to_multipoint(inputpointgeomlist):

    as_pointXYList = [geom.asPoint() for geom in inputpointgeomlist]

    return QgsGeometry.fromMultiPointXY(as_pointXYList)

def segments_to_add_points_tolinelayer(input_linelayer,pointgeomlist,buffer_d=1):

    # print(len(pointgeomlist))
    # to multipoint to simplify incidence for each feature in inputlayer
    as_geom = pointlist_to_multipoint(pointgeomlist)

    segments_list = []

    for feature in input_linelayer.getFeatures():
        buffer = feature.geometry().buffer(buffer_d,5)

        centroid = buffer.centroid()

        # incident points on buffer
        incident_list = buffer.intersection(as_geom)



        # creating the segments:
        for point in incident_list.asMultiPoint():

            desired_vec_len = centroid.distance(QgsGeometry.fromPointXY(point)) + buffer_d

            # using vector to ensure that the line that we will build will really intersect the line
            curr_vec = vector_from_2_pts(centroid,QgsGeometry.fromPointXY(point),desired_vec_len)

            P_forline = centroid.asPoint() + curr_vec

            segments_list.append(QgsGeometry.fromPolyline([QgsPoint(centroid.asPoint()),QgsPoint(P_forline)]))

    segments_asMultiLineString = QgsGeometry.collectGeometry(segments_list)

    segments_asfeatlist = [geom_to_feature(segments_asMultiLineString)]

    segments_aslayer = layer_from_featlist(segments_asfeatlist,'segments_intersections','LineString')

    dissolved_segments_layer = dissolve_tosinglegeom(segments_aslayer)

    # splitted_sidewalks = split_lines(input_linelayer,dissolved_segments_layer)

    return dissolved_segments_layer


def rejoin_splitted_lines(inputlineslayer,incidence_layer,attrs_dict={'highway':QVariant.String,'footway':QVariant.String}):

    rejoined_features = []

    for incidence_feature in incidence_layer.getFeatures():
        incident_features = []

        for possible_inc_feature in inputlineslayer.getFeatures():

            if incidence_feature.geometry().contains(possible_inc_feature.geometry()):
                incident_features.append(possible_inc_feature.geometry())

                attrs = possible_inc_feature.attributes()

        rejoinded_multipart = QgsGeometry.collectGeometry(incident_features)

        as_singleline = rejoinded_multipart.mergeLines()

        as_singleline.removeDuplicateNodes(0.000001)

        rejoined_features.append(geom_to_feature(as_singleline,attrs))

    return layer_from_featlist(rejoined_features,'rejoined_part1','LineString',attrs_dict=attrs_dict)

def swap_features_layer_another(inputdesiredlayer,layer_with_newfeatures):
    """
        swapping features, presuming same type and same fields
    """

    with edit(inputdesiredlayer):

        # first deleting all features
        for old_feature in inputdesiredlayer.getFeatures():
            inputdesiredlayer.deleteFeature(old_feature.id())

        # then inserting from the other
        for new_feature in layer_with_newfeatures.getFeatures():
            inputdesiredlayer.addFeature(new_feature)

def read_json(inputpath):
    with open(inputpath) as reader:
        data = reader.read()

    return json.loads(data)

def dump_json(inputdict,outputpath):
    with open(outputpath,'w+') as json_handle:
        json.dump(inputdict,json_handle)

def merge_geojsons(input_pathlist,outputpath):
    '''
        simple function to merge geojsons without using any library.

        Same CRS for all files is required.
    '''

    ref_dict = None

    for i,path in enumerate(input_pathlist):


        if i == 0:
            ref_dict = read_json(path)

        else:
            ref_dict['features'] += read_json(path)['features']


    dump_json(ref_dict,outputpath)