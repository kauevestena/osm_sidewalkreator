# SidewalKreator Algorithm Description

This document describes the step-by-step algorithm executed by the OSM SidewalKreator QGIS plugin (GUI) and how the same logic is mirrored in the headless QGIS Processing algorithms under `processing/`.

## Step 1: Data Fetching (`call_get_osm_data`)

This is the initial step where the plugin acquires the necessary map data from OpenStreetMap (OSM).

1.  **Input Area**: The user selects a polygon layer in QGIS and a specific feature from that layer which defines the area of interest.
2.  **Bounding Box**: The bounding box of the selected polygon feature is calculated.
3.  **Overpass Query**: An Overpass API query is constructed using the calculated bounding box to fetch all `highway` and `building` features within that area. The user can set a timeout for the API request.
4.  **Data Acquisition**: The plugin sends the query to the Overpass API and retrieves the data in GeoJSON format.
5.  **Clipping**: The retrieved OSM data (roads) is clipped precisely to the boundary of the user-selected input polygon.
6.  **Reprojection**: The clipped data is reprojected from the standard WGS 84 (EPSG:4326) to a custom local Transverse Mercator projection. The center of the bounding box is used as the central meridian for this projection. This is crucial for minimizing distortion and allowing for accurate metric measurements (e.g., buffer distances in meters).
7.  **Building and Address Data**:
    *   If the user has not opted to ignore buildings, the plugin fetches `building` polygons.
    *   It also fetches nodes tagged with `addr:housenumber` to get address locations.
    *   If either building or address data is found, a "Points of Interest" (POIs) layer is created by merging the centroids of the building polygons and the address nodes. This layer is used later for advanced sidewalk splitting.
8.  **UI Population**: The plugin identifies all unique values of the `highway` tag from the fetched road data (e.g., `residential`, `tertiary`, `primary`). It populates a table in the UI with these values, allowing the user to specify a default width in meters for each road type.

## Step 2: Data Cleaning and Preparation (`data_clean`)

Once the data is fetched, this step processes it to make it suitable for generating sidewalks.

1.  **Filter Roads**: Roads corresponding to `highway` tags that the user has set to a width of 0 are removed from the dataset. This allows the user to exclude certain road types from the analysis. Existing ways tagged as `footway=sidewalk` or `footway=crossing` are identified and stored separately.
2.  **Protoblock Creation**: The road network is polygonized to create "protoblocks". These are the enclosed areas formed by the road network, analogous to city blocks.
3.  **Filter Existing Sidewalks**: The plugin checks if any protoblocks already contain a significant network of `footway=sidewalk` ways. If the area of the existing sidewalks within a protoblock is above a certain percentage of the protoblock's area, that protoblock is removed, preventing the plugin from drawing sidewalks where they already exist.
4.  **Network Simplification**:
    *   The road lines are split at every intersection to create individual segments.
    *   The user can specify a number of iterations to remove "dead-end" streets (segments that do not form part of a closed block), which helps clean the road network topology.
5.  **Intersection Calculation**: The precise locations of all road intersections are calculated and stored as a point layer.
6.  **Width Assignment**: The width specified by the user in the UI table (or a default value) is assigned as an attribute to each road segment.

## Step 3: Sidewalk Generation (`draw_sidewalks` / Processing)

This is the core step where the actual sidewalk geometries are created.

1.  **Building Overlap Check**: If the user has enabled this option, the algorithm adjusts road widths to prevent generated sidewalks from overlapping existing building polygons. For each road segment, it calculates the distance to the nearest building. If a sidewalk would overlap, its width is reduced to maintain a minimum user-specified distance from the building.
2.  **Buffering**: The primary method for creating sidewalks is buffering:
    *   A buffer is generated around each road segment. The buffer distance is dynamic, calculated as `(road_width / 2) + (user_defined_extra_distance / 2)`.
    *   These individual buffers are dissolved into a single polygon representing the entire road network area.
    *   To create smooth, rounded corners at intersections, a two-step buffering process is applied: a positive buffer is created with a user-defined "Curve Radius", and then a negative buffer of the same radius is applied.
3.  **Sidewalk Extraction (Difference Method)**:
    *   A very large buffer is created around the entire dissolved road network buffer.
    *   The algorithm then computes the geometric "difference" between this large buffer and the road network buffer.
    *   The result of the difference operation is a layer containing the polygons that fall *outside* the road network. The largest of these polygons (the area surrounding the entire map extent) is discarded, leaving only the internal polygons, which are the sidewalks.
