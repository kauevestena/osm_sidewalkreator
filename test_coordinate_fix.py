#!/usr/bin/env python3
"""
Test script to verify coordinate transformation issue with improved logic
"""

from qgis.core import (
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)


def test_coordinate_parsing():
    """Test coordinate parsing and transformation"""

    # Your original coordinates
    input_coords = (
        "-5488872.471400000,-5488263.192300000,-2936393.153600000,-2935998.943900000"
    )
    print(f"Input coordinates: {input_coords}")

    # Parse coordinates
    nums = [float(x.strip()) for x in input_coords.split(",")]
    print(f"Parsed numbers: {nums}")

    # Test both interpretations
    print("\n=== Testing both interpretations ===")
    rect1 = QgsRectangle(nums[0], nums[1], nums[2], nums[3])  # minX,minY,maxX,maxY
    rect2 = QgsRectangle(
        nums[0], nums[2], nums[1], nums[3]
    )  # minX,maxX,minY,maxY reordered

    area1 = rect1.width() * rect1.height()
    area2 = rect2.width() * rect2.height()

    print(
        f"Interpretation 1 (minX,minY,maxX,maxY): {rect1.width():.1f}m × {rect1.height():.1f}m (area: {area1:.0f})"
    )
    print(
        f"Interpretation 2 (minX,maxX,minY,maxY): {rect2.width():.1f}m × {rect2.height():.1f}m (area: {area2:.0f})"
    )

    # Choose the interpretation that results in a smaller, more reasonable area
    # For neighborhood processing, we expect areas less than 100 km²
    if area2 < area1 and area2 < 100_000_000:  # 100 km² = 100,000,000 m²
        print("✓ Using interpretation 2 (reordered coordinates) - smaller area")
        chosen_rect = rect2
    elif area1 < 100_000_000:
        print("✓ Using interpretation 1 (original order) - reasonable area")
        chosen_rect = rect1
    else:
        print("✓ Both interpretations result in very large areas, using smaller one")
        chosen_rect = rect2 if area2 < area1 else rect1

    print(f"Chosen rectangle: {chosen_rect.toString()}")

    # Transform to EPSG:4326
    crs_3857 = QgsCoordinateReferenceSystem("EPSG:3857")
    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")

    # Create a dummy project context for transformation
    transform = QgsCoordinateTransform(crs_3857, crs_4326, QgsProject.instance())

    print("\n=== Final transformation result ===")

    try:
        extent_4326 = transform.transform(chosen_rect)
        print(f"Transformed to 4326: {extent_4326.toString()}")
        print(
            f"  Longitude range: {extent_4326.xMinimum():.6f} to {extent_4326.xMaximum():.6f}"
        )
        print(
            f"  Latitude range: {extent_4326.yMinimum():.6f} to {extent_4326.yMaximum():.6f}"
        )

        # Check if coordinates are reasonable for a neighborhood in Brazil
        lon_center = (extent_4326.xMinimum() + extent_4326.xMaximum()) / 2
        lat_center = (extent_4326.yMinimum() + extent_4326.yMaximum()) / 2
        print(f"  Center: {lon_center:.6f}, {lat_center:.6f}")

        # Check if this looks like Brazil (approximate bounds: lon -75 to -30, lat -35 to 5)
        if -75 <= lon_center <= -30 and -35 <= lat_center <= 5:
            print("  ✓ Coordinates appear to be in Brazil")
        else:
            print("  ⚠ Coordinates don't appear to be in Brazil")

    except Exception as e:
        print(f"Transformation failed: {e}")


if __name__ == "__main__":
    test_coordinate_parsing()
