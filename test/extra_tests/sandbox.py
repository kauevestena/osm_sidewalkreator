# # import datetime

# # print(datetime.datetime.utcnow().timestamp())

# # import ogr2osm

# # import logging


# # inputpath = "/home/kaue/sidewalkreator_out_1648133887/crossings4326.geojson"

# # outputpath = "/home/kaue/sidewalkreator_out_1648133887/crossings4326.osm"

# # # logger part (test without it)
# # ogr2osmlogger = logging.getLogger('ogr2osm')
# # ogr2osmlogger.setLevel(logging.ERROR)
# # ogr2osmlogger.addHandler(logging.StreamHandler())


# # translation_object = ogr2osm.TranslationBase()
# # datasource = ogr2osm.OgrDatasource(translation_object)
# # datasource.open_datasource(inputpath)

# # osmdata = ogr2osm.OsmData(translation_object)
# # osmdata.process(datasource)

# # datawriter = ogr2osm.OsmDataWriter(outputpath)
# # osmdata.output(datawriter)

# # print()

# import json




# gsonpath1 = "/home/kaue/sidewalkreator_out_1648133887/crossings4326.geojson"

# gsonpath2 = '/home/kaue/sidewalkreator_out_1648133887/kerbs4326.geojson'

# gsonpath3 = '/home/kaue/sidewalkreator_out_1648133887/sidewalks4326.geojson'


# merged_path = '/home/kaue/sidewalkreator_out_1648133887/merged_outputs.geojson'

# gjsonpaths = [gsonpath1,gsonpath2,gsonpath3]




# merge_geojsons(gjsonpaths,merged_path)

# a = {1:2,3:4}


# if 1 in a:
#     print(a[1])

# import ogr2ogr