"""
osm_fetch.py created for import and convert the desired OSM data
"""

import requests, os, time, json, tempfile

# import codecs
# import geopandas as gpd
# from geopandas import read_file
from osgeo import ogr
import re  # For parsing other_tags
from itertools import cycle

# from qgis.core import QgsApplication # Keep QgsApplication for now, path logic was adjusted
try:
    from qgis.core import QgsApplication
except ImportError:
    # This allows the module to be imported outside QGIS, e.g. for standalone scripts or tests
    # However, functionality relying on QgsApplication (like profile path) will not work.
    # A default basepath is set below in that case.
    QgsApplication = None

# doing some stuff again to avoid circular imports:
# homepath = os.path.expanduser('~')

if QgsApplication:
    try:
        profilepath = QgsApplication.qgisSettingsDirPath()
        base_pluginpath_p2 = "python/plugins/osm_sidewalkreator"
        basepath = os.path.join(profilepath, base_pluginpath_p2)
    except Exception as e:  # Other QGIS related errors
        print(
            f"Error obtaining QGIS paths in osm_fetch: {e}. Setting basepath to current working directory."
        )
        basepath = "."
else:
    print(
        "QGIS context not found, setting basepath to current working directory for osm_fetch module."
    )
    basepath = "."


"""
## MAJOR TODO: evaluate the use of "import gdal" to use gdal ogr api and osm driver to convert the .osm files, leaving zero external dependencies...
"""


def delete_filelist_that_exists(filepathlist):
    for filepath in filepathlist:
        if os.path.exists(filepath):
            os.remove(filepath)


def join_to_a_outfolder(filename, foldername="temporary"):
    outfolder = os.path.join(basepath, foldername)

    return os.path.join(outfolder, filename)


def osm_query_string_by_bbox(
    min_lat,
    min_lgt,
    max_lat,
    max_lgt,
    interest_key="highway",
    node=False,
    way=True,
    relation=False,
    print_querystring=False,
    interest_value=None,
    dump_path=None,
):

    node_part = way_part = relation_part = ""

    query_bbox = f"{min_lat},{min_lgt},{max_lat},{max_lgt}"

    interest_value_part = ""

    if interest_value:
        interest_value_part = f'="{interest_value}"'

    if node:
        node_part = f'node["{interest_key}"{interest_value_part}]({query_bbox});'
    if way:
        way_part = f'way["{interest_key}"{interest_value_part}]({query_bbox});'
    if relation:
        relation_part = (
            f'relation["{interest_key}"{interest_value_part}]({query_bbox});'
        )

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
        with open(dump_path, "w+") as querydumper:
            querydumper.write(overpass_query)

    return overpass_query


# filter_gjsonfeats_bygeomtype function removed as its functionality is integrated into get_osm_data