4.  **Polygon to Line Conversion**: The sidewalk polygons are converted into line geometries, representing the edges of the sidewalks.
5.  **Exclusion/Sure Zones**: The plugin handles `sidewalk=no/left/right/both` tags by creating "exclusion zones" (from `sidewalk=no`, etc.) and "sure zones" (from `sidewalk=yes/both`, etc.). The exclusion zone polygons are subtracted from the generated sidewalk layer. This is implemented headlessly in `processing/sidewalk_generation_logic.py`.
6.  **Attribute Calculation**: Area, perimeter, and shape ratios are calculated for the sidewalk polygons for potential quality analysis.
7.  **Protoblock Filtering**: Sidewalk lines are filtered to those intersecting dissolved protoblocks to remove disjoint segments. Processing algorithms do this automatically.
8.  **Pre-existing Sidewalk Filtering**: To avoid drawing where sidewalks already exist in OSM, protoblocks already “filled” with `footway=sidewalk` are removed before generation. Coverage is estimated by incident sidewalk length and compared against `cutoff_percent_protoblock` (see `parameters.py`). Implemented in both `full_sidewalkreator_polygon_algorithm.py` and `full_sidewalkreator_bbox_algorithm.py`.

## Step 4: Crossing Generation (`draw_crossings`)

This step adds pedestrian crossings at intersections.

1.  **Identify Intersection Points**: The algorithm identifies intersections where three or more road segments meet, as these are candidates for crossings.
2.  **Calculate Crossing Geometry**: For each road segment approaching a valid intersection:
    *   An "inner point" is calculated a short distance inward from the intersection along the road's centerline.
    *   The direction of the crossing is determined based on user choice: either perpendicular to the current road segment or parallel to the main intersecting road.
    *   A line is projected from the inner point across the street in the calculated direction until it intersects the sidewalk line on the opposite side.
    *   This process defines the centerline of the crossing. Points along this line are created to represent the kerbs (`barrier=kerb`).
3.  **Quality Control**: The length of the generated crossing is compared to the expected width of the street. If the crossing is significantly longer than expected (e.g., at a skewed intersection), it is flagged and can be automatically removed by the user.

## Step 5: Sidewalk Splitting (`sidewalks_splitting`)

This function subdivides the continuous sidewalk lines into smaller, more practical segments for mapping.

1.  **Split at Block Corners**: The sidewalks are first split at the corners of the protoblocks.
2.  **Advanced Splitting Rules**: The user can choose one or more of the following methods for further splitting:
    *   **Voronoi Polygons**: If the POI layer (from building centroids/addresses) is available, the algorithm generates Voronoi polygons around these points within each protoblock. The sidewalks are then split where they intersect the boundaries of these Voronoi cells. This is useful for associating sidewalk segments with specific building facades or addresses.
    *   **Maximum Length**: Sidewalks are split into segments that do not exceed a user-defined maximum length.
    *   **Number of Segments**: Each sidewalk section (e.g., along one side of a block) is split into a user-defined number of equal-length segments.
3.  **Topological Cleaning**: After splitting, the algorithm performs snapping and removes duplicate vertices to ensure the final sidewalk network is topologically correct. It also attempts to merge very short segments with their neighbors to avoid creating unnecessarily tiny features.

## Step 6: Output Generation (`outputting_files`)

The final step prepares and exports all the generated data.

1.  **Data Finalization**: The final layers (sidewalks, crossings, kerbs) are cleaned of any temporary attributes. The kerb layer is regenerated from the final set of crossings to ensure consistency.
2.  **File Export**:
    *   An output folder is created.
    *   The final sidewalk, crossing, and kerb layers are reprojected back to WGS 84 (EPSG:4326) and saved as separate GeoJSON files.
3.  **Merged GeoJSON**: To simplify importing into JOSM (a popular OSM editor), the individual GeoJSON files are merged into a single `sidewalkreator_output.geojson` file. GeoJSON format supports mixed geometry types, so this file contains the line-based sidewalks and crossings alongside the point-based kerbs.
4.  **Auxiliary Files**: Additional data generated during the process, such as the input polygon, protoblocks, and road intersection points, are saved in an auxiliary folder for reference.
5.  **Changeset Comment**: A text file is generated containing a recommended changeset comment for when the user uploads the data to OpenStreetMap.
6.  **Parameters Dump**: The state of all user-configurable options in the plugin dialog is saved to a JSON file, allowing the user to easily replicate a previous run.

## Notes for Processing Algorithms

- Primary outputs (e.g., sidewalks) are returned as in-memory layers in EPSG:4326, suitable for headless workflows and tests.
- Exclusion/sure zones, protoblock filtering, and the pre-existing sidewalk filter are implemented to match the GUI behavior as closely as possible.
- When building data is unavailable, overlap-aware width adjustment is skipped and sensible defaults are applied.
