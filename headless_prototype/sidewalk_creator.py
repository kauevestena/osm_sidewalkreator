import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import split, polygonize, unary_union, snap
from shapely import wkt
from collections import Counter
import numpy as np
import math

class SidewalkCreator:
    """
    A class to create sidewalks and crossings from OpenStreetMap data, independent of QGIS.
    """

    def __init__(self, **kwargs):
        """
        Initializes the SidewalkCreator with configuration parameters.

        Args:
            **kwargs: Configuration parameters that can be overridden.
        """
        # Default configuration parameters, derived from the QGIS plugin's defaults
        self.config = {
            'default_widths': {
                'residential': 5.0,
                'primary': 8.0,
                'secondary': 7.0,
                'tertiary': 6.0,
                'footway': 0.0, # Will be filtered out
            },
            'fallback_default_width': 5.0,
            'protoblocks_buffer': 0.001,
            'min_dist_to_building': 0.5,
            'curve_radius': 10.0,
            'sidewalk_buffer_dist': 1.0, # Corresponds to d_to_add_to_each_side
            'min_sidewalk_width': 0.4, # Corresponds to minimal_buffer * 2
            'kerb_placement_percentage': 0.1,
            'crossing_length_tolerance': 20.0, # Percentage
            'crossing_inward_distance': 1.0,
            'min_road_segment_len': 20.0,
            'use_buildings': True,
            'dead_end_iterations': 0,
            'max_split_length': 50,
            'split_by_max_len': True,
            'split_by_n_segments': False,
            'n_segments_split': 10,
            'cutoff_percent_protoblock': 10.0,
        }
        self.config.update(kwargs)

        # Placeholder attributes for intermediate GeoDataFrames
        self.area_of_interest = None
        self.local_crs = None
        self.gdf_roads_raw = None
        self.gdf_buildings_raw = None
        self.gdf_roads_cleaned = None
        self.gdf_protoblocks = None
        self.gdf_sidewalks = None
        self.gdf_crossings = None
        self.gdf_kerbs = None
        self.final_gdf = None

    def _get_config(self, **kwargs):
        """Helper to merge base config with method-specific overrides."""
        config = self.config.copy()
        config.update(kwargs)
        return config

    def step_1_fetch_data(self, area):
        """
        Fetches and prepares OSM data for the given area.

        Args:
            area: The area of interest. Can be a GeoDataFrame, a Shapely Polygon,
                  a bounding box (tuple of 4), or a place name string.
        """
        print("Step 1: Fetching data...")

        tags = {"highway": True, "building": True}

        if isinstance(area, gpd.GeoDataFrame):
            self.area_of_interest = area
            # Ensure the input GeoDataFrame is in WGS84 for OSMnx
            area_wgs84 = area.to_crs("EPSG:4326")
            gdf = ox.features_from_polygon(area_wgs84.unary_union, tags)
        elif isinstance(area, Polygon):
            self.area_of_interest = gpd.GeoDataFrame([1], geometry=[area], crs="EPSG:4326")
            gdf = ox.features_from_polygon(area, tags)
        elif isinstance(area, tuple) and len(area) == 4:
            # north, south, east, west
            north, south, east, west = area
            self.area_of_interest = None # No specific polygon for clipping later
            gdf = ox.features_from_bbox(north, south, east, west, tags)
        elif isinstance(area, str):
            # Geocode the place name to get a polygon
            self.area_of_interest = ox.geocode_to_gdf(area)
            gdf = ox.features_from_place(area, tags)
        else:
            raise TypeError("Area must be a GeoDataFrame, a Shapely Polygon, a bounding box tuple, or a place name string.")

        # Reset index to make columns like 'highway' accessible
        gdf = gdf.reset_index()

        # Separate roads and buildings
        self.gdf_roads_raw = gdf[gdf['highway'].notna()].copy()
        if self.config.get('use_buildings', True):
            self.gdf_buildings_raw = gdf[gdf['building'].notna()].copy()
        else:
            self.gdf_buildings_raw = gpd.GeoDataFrame(geometry=[])


        # Reproject to a local CRS for accurate measurements
        if not self.gdf_roads_raw.empty:
            # Get the centroid of the roads to determine the local CRS
            centroid = self.gdf_roads_raw.unary_union.centroid
            # Get the UTM zone from the centroid
            utm_crs = self.gdf_roads_raw.estimate_utm_crs(datum_name="WGS 84")
            self.local_crs = utm_crs

            self.gdf_roads_raw = self.gdf_roads_raw.to_crs(self.local_crs)

            if self.gdf_buildings_raw is not None and not self.gdf_buildings_raw.empty:
                self.gdf_buildings_raw = self.gdf_buildings_raw.to_crs(self.local_crs)

            if self.area_of_interest is not None:
                 self.area_of_interest = self.area_of_interest.to_crs(self.local_crs)
                 # Clip the data to the precise polygon
                 self.gdf_roads_raw = gpd.clip(self.gdf_roads_raw, self.area_of_interest)
                 if self.gdf_buildings_raw is not None and not self.gdf_buildings_raw.empty:
                     self.gdf_buildings_raw = gpd.clip(self.gdf_buildings_raw, self.area_of_interest)


        print(f"Data fetched and reprojected to {self.local_crs}.")
        if self.gdf_roads_raw is not None:
            print(f"Found {len(self.gdf_roads_raw)} road segments.")
        if self.gdf_buildings_raw is not None:
            print(f"Found {len(self.gdf_buildings_raw)} buildings.")

    def step_2_clean_data(self, **kwargs):
        """Cleans the fetched OSM data."""
        if self.gdf_roads_raw is None:
            raise ValueError("Raw road data not found. Run step_1_fetch_data first.")

        print("Step 2: Cleaning data...")
        config = self._get_config(**kwargs)

        # 1. Assign widths and filter roads
        default_widths = config.get('default_widths', {})
        fallback_width = config.get('fallback_default_width', 5.0)

        def assign_width(row):
            highway_tag = row.get('highway')
            return default_widths.get(str(highway_tag), fallback_width)

        self.gdf_roads_raw['width'] = self.gdf_roads_raw.apply(assign_width, axis=1)

        self.gdf_existing_sidewalks = self.gdf_roads_raw[self.gdf_roads_raw.get('footway') == 'sidewalk'].copy()
        self.gdf_existing_crossings = self.gdf_roads_raw[self.gdf_roads_raw.get('footway') == 'crossing'].copy()

        temp_roads = self.gdf_roads_raw[~self.gdf_roads_raw['highway'].isin(['footway', 'pedestrian', 'path', 'steps'])].copy()
        roads_for_processing = temp_roads[temp_roads['width'] > 0.5].copy()

        # 2. Find intersection points to prepare for splitting
        sindex = roads_for_processing.sindex
        intersections_set = set()
        for idx, road in roads_for_processing.iterrows():
            geom = road.geometry
            possible_matches_idx = list(sindex.intersection(geom.bounds))
            possible_matches = roads_for_processing.iloc[possible_matches_idx]
            actual_matches = possible_matches[possible_matches.index != idx]

            for _, match in actual_matches.iterrows():
                if geom.intersects(match.geometry):
                    intersection = geom.intersection(match.geometry)
                    if 'Point' in intersection.geom_type:
                        if intersection.geom_type == 'MultiPoint':
                            for p in intersection.geoms:
                                intersections_set.add(p.wkt)
                        else:
                            intersections_set.add(intersection.wkt)

        if intersections_set:
            self.gdf_intersections = gpd.GeoDataFrame(geometry=[wkt.loads(p) for p in intersections_set], crs=self.local_crs)
            print(f"Found {len(self.gdf_intersections)} intersection points.")
        else:
            self.gdf_intersections = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            print("No intersection points found.")

        # 3. Split lines at all found intersections
        if not self.gdf_intersections.empty:
            all_intersections = self.gdf_intersections.unary_union
            split_lines_data = []

            for _, road in roads_for_processing.iterrows():
                try:
                    split_geoms = list(split(road.geometry, all_intersections))
                    for geom in split_geoms:
                        new_road_attrs = road.to_dict()
                        new_road_attrs['geometry'] = geom
                        split_lines_data.append(new_road_attrs)
                except (TypeError, ValueError):
                    split_lines_data.append(road.to_dict())

            gdf_roads_split = gpd.GeoDataFrame(split_lines_data, crs=self.local_crs).reset_index(drop=True)
        else:
            gdf_roads_split = roads_for_processing.copy()

        print(f"Road network split into {len(gdf_roads_split)} segments.")

        # 4. Iteratively remove dead-end streets
        dead_end_iterations = config.get('dead_end_iterations', 0)
        temp_split_gdf = gdf_roads_split.copy()

        for i in range(dead_end_iterations):
            print(f"Dead-end removal iteration {i+1}...")

            endpoints = []
            for geom in temp_split_gdf.geometry:
                if geom.geom_type == 'LineString' and not geom.is_empty:
                    endpoints.append(geom.coords[0])
                    endpoints.append(geom.coords[-1])

            endpoint_counts = Counter(endpoints)
            dead_end_nodes = {point for point, count in endpoint_counts.items() if count == 1}

            if not dead_end_nodes:
                print("No more dead-ends found.")
                break

            to_remove = temp_split_gdf.geometry.apply(
                lambda geom: not geom.is_empty and (geom.coords[0] in dead_end_nodes or geom.coords[-1] in dead_end_nodes)
            )

            if not to_remove.any():
                print("No segments to remove in this iteration.")
                break

            temp_split_gdf = temp_split_gdf[~to_remove]
            print(f"Removed {to_remove.sum()} dead-end segments.")

        self.gdf_roads_cleaned = temp_split_gdf.copy()
        print(f"Final cleaned road network has {len(self.gdf_roads_cleaned)} segments.")
        print("Data cleaning complete.")

    def step_3_create_protoblocks(self, **kwargs):
        """Creates protoblocks from the cleaned road network."""
        if self.gdf_roads_cleaned is None or self.gdf_roads_cleaned.empty:
            raise ValueError("Cleaned road data not found. Run step_2_clean_data first.")

        print("Step 3: Creating protoblocks...")
        config = self._get_config(**kwargs)

        # 1. Polygonize the road network to create protoblocks
        road_lines = self.gdf_roads_cleaned.geometry.unary_union
        polygons = list(polygonize(road_lines))

        if not polygons:
            print("Polygonization did not result in any protoblocks.")
            self.gdf_protoblocks = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            return

        protoblocks_gdf = gpd.GeoDataFrame(geometry=polygons, crs=self.local_crs)
        # Add a unique ID to each protoblock for joining later
        protoblocks_gdf['protoblock_id'] = range(len(protoblocks_gdf))
        print(f"Created {len(protoblocks_gdf)} initial protoblocks.")

        # 2. Filter out protoblocks that already have a significant sidewalk network
        if self.gdf_existing_sidewalks is not None and not self.gdf_existing_sidewalks.empty:
            cutoff_percent = config.get('cutoff_percent_protoblock', 10.0)

            protoblocks_gdf['protoblock_area'] = protoblocks_gdf.geometry.area

            # Intersect existing sidewalks with protoblocks to find sidewalk segments inside each protoblock
            if protoblocks_gdf.crs != self.gdf_existing_sidewalks.crs:
                 self.gdf_existing_sidewalks = self.gdf_existing_sidewalks.to_crs(protoblocks_gdf.crs)

            overlay = gpd.overlay(protoblocks_gdf, self.gdf_existing_sidewalks, how='intersection', keep_geom_type=False)

            if not overlay.empty:
                overlay['sidewalk_len'] = overlay.geometry.length

                # Sum the length of all sidewalk segments within each original protoblock
                sidewalk_len_by_protoblock = overlay.groupby('protoblock_id')['sidewalk_len'].sum()

                # Join the total length back to the protoblocks
                protoblocks_gdf = protoblocks_gdf.join(sidewalk_len_by_protoblock, on='protoblock_id')
                protoblocks_gdf['sidewalk_len'] = protoblocks_gdf['sidewalk_len'].fillna(0)

                # Calculate the ratio using the formula from the original plugin: ((length/4)^2 / area) * 100
                protoblocks_gdf['sidewalk_area_ratio'] = ((protoblocks_gdf['sidewalk_len'] / 4) ** 2 / protoblocks_gdf['protoblock_area']) * 100

                # Filter out protoblocks where the ratio is too high
                protoblocks_to_keep = protoblocks_gdf[protoblocks_gdf['sidewalk_area_ratio'] <= cutoff_percent]

                print(f"Removed {len(protoblocks_gdf) - len(protoblocks_to_keep)} protoblocks with existing sidewalks.")
                self.gdf_protoblocks = protoblocks_to_keep[['geometry', 'protoblock_id']].copy()
            else:
                self.gdf_protoblocks = protoblocks_gdf[['geometry', 'protoblock_id']].copy()
        else:
            self.gdf_protoblocks = protoblocks_gdf[['geometry', 'protoblock_id']].copy()

        print(f"Final protoblock count: {len(self.gdf_protoblocks)}")

    def step_4_draw_sidewalks(self, **kwargs):
        """Generates sidewalk geometries."""
        if self.gdf_roads_cleaned is None or self.gdf_roads_cleaned.empty:
            raise ValueError("Cleaned road data not found. Run step_2_clean_data first.")

        print("Step 4: Drawing sidewalks...")
        config = self._get_config(**kwargs)

        roads_for_sidewalks = self.gdf_roads_cleaned.copy()

        # 1. Optional: Adjust road widths to avoid building overlap
        if config.get('use_buildings', True) and self.gdf_buildings_raw is not None and not self.gdf_buildings_raw.empty:
            print("Adjusting sidewalk widths for building overlap...")

            buildings_union = self.gdf_buildings_raw.unary_union

            adjusted_widths = []
            min_dist_to_building = config.get('min_dist_to_building', 0.5)
            sidewalk_buffer_dist = config.get('sidewalk_buffer_dist', 1.0)
            min_sidewalk_width = config.get('min_sidewalk_width', 0.4)

            for _, road in roads_for_sidewalks.iterrows():
                dist_to_buildings = road.geometry.distance(buildings_union)

                projected_sidewalk_dist = (road['width'] / 2) + (sidewalk_buffer_dist / 2)

                if (projected_sidewalk_dist + min_dist_to_building) > dist_to_buildings:
                    new_width = 2 * (dist_to_buildings - min_dist_to_building - (sidewalk_buffer_dist / 2))
                    adjusted_widths.append(max(new_width, min_sidewalk_width))
                else:
                    adjusted_widths.append(road['width'])

            roads_for_sidewalks['width'] = adjusted_widths

        # 2. Generate sidewalk buffers
        print("Generating road buffers...")
        sidewalk_buffer_dist = config.get('sidewalk_buffer_dist', 1.0)
        buffer_distances = (roads_for_sidewalks['width'] / 2) + (sidewalk_buffer_dist / 2)

        road_buffers = roads_for_sidewalks.geometry.buffer(buffer_distances, cap_style=2, join_style=2)

        dissolved_buffer = unary_union(list(road_buffers))
        curve_radius = config.get('curve_radius', 10.0)
        if curve_radius > 0:
            rounded_buffer = dissolved_buffer.buffer(curve_radius, join_style=1).buffer(-curve_radius, join_style=1)
        else:
            rounded_buffer = dissolved_buffer

        # 3. Extract sidewalks using the difference method
        print("Extracting sidewalk polygons...")

        if rounded_buffer.is_empty:
            print("Road buffer is empty, no sidewalks to generate from it.")
            sidewalks_gdf = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
        else:
            bounds = rounded_buffer.bounds
            big_buffer_dist = 100
            p1 = (bounds[0]-big_buffer_dist, bounds[1]-big_buffer_dist)
            p2 = (bounds[2]+big_buffer_dist, bounds[1]-big_buffer_dist)
            p3 = (bounds[2]+big_buffer_dist, bounds[3]+big_buffer_dist)
            p4 = (bounds[0]-big_buffer_dist, bounds[3]+big_buffer_dist)
            bbox_poly = Polygon([p1, p2, p3, p4, p1])

            diff_polys = bbox_poly.difference(rounded_buffer)

            if isinstance(diff_polys, MultiPolygon):
                polys = list(diff_polys.geoms)
                areas = [p.area for p in polys]
                # Remove the polygon with the largest area, which is the outer ring
                sidewalk_polys = [p for i, p in enumerate(polys) if i != areas.index(max(areas))]
                sidewalks_gdf = gpd.GeoDataFrame(geometry=sidewalk_polys, crs=self.local_crs)
            elif isinstance(diff_polys, Polygon):
                sidewalks_gdf = gpd.GeoDataFrame(geometry=[diff_polys], crs=self.local_crs)
            else:
                sidewalks_gdf = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)

        # 4. Handle exclusion zones from `sidewalk` tags
        print("Handling exclusion zones...")
        if 'sidewalk' in roads_for_sidewalks.columns:
            # Filter for roads explicitly tagged with sidewalk=no
            exclusion_roads = roads_for_sidewalks[roads_for_sidewalks['sidewalk'] == 'no'].copy()
            if not exclusion_roads.empty:
                print(f"Found {len(exclusion_roads)} segments tagged for sidewalk exclusion.")
                exclusion_buffer_distances = (exclusion_roads['width'] / 2) + (sidewalk_buffer_dist / 2) + 1
                exclusion_polys = exclusion_roads.geometry.buffer(exclusion_buffer_distances, cap_style=2)
                exclusion_zone = unary_union(list(exclusion_polys))

                sidewalks_gdf.geometry = sidewalks_gdf.geometry.difference(exclusion_zone)
                sidewalks_gdf = sidewalks_gdf[~sidewalks_gdf.is_empty]
        else:
            print("No 'sidewalk' tag column found, skipping exclusion zones.")

        # 5. Convert sidewalk polygons to lines
        print("Converting polygons to lines...")
        sidewalks_gdf.geometry = sidewalks_gdf.geometry.boundary

        self.gdf_sidewalks = sidewalks_gdf[~sidewalks_gdf.is_empty].copy()

        print(f"Generated {len(self.gdf_sidewalks)} sidewalk lines.")

    def step_5_draw_crossings(self, **kwargs):
        """Generates pedestrian crossings at intersections."""
        if self.gdf_roads_cleaned is None or self.gdf_sidewalks is None:
            raise ValueError("Cleaned roads and sidewalks must be generated first.")

        print("Step 5: Drawing crossings...")
        config = self._get_config(**kwargs)

        roads = self.gdf_roads_cleaned
        sidewalks_union = self.gdf_sidewalks.unary_union

        endpoints = []
        for geom in roads.geometry:
            if geom.geom_type == 'LineString' and not geom.is_empty:
                endpoints.extend([geom.coords[0], geom.coords[-1]])

        endpoint_counts = Counter(endpoints)
        valid_intersections = {pt for pt, count in endpoint_counts.items() if count >= 3}

        if not valid_intersections:
            print("No valid intersections (degree >= 3) found.")
            self.gdf_crossings = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            self.gdf_kerbs = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            return

        crossings_list = []

        for _, road in roads.iterrows():
            line = road.geometry
            if line.is_empty: continue

            start_pt_coords, end_pt_coords = line.coords[0], line.coords[-1]

            for pt_coords in [start_pt_coords, end_pt_coords]:
                if pt_coords not in valid_intersections:
                    continue

                inward_dist = config.get('crossing_inward_distance', 1.0)

                if pt_coords == start_pt_coords:
                    p1 = Point(line.coords[0])
                    p2 = Point(line.coords[1])
                else:
                    p1 = Point(line.coords[-1])
                    p2 = Point(line.coords[-2])

                road_vector = np.array([p1.x - p2.x, p1.y - p2.y])
                road_vector_norm = road_vector / np.linalg.norm(road_vector)

                inner_pt = Point(p1.x - road_vector_norm[0] * inward_dist,
                                 p1.y - road_vector_norm[1] * inward_dist)

                perp_vector = np.array([-road_vector_norm[1], road_vector_norm[0]])

                line_end1 = Point(inner_pt.x + perp_vector[0] * 50, inner_pt.y + perp_vector[1] * 50)
                line_end2 = Point(inner_pt.x - perp_vector[0] * 50, inner_pt.y - perp_vector[1] * 50)
                test_line = LineString([line_end1, line_end2])

                intersections = test_line.intersection(sidewalks_union)

                if intersections.is_empty or 'Point' not in intersections.geom_type:
                    continue

                if intersections.geom_type == 'MultiPoint' and len(intersections.geoms) >= 2:
                    points = list(intersections.geoms)
                    points.sort(key=lambda p: p.distance(inner_pt))

                    # Find the two points that are on opposite sides of the inner point
                    vec_inner_p0 = [points[0].x - inner_pt.x, points[0].y - inner_pt.y]

                    p1 = points[0]
                    p2 = None
                    for i in range(1, len(points)):
                        vec_inner_pi = [points[i].x - inner_pt.x, points[i].y - inner_pt.y]
                        # Check if vectors are pointing in opposite directions (dot product is negative)
                        if np.dot(vec_inner_p0, vec_inner_pi) < 0:
                            p2 = points[i]
                            break

                    if p1 and p2:
                        crossing_geom = LineString([p1, p2])
                        crossings_list.append({'geometry': crossing_geom, 'road_width': road['width']})

        if not crossings_list:
            print("Could not generate any crossing geometries.")
            self.gdf_crossings = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            self.gdf_kerbs = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)
            return

        crossings_gdf = gpd.GeoDataFrame(crossings_list, crs=self.local_crs)

        # Quality Control
        tolerance = 1 + (config.get('crossing_length_tolerance', 20.0) / 100)
        sidewalk_buffer_dist = config.get('sidewalk_buffer_dist', 1.0)
        crossings_gdf['expected_len'] = crossings_gdf['road_width'] + sidewalk_buffer_dist
        crossings_gdf['actual_len'] = crossings_gdf.geometry.length
        crossings_gdf = crossings_gdf[crossings_gdf['actual_len'] <= crossings_gdf['expected_len'] * tolerance]

        # Generate Kerbs
        kerbs_list = []
        kerb_percent = config.get('kerb_placement_percentage', 0.1)
        for _, crossing in crossings_gdf.iterrows():
            line = crossing.geometry
            if line.length > 0:
                kerb1 = line.interpolate(line.length * kerb_percent)
                kerb2 = line.interpolate(line.length * (1 - kerb_percent))
                kerbs_list.append({'geometry': kerb1})
                kerbs_list.append({'geometry': kerb2})

        self.gdf_crossings = crossings_gdf[['geometry']].copy()
        if kerbs_list:
            self.gdf_kerbs = gpd.GeoDataFrame(kerbs_list, crs=self.local_crs)
        else:
            self.gdf_kerbs = gpd.GeoDataFrame(geometry=[], crs=self.local_crs)

        print(f"Generated {len(self.gdf_crossings)} crossings and {len(self.gdf_kerbs)} kerbs.")

    def step_6_split_sidewalks(self, **kwargs):
        """Splits the generated sidewalk lines into smaller segments."""
        if self.gdf_sidewalks is None or self.gdf_sidewalks.empty:
            print("No sidewalks to split.")
            return

        print("Step 6: Splitting sidewalks...")
        config = self._get_config(**kwargs)

        sidewalks_to_split = self.gdf_sidewalks.copy()

        # 1. Split at protoblock corners
        if self.gdf_protoblocks is not None and not self.gdf_protoblocks.empty:
            print("Splitting sidewalks at protoblock corners...")
            all_corners = []
            for poly in self.gdf_protoblocks.geometry:
                all_corners.extend(poly.exterior.coords)

            unique_corner_points = {Point(c) for c in all_corners}
            splitter_points = unary_union(list(unique_corner_points))

            split_geoms = []
            for line in sidewalks_to_split.geometry:
                snapped_splitter = snap(splitter_points, line, 0.0001)
                actual_splitter = line.intersection(snapped_splitter)

                if not actual_splitter.is_empty and 'Point' in actual_splitter.geom_type:
                    split_geoms.extend(list(split(line, actual_splitter)))
                else:
                    split_geoms.append(line)

            sidewalks_to_split = gpd.GeoDataFrame(geometry=split_geoms, crs=self.local_crs)

        # 2. Split by maximum length
        if config.get('split_by_max_len', True):
            max_len = config.get('max_split_length', 50)
            print(f"Splitting sidewalks by maximum length of {max_len}...")

            final_split_geoms = []
            for line in sidewalks_to_split.geometry:
                if line.length > max_len:
                    num_segments = math.ceil(line.length / max_len)
                    for i in range(num_segments):
                        start = line.interpolate(i * (line.length / num_segments))
                        end = line.interpolate((i + 1) * (line.length / num_segments))
                        final_split_geoms.append(LineString([start, end]))
                else:
                    final_split_geoms.append(line)

            self.gdf_sidewalks = gpd.GeoDataFrame(geometry=final_split_geoms, crs=self.local_crs)
        else:
            self.gdf_sidewalks = sidewalks_to_split

        # 3. Final topological cleaning: Snap sidewalks to crossing endpoints
        if self.gdf_crossings is not None and not self.gdf_crossings.empty:
            print("Snapping sidewalks and crossings for topology...")
            crossing_endpoints = []
            for line in self.gdf_crossings.geometry:
                if not line.is_empty:
                    crossing_endpoints.extend([Point(line.coords[0]), Point(line.coords[-1])])

            if crossing_endpoints:
                crossing_endpoints_union = unary_union(crossing_endpoints)

                snapped_sidewalk_geoms = []
                for line in self.gdf_sidewalks.geometry:
                    snapped_line = snap(line, crossing_endpoints_union, 0.1)
                    snapped_sidewalk_geoms.append(snapped_line)

                self.gdf_sidewalks = gpd.GeoDataFrame(geometry=snapped_sidewalk_geoms, crs=self.local_crs)

        print(f"Final sidewalk count after splitting: {len(self.gdf_sidewalks)}")

    def run_all(self, area, **kwargs):
        """Runs the entire workflow from start to finish."""
        self.step_1_fetch_data(area)
        self.step_2_clean_data(**kwargs)
        self.step_3_create_protoblocks(**kwargs)
        self.step_4_draw_sidewalks(**kwargs)
        self.step_5_draw_crossings(**kwargs)
        self.step_6_split_sidewalks(**kwargs)

        print("Combining results into a single GeoDataFrame...")

        gdfs_to_concat = []
        if self.gdf_sidewalks is not None and not self.gdf_sidewalks.empty:
            gdf = self.gdf_sidewalks.copy()
            gdf['type'] = 'sidewalk'
            gdfs_to_concat.append(gdf)
        if self.gdf_crossings is not None and not self.gdf_crossings.empty:
            gdf = self.gdf_crossings.copy()
            gdf['type'] = 'crossing'
            gdfs_to_concat.append(gdf)
        if self.gdf_kerbs is not None and not self.gdf_kerbs.empty:
            gdf = self.gdf_kerbs.copy()
            gdf['type'] = 'kerb'
            gdfs_to_concat.append(gdf)

        if not gdfs_to_concat:
            print("Workflow did not generate any features.")
            self.final_gdf = gpd.GeoDataFrame(geometry=[], crs=self.local_crs if self.local_crs else "EPSG:4326")
        else:
            self.final_gdf = gpd.pd.concat(gdfs_to_concat, ignore_index=True)

        def add_osm_tags(row):
            if row['type'] == 'sidewalk':
                row['highway'] = 'footway'
                row['footway'] = 'sidewalk'
            elif row['type'] == 'crossing':
                row['highway'] = 'footway'
                row['footway'] = 'crossing'
            elif row['type'] == 'kerb':
                row['barrier'] = 'kerb'
            return row

        if not self.final_gdf.empty:
            for col in ['highway', 'footway', 'barrier']:
                if col not in self.final_gdf.columns:
                    self.final_gdf[col] = None
            self.final_gdf = self.final_gdf.apply(add_osm_tags, axis=1)

        if self.final_gdf.crs is not None:
            self.final_gdf = self.final_gdf.to_crs("EPSG:4326")

        print("Workflow complete. Returning final GeoDataFrame in WGS84 (EPSG:4326).")
        return self.final_gdf

    def draw_protoblocks(self, area, **kwargs):
        """Runs the workflow to generate and return just the protoblocks."""
        self.step_1_fetch_data(area)
        self.step_2_clean_data(**kwargs)
        self.step_3_create_protoblocks(**kwargs)

        print("Protoblock generation complete.")
        if self.gdf_protoblocks is not None and not self.gdf_protoblocks.empty:
            return self.gdf_protoblocks.to_crs("EPSG:4326")
        else:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