def get_osm_data(
    querystring,
    tempfilesname,
    geomtype="LineString",
    print_response=False,
    timeout=30,
    return_as_string=False,
):
    """
    get the osmdata and stores in files or in a geojson string, also generates temporary files
    """

    overpass_url_list = [
        "http://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
        "https://overpass.openstreetmap.fr/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    # to iterate circularly, thx: https://stackoverflow.com/a/23416519/4436950
    circular_iterator = cycle(overpass_url_list)

    overpass_url = next(circular_iterator)

    while True:
        # TODO: ensure sucess
        #   (the try statement is an improvement already)
        print(f"[osm_fetch DEBUG] Value of 'timeout' before requests.get: {timeout}, type: {type(timeout)}") # DEBUG PRINT
        try:
            response = requests.get(
                overpass_url, params={"data": querystring}, timeout=timeout
            )

            if response.status_code == 200:
                print(f"Request to {overpass_url} successful (status 200).")
                break
            else:
                print(f"Request to {overpass_url} failed with status: {response.status_code}, Response: {response.text[:500]}") # Log more of response

        except requests.exceptions.Timeout as e_timeout:
            print(f"TIMEOUT during request to {overpass_url}: {e_timeout}")
        except requests.exceptions.ConnectionError as e_conn_err:
            print(f"CONNECTION ERROR during request to {overpass_url}: {e_conn_err}")
        except requests.exceptions.RequestException as e_req:
            print(f"Request to {overpass_url} failed with RequestException: {e_req}")
        except Exception as e_generic:
            print(f"Request to {overpass_url} failed with generic Exception: {e_generic}")

        # If not successful, try next server after a delay
        print(f"Request to {overpass_url} not successful, retrying in 5 seconds...") # Clarified message
        time.sleep(5)
        overpass_url = next(circular_iterator) # This was outside the try-except, should be part of the loop logic for retrying
        print("Retrying with server:", overpass_url) # Clarified message

    # Check if the loop completed due to success or exhaustion of retries (though current loop is infinite until success)
    # This part of the code is reached ONLY if 'break' was hit (i.e. status_code == 200)
    # If all servers failed indefinitely, this part wouldn't be reached with the current while True / break structure.
    # A counter for retries might be good to eventually give up.

    if response.status_code != 200:
        print(f"Failed to fetch data from all Overpass servers. Last attempt was to {overpass_url} with status {response.status_code}.")
        return None # Explicitly return None if all retries failed (if we add a retry limit)

    if print_response:
        print(response)

    xml_filecontent = response.text

    geojson_datadict = None
    temp_osm_file_path = None  # Initialize to ensure it's available in finally
    datasource = None  # Initialize for finally block
    ogr_layer = None  # Initialize for finally block
    # ogr_feature is usually handled in loop, but good to be explicit if needed outside

    try:
        # Save xml_filecontent to a temporary .osm file
        # delete=False is important because GDAL needs to open it by path.
        # We will manually delete it in the finally block.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".osm", delete=False, encoding="utf-8"
        ) as tmp_osm:
            tmp_osm.write(xml_filecontent)
            temp_osm_file_path = tmp_osm.name

        datasource = ogr.Open(temp_osm_file_path)
        if datasource is None:
            print(
                f"Error: Could not open OSM data from {temp_osm_file_path} using GDAL."
            )
            return None  # Or raise an appropriate exception

        # Determine OGR layer name based on geomtype
        if geomtype == "Point":
            layer_name = "points"
        elif geomtype == "LineString":
            layer_name = "lines"
        elif geomtype == "Polygon" or geomtype == "MultiPolygon":  # Handle both
            layer_name = "multipolygons"
        else:
            print(f"Unsupported geometry type: {geomtype}")
            return None

        ogr_layer = datasource.GetLayerByName(layer_name)
        if ogr_layer is None:
            print(
                f"Error: Layer '{layer_name}' not found in {temp_osm_file_path}. Available layers:"
            )
            if datasource:  # Check datasource is not None
                for i in range(datasource.GetLayerCount()):
                    lyr = datasource.GetLayer(i)
                    if lyr:
                        print(f"  - {lyr.GetName()}")
            return None

        features_list = []
        ogr_feature = ogr_layer.GetNextFeature()  # Initialize first feature
        while ogr_feature:
            geom = ogr_feature.GetGeometryRef()
            geom_geojson_dict = None  # Initialize for current feature
            if geom:
                try:
                    geom_geojson_str = geom.ExportToJson()
                    geom_geojson_dict = json.loads(geom_geojson_str)
                except Exception as e:
                    print(
                        f"Warning: Error exporting geometry to GeoJSON for a feature: {e}"
                    )

            properties = {}
            for i in range(ogr_feature.GetFieldCount()):
                field_defn = ogr_feature.GetFieldDefnRef(i)
                properties[field_defn.GetNameRef()] = ogr_feature.GetField(i)

            # Handle 'other_tags' (HSTORE string) from GDAL OSM driver
            # This is crucial for replicating the old tag flattening behavior
            if "other_tags" in properties and properties["other_tags"] is not None:
                try:
                    tags_str = properties["other_tags"]
                    parsed_tags = {}
                    if isinstance(tags_str, str) and tags_str.strip():
                        # Regex to find "key"=>"value" pairs. Handles escaped quotes in values poorly.
                        # A more robust HSTORE parser might be needed for complex cases.
                        # Example: '"highway"=>"residential","name"=>"Main Street"'
                        for match in re.finditer(
                            r'"([^"]+)"=>"((?:[^"]|"")*)"', tags_str
                        ):
                            key, value = match.groups()
                            # GDAL HSTORE values might double-escape quotes, e.g. "" for a single "
                            parsed_tags[key] = value.replace('""', '"')

                        # If regex fails or for simpler non-HSTORE "key=value,key2=value2" (less common for other_tags)
                        if not parsed_tags and "=>" not in tags_str:
                            for pair in tags_str.split(","):  # Fallback attempt
                                if "=" in pair:
                                    k, v = pair.split("=", 1)
                                    parsed_tags[k.strip()] = v.strip()

                        if parsed_tags:
                            properties.update(parsed_tags)
                            # Optionally delete the original 'other_tags' field if it's not desired in final properties
                            # del properties['other_tags']
                except Exception as e:
                    print(
                        f"Warning: Could not parse 'other_tags' field content: '{properties.get('other_tags', '')}'. Error: {e}"
                    )

            features_list.append(
                {
                    "type": "Feature",
                    "geometry": geom_geojson_dict,  # This can be None if geometry export failed
                    "properties": properties,
                }
            )
            ogr_feature.Destroy()  # Destroy feature to free memory within the loop
            ogr_feature = ogr_layer.GetNextFeature()  # Get next feature

        geojson_datadict = {"type": "FeatureCollection", "features": features_list}

    finally:
        # Cleanup GDAL objects explicitly
        ogr_feature = None  # Ensure reference is cleared if loop was exited prematurely
        ogr_layer = None
        if datasource is not None:
            # datasource.Release() # Generally not needed for ogr.Open with Python bindings
            datasource = None

        # Ensure temporary file is deleted
        if temp_osm_file_path and os.path.exists(temp_osm_file_path):
            try:
                os.remove(temp_osm_file_path)
            except OSError as e:
                print(
                    f"Warning: Could not delete temporary OSM file '{temp_osm_file_path}': {e}"
                )

    if geojson_datadict is None:
        print("Conversion failed or produced no data (geojson_datadict is None).")
        return None

    print(
        "Conversion successful with GDAL!"
    )  # Changed print message slightly for clarity

    if return_as_string:
        return json.dumps(geojson_datadict)
    else:
        geojsonfilepath = join_to_a_outfolder(tempfilesname + "_osm.geojson")
        print(
            "GeoJSON will be written to: ", geojsonfilepath
        )  # Changed print message slightly

        # The old code saved an "unfiltered" version. With GDAL layer selection,
        # this is less relevant as we are directly getting the desired geometry types.
        # So, only saving the main geojson_datadict.

        with open(geojsonfilepath, "w+") as geojson_handle:
            json.dump(geojson_datadict, geojson_handle)
        return geojsonfilepath
