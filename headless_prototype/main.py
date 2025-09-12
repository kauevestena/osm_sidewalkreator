from sidewalk_creator import SidewalkCreator
import geopandas as gpd

def main():
    """
    Example script to demonstrate the use of the SidewalkCreator class.
    """
    print("Initializing SidewalkCreator...")
    # You can override default configuration parameters here, for example:
    # config = {'dead_end_iterations': 1}
    # creator = SidewalkCreator(**config)
    creator = SidewalkCreator()

    # Define the area of interest
    # This can be a place name, a bounding box, a shapely Polygon, or a GeoDataFrame
    # area = "Piedmont, California"
    # Using a smaller area for a quicker test
    area = "Trafalgar Square, London"

    print(f"Running the full sidewalk creation workflow for: {area}")

    # Run the full workflow
    try:
        final_gdf = creator.run_all(area)

        if final_gdf is not None and not final_gdf.empty:
            print("\nWorkflow successful. Final GeoDataFrame info:")
            final_gdf.info()

            # Save the final output to a GeoJSON file
            output_filename = "sidewalk_output.geojson"
            final_gdf.to_file(output_filename, driver='GeoJSON')
            print(f"\nSuccessfully saved the final output to {output_filename}")
        else:
            print("\nWorkflow completed, but no features were generated.")

    except Exception as e:
        print(f"\nAn error occurred during the workflow: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 50)

    # Example of running only the protoblock generation
    print(f"Running just the protoblock generation for: {area}")
    try:
        # Re-instantiate the creator to start fresh
        protoblock_creator = SidewalkCreator()
        protoblocks_gdf = protoblock_creator.draw_protoblocks(area)

        if protoblocks_gdf is not None and not protoblocks_gdf.empty:
            print("\nProtoblock generation successful. GeoDataFrame info:")
            protoblocks_gdf.info()

            # Save the protoblocks to a GeoJSON file
            protoblocks_filename = "protoblocks_output.geojson"
            protoblocks_gdf.to_file(protoblocks_filename, driver='GeoJSON')
            print(f"\nSuccessfully saved the protoblocks to {protoblocks_filename}")
        else:
            print("\nProtoblock generation completed, but no features were generated.")

    except Exception as e:
        print(f"\nAn error occurred during protoblock generation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
