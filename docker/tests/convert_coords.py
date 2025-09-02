#!/usr/bin/env python3
from osgeo import osr, ogr

# Create coordinate transformation from WGS84 to Web Mercator
source = osr.SpatialReference()
source.ImportFromEPSG(4326)  # WGS84

target = osr.SpatialReference()  
target.ImportFromEPSG(3857)  # Web Mercator

transform = osr.CoordinateTransformation(source, target)

# Original coordinates from the log
coords_4326 = [
    (-49.31350999165461, -25.477925024097257),  # min_lon, min_lat
    (-49.2879868808341, -25.463016332803363)    # max_lon, max_lat
]

print("Converting coordinates from EPSG:4326 to EPSG:3857:")
coords_3857 = []
for lon, lat in coords_4326:
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(lon, lat)
    point.Transform(transform)
    x, y = point.GetX(), point.GetY()
    coords_3857.append((x, y))
    print(f"  ({lon}, {lat}) -> ({x}, {y})")

print(f"\nEPSG:3857 bounds: {coords_3857[0][0]}, {coords_3857[0][1]}, {coords_3857[1][0]}, {coords_3857[1][1]}")

# Create the GeoJSON
import json
polygon_3857 = {
    "type": "FeatureCollection",
    "crs": {
        "type": "name",
        "properties": {
            "name": "EPSG:3857"
        }
    },
    "features": [
        {
            "type": "Feature", 
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [coords_3857[0][0], coords_3857[0][1]],  # bottom-left
                    [coords_3857[1][0], coords_3857[0][1]],  # bottom-right
                    [coords_3857[1][0], coords_3857[1][1]],  # top-right
                    [coords_3857[0][0], coords_3857[1][1]],  # top-left
                    [coords_3857[0][0], coords_3857[0][1]]   # close polygon
                ]]
            }
        }
    ]
}

with open('/tmp/polygon_3857_proper.geojson', 'w') as f:
    json.dump(polygon_3857, f, indent=2)
    
print("Created proper EPSG:3857 polygon at /tmp/polygon_3857_proper.geojson")
