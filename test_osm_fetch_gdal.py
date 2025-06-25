import sys
import os

# Assuming osm_fetch.py is in the same directory or accessible via PYTHONPATH
# For local testing, if osm_fetch.py is in the root of the repo:
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

try:
    from osm_fetch import get_osm_data, osm_query_string_by_bbox

    print("Successfully imported osm_fetch modules.")
except ImportError as e:
    print(f"Error importing osm_fetch: {e}")
    sys.exit(1)


def run_test():
    print("Starting test...")

    # Define a test bounding box (e.g., a small area in Heidelberg)
    min_lat, min_lgt, max_lat, max_lgt = 49.39, 8.67, 49.42, 8.71

    # Query for amenities (e.g., cafes) - points
    print(f"Generating query string for points (amenity=cafe)...")
    point_query_string = osm_query_string_by_bbox(
        min_lat,
        min_lgt,
        max_lat,
        max_lgt,
        interest_key="amenity",
        interest_value="cafe",
        node=True,
        way=False,
        relation=False,  # Query only nodes for points
        print_querystring=True,
    )

    temp_filename_points = "test_heidelberg_cafes_points"
    geom_type_points = "Point"

    print(
        f"\nFetching point data for '{geom_type_points}' with temp name '{temp_filename_points}'..."
    )
    try:
        # Test with return_as_string=True
        geojson_points_str = get_osm_data(
            point_query_string,
            temp_filename_points,
            geomtype=geom_type_points,
            return_as_string=True,
            timeout=60,  # Increased timeout for Overpass query
        )
        if geojson_points_str:
            print(
                f"Successfully fetched point data as string. Length: {len(geojson_points_str)}"
            )
            # print("Point GeoJSON String (first 500 chars):", geojson_points_str[:500])
            # Further checks could involve parsing the JSON and checking structure
        else:
            print("Failed to fetch point data or no data returned.")

        # Test with return_as_string=False (saves to file)
        # To avoid issues with QGIS paths, this test will expect the file in the CWD's 'temporary' folder
        # Ensure 'temporary' folder exists or osm_fetch creates it.
        # The join_to_a_outfolder function in osm_fetch.py uses a 'temporary' subfolder relative to basepath.
        # For this standalone test, we might need to adjust expectations or mock basepath if it's complex.
        # For now, let's assume join_to_a_outfolder works and creates ./temporary/ if basepath is '.'

        # Create a dummy 'temporary' folder for the test if it doesn't exist
        # and set basepath for osm_fetch to current dir for this test.
        # This is a bit of a hack for standalone testing.
        original_basepath = None
        if "basepath" in sys.modules["osm_fetch"].__dict__:
            original_basepath = sys.modules["osm_fetch"].basepath
            sys.modules["osm_fetch"].basepath = "."  # Override basepath for test

        temp_dir = "temporary"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            print(f"Created directory: {temp_dir}")

        print(f"\nFetching point data again, this time saving to file...")
        geojson_points_filepath = get_osm_data(
            point_query_string,
            temp_filename_points,
            geomtype=geom_type_points,
            return_as_string=False,
            timeout=60,
        )
        if geojson_points_filepath:
            print(f"Successfully fetched point data to file: {geojson_points_filepath}")
            if os.path.exists(geojson_points_filepath):
                print(f"File '{geojson_points_filepath}' confirmed to exist.")
                # Optional: Read and verify content
                # with open(geojson_points_filepath, 'r') as f:
                #     print(f"File content (first 500 chars): {f.read(500)}")
            else:
                print(f"File '{geojson_points_filepath}' NOT found.")
        else:
            print("Failed to fetch point data to file or no data returned.")

        # Restore original basepath if changed
        if original_basepath is not None:
            sys.modules["osm_fetch"].basepath = original_basepath

    except Exception as e:
        print(f"An error occurred during get_osm_data call: {e}")
        import traceback

        traceback.print_exc()

    # Query for ways (e.g., roads)
    # print(f"\nGenerating query string for ways (highway=residential)...")
    # way_query_string = osm_query_string_by_bbox(
    #     min_lat, min_lgt, max_lat, max_lgt,
    #     interest_key="highway", interest_value="residential",
    #     node=False, way=True, relation=False,
    #     print_querystring=True
    # )
    # temp_filename_ways = "test_heidelberg_roads_ways"
    # geom_type_ways = "LineString"

    # print(f"\nFetching line data for '{geom_type_ways}' with temp name '{temp_filename_ways}'...")
    # try:
    #     geojson_ways_filepath = get_osm_data(
    #         way_query_string,
    #         temp_filename_ways,
    #         geomtype=geom_type_ways,
    #         return_as_string=False, # Save to file
    #         timeout=60
    #     )
    #     if geojson_ways_filepath:
    #         print(f"Successfully fetched line data to file: {geojson_ways_filepath}")
    #         if os.path.exists(geojson_ways_filepath):
    #             print(f"File '{geojson_ways_filepath}' confirmed to exist.")
    #         else:
    #             print(f"File '{geojson_ways_filepath}' NOT found.")
    #     else:
    #         print("Failed to fetch line data to file or no data returned.")
    # except Exception as e:
    #     print(f"An error occurred during get_osm_data call for ways: {e}")
    #     import traceback
    #     traceback.print_exc()

    print("\nTest finished.")


if __name__ == "__main__":
    run_test()
