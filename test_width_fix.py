#!/usr/bin/env python3

# Quick test of the width assignment logic
import sys

sys.path.append(
    "/home/kaue/.local/share/QGIS/QGIS3/profiles/default/python/plugins/osm_sidewalkreator"
)

from parameters import widths_fieldname

# Test the parameters we're using
print("Testing width assignment logic...")


# Simulate the fixes
def test_width_assignment():
    # Simulate original_width_val scenarios
    test_cases = [
        (None, "NULL value"),
        (0.0, "Zero value"),
        (6.0, "Valid value"),
        ("", "Empty string"),
    ]

    for original_width_val, description in test_cases:
        print(f"\nTesting {description}: {original_width_val}")

        # Apply the fixed logic
        if original_width_val is None or original_width_val == 0.0:
            # Use default width when no width is specified
            result = 6.0  # Default to 6m
        else:
            try:
                result = float(original_width_val)
            except:
                result = 6.0  # Default to 6m

        print(f"  Result: {result}")

        # Calculate buffer expression result
        d_to_add_value = 1.0  # Default
        buffer_distance = result / 2 + d_to_add_value / 2.0
        print(f"  Buffer distance: {buffer_distance} meters")


if __name__ == "__main__":
    print(f"widths_fieldname: '{widths_fieldname}'")
    test_width_assignment()

    print("\n" + "=" * 50)
    print("EXPECTED RESULTS:")
    print("- NULL/0.0 values should become 6.0m -> 3.5m buffer")
    print("- Valid values should remain unchanged")
    print("- Buffer expression: (width/2) + (d_to_add/2)")
    print("- For 6m width + 1m d_to_add: (6/2) + (1/2) = 3.5m buffer")
