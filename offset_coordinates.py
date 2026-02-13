#!/usr/bin/env python3
"""
Offset coordinates to avoid mapping to real-world infrastructure
Adds random offset to move dataset outside Phoenix metro area
"""

import pandas as pd

# Offset coordinates by ~15 miles east and ~10 miles north
# This moves the dataset away from Phoenix proper
OFFSET_X = 0.20  # ~15 miles east (longitude)
OFFSET_Y = 0.15  # ~10 miles north (latitude)

print("="*70)
print("COORDINATE OFFSET UTILITY")
print("="*70)

print(f"\nApplying offset:")
print(f"  X (longitude): +{OFFSET_X:.2f} degrees (~15 miles east)")
print(f"  Y (latitude):  +{OFFSET_Y:.2f} degrees (~10 miles north)")

# Load coordinates
coords_csv = pd.read_csv('sisyphean-power-and-light/network/coordinates.csv')

print(f"\nOriginal coordinate range:")
print(f"  X: {coords_csv['x'].min():.4f} to {coords_csv['x'].max():.4f}")
print(f"  Y: {coords_csv['y'].min():.4f} to {coords_csv['y'].max():.4f}")
print(f"  (Phoenix metro area)")

# Apply offset
coords_csv['x'] = coords_csv['x'] + OFFSET_X
coords_csv['y'] = coords_csv['y'] + OFFSET_Y

print(f"\nNew coordinate range:")
print(f"  X: {coords_csv['x'].min():.4f} to {coords_csv['x'].max():.4f}")
print(f"  Y: {coords_csv['y'].min():.4f} to {coords_csv['y'].max():.4f}")
print(f"  (Offset from real infrastructure)")

# Save updated coordinates
coords_csv.to_csv('sisyphean-power-and-light/network/coordinates.csv', index=False)

# Update coordinates.dss file
print(f"\nUpdating coordinates.dss file...")

with open('sisyphean-power-and-light/network/coordinates.dss', 'r') as f:
    dss_lines = f.readlines()

updated_lines = []
for line in dss_lines:
    if line.strip().startswith('SetBusXY'):
        # Parse the SetBusXY command format: SetBusXY bus=name x=value y=value
        parts = line.split()
        if len(parts) >= 4:
            bus_part = parts[1]  # bus=bus_name
            x_part = parts[2]    # x=value
            y_part = parts[3]    # y=value

            bus_name = bus_part.split('=')[1]
            old_x = float(x_part.split('=')[1])
            old_y = float(y_part.split('=')[1])

            new_x = old_x + OFFSET_X
            new_y = old_y + OFFSET_Y

            updated_lines.append(f"SetBusXY bus={bus_name} x={new_x:.6f} y={new_y:.6f}\n")
        else:
            updated_lines.append(line)
    else:
        updated_lines.append(line)

with open('sisyphean-power-and-light/network/coordinates.dss', 'w') as f:
    f.writelines(updated_lines)

print(f"✅ Coordinates offset successfully")
print(f"\nNew location approximates fictional area outside Phoenix metro")
print(f"This prevents accidental mapping to real utility infrastructure.")

print("\n" + "="*70)
print("RECOMMENDED: Add disclaimer to README about synthetic coordinates")
print("="*70)
