#!/usr/bin/env python3
"""
export_bhubaneswar_map.py
Generates a true A3-sized (420 x 297 mm), 300 DPI high-resolution map of the 
HydroShield OD Bhubaneswar basin (Nayapalli / NH-16 Channel No. 4).

Features:
- Standard A3 Landscape dimensions (16.54 x 11.69 inches @ 300 DPI)
- Extra-large, high-visibility points and label badges for DR-01 to DR-25
- Large, bold hospital lifeline corridors
- Free, un-watermarked OpenStreetMap tiles (no API key required)
"""

import io
import json
import math
import urllib.request
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ==============================================================================
# 1. COORDINATE BOUNDARIES & LOCATIONS (BHUBANESWAR BASIN)
# ==============================================================================
LAT_MIN, LAT_MAX = 20.2880, 20.3050
LON_MIN, LON_MAX = 85.8120, 85.8320

# Primary Ground-Truth NFC Tag Landmarks (DR-01 to DR-05)
PRIMARY_NFC_TAGS = [
    ("DR-01", "ISKCON Temple NH-16 Culvert", 20.2961, 85.8245),
    ("DR-02", "CRP Square Main Junction", 20.2915, 85.8168),
    ("DR-03", "Behera Sahi Low-Point Drain", 20.2982, 85.8260),
    ("DR-04", "Jayadev Vihar Hospital Connector", 20.2998, 85.8285),
    ("DR-05", "Channel No. 4 Outfall", 20.2930, 85.8305),
]

# 108 Emergency Hospital Gateways
HOSPITALS = [
    ("KIMS Corridor Gateway", 20.3043, 85.8147),
    ("Capital Hospital Gateway", 20.2894, 85.8311),
    ("AIIMS Corridor Gateway", 20.2892, 85.8132),
]

# Load Synthetic Nodes (DR-06 to DR-25) from drains.geojson if available, else fallback
synthetic_nodes = []
drains_file = Path("backend/data/drains.geojson")
if drains_file.exists():
    try:
        data = json.loads(drains_file.read_text(encoding="utf-8"))
        for f in data.get("features", []):
            p = f["properties"]
            if p.get("feature_type") == "drain_node" and not p.get("nfc_tagged", False):
                lon, lat = f["geometry"]["coordinates"]
                synthetic_nodes.append((p["drain_id"], lat, lon))
    except Exception:
        pass

if not synthetic_nodes:
    synthetic_nodes = [
        ("DR-06", 20.2906, 85.8267), ("DR-07", 20.3001, 85.8316),
        ("DR-08", 20.2984, 85.8131), ("DR-09", 20.3030, 85.8262),
        ("DR-10", 20.2909, 85.8138), ("DR-11", 20.2911, 85.8316),
        ("DR-12", 20.2958, 85.8277), ("DR-13", 20.2988, 85.8234),
        ("DR-14", 20.2931, 85.8236), ("DR-15", 20.2999, 85.8250),
        ("DR-16", 20.3040, 85.8150), ("DR-17", 20.2966, 85.8201),
        ("DR-18", 20.2961, 85.8144), ("DR-19", 20.2903, 85.8176),
        ("DR-20", 20.2932, 85.8206), ("DR-21", 20.2950, 85.8202),
        ("DR-22", 20.2917, 85.8238), ("DR-23", 20.2934, 85.8127),
        ("DR-24", 20.2934, 85.8277), ("DR-25", 20.2986, 85.8192),
    ]

# ==============================================================================
# 2. SLIPPY TILE CALCULATION & DOWNLOAD
# ==============================================================================
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    return math.degrees(lat_rad), lon_deg

def fetch_map_tile(x, y, z):
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "HydroShieldA3MapExporter/2.0 (contact@hydroshield.od)"}
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return Image.open(io.BytesIO(resp.read())).convert("RGB")

print("[1/3] Downloading OpenStreetMap basemap tiles for Bhubaneswar basin...")
ZOOM = 16
x0, y0 = deg2num(LAT_MAX + 0.001, LON_MIN - 0.001, ZOOM)
x1, y1 = deg2num(LAT_MIN - 0.001, LON_MAX + 0.001, ZOOM)

total_w = (x1 - x0 + 1) * 256
total_h = (y1 - y0 + 1) * 256
stitched_img = Image.new("RGB", (total_w, total_h))

for x in range(x0, x1 + 1):
    for y in range(y0, y1 + 1):
        tile = fetch_map_tile(x, y, ZOOM)
        stitched_img.paste(tile, ((x - x0) * 256, (y - y0) * 256))

nw_lat, nw_lon = num2deg(x0, y0, ZOOM)
se_lat, se_lon = num2deg(x1 + 1, y1 + 1, ZOOM)

# ==============================================================================
# 3. RENDER OVERLAYS ON EXACT A3 CANVAS (16.54 x 11.69 inches @ 300 DPI)
# ==============================================================================
print("[2/3] Rendering enlarged DR points, labels, and boundaries on A3 layout...")

# A3 Landscape size in inches: 420mm / 25.4 = 16.535 in, 297mm / 25.4 = 11.693 in
fig, ax = plt.subplots(figsize=(16.54, 11.69), dpi=300)

# Display stitched basemap
ax.imshow(stitched_img, extent=[nw_lon, se_lon, se_lat, nw_lat], aspect='auto')

# 1. Plot Synthetic Drainage Nodes (DR-06 to DR-25) — Super Enlarged
for did, lat, lon in synthetic_nodes:
    ax.scatter(
        lon, lat, color='#0284C7', s=420, zorder=4, 
        edgecolor='white', linewidth=2.4, alpha=0.98
    )
    ax.text(
        lon, lat + 0.00055, did, fontsize=11.0, fontweight='bold', color='#0369A1',
        ha='center', va='bottom', zorder=5,
        bbox=dict(boxstyle='round,pad=0.30', fc='#F0F9FF', ec='#0284C7', linewidth=1.6, alpha=0.95)
    )

# 2. Plot Primary NFC-Tagged Nodes (DR-01 to DR-05) — Maximum Prominence
for did, name, lat, lon in PRIMARY_NFC_TAGS:
    ax.scatter(
        lon, lat, color='#DC2626', s=1100, zorder=6, 
        edgecolor='#FEF08A', linewidth=4.0, marker='o'
    )
    ax.text(
        lon, lat - 0.00078, f"{did}: {name}", fontsize=13.5, fontweight='black', color='#991B1B',
        ha='center', va='top', zorder=7,
        bbox=dict(boxstyle='round,pad=0.42', fc='#FEF2F2', ec='#DC2626', linewidth=2.4, alpha=0.98)
    )

# 3. Plot 108 Emergency Hospital Gateways — Enlarged Corridors
for name, lat, lon in HOSPITALS:
    ax.scatter(
        lon, lat, color='#1E40AF', s=950, zorder=5, 
        edgecolor='white', linewidth=3.2, marker='P'
    )
    ax.text(
        lon, lat + 0.00072, f"108 Route: {name}", fontsize=12.0, fontweight='bold', color='#1E3A8A',
        ha='center', va='bottom', zorder=6,
        bbox=dict(boxstyle='square,pad=0.38', fc='#EFF6FF', ec='#1E40AF', linewidth=1.8, alpha=0.96)
    )

# 4. Draw Study Basin Bounding Box (Prominent Amber Dashed Border)
basin_rect = mpatches.Rectangle(
    (LON_MIN, LAT_MIN), LON_MAX - LON_MIN, LAT_MAX - LAT_MIN,
    fill=False, edgecolor='#D97706', linewidth=3.8, linestyle='--', zorder=3
)
ax.add_patch(basin_rect)

# 5. Framing, Axes, and Header Title
ax.set_xlim(LON_MIN - 0.0010, LON_MAX + 0.0010)
ax.set_ylim(LAT_MIN - 0.0010, LAT_MAX + 0.0010)
ax.set_xlabel("Longitude (°E)", fontsize=12, fontweight='bold', color='#0F172A')
ax.set_ylabel("Latitude (°N)", fontsize=12, fontweight='bold', color='#0F172A')
ax.set_title(
    "HydroShield OD — Bhubaneswar Urban Flood Monitoring Basin (Nayapalli / NH-16 Channel No. 4)",
    fontsize=16, fontweight='heavy', pad=18, color='#0F172A'
)

# 6. High-Visibility Legend
legend_elements = [
    mpatches.Patch(facecolor='#DC2626', edgecolor='#FEF08A', label='Primary NFC-Tagged Landmark Assets (DR-01 to DR-05)'),
    mpatches.Patch(facecolor='#0284C7', edgecolor='white', label='Synthetic Distributed Inlets (DR-06 to DR-25)'),
    mpatches.Patch(facecolor='#1E40AF', edgecolor='white', label='108 Emergency Hospital Gateways (AIIMS, KIMS, Capital)'),
    mpatches.Patch(facecolor='none', edgecolor='#D97706', linestyle='--', label='Study Area Boundary Box (~2.8 km²)')
]
ax.legend(
    handles=legend_elements, loc='upper left', framealpha=0.97, 
    facecolor='white', edgecolor='#64748B', fontsize=11.0, borderpad=0.8
)

# ==============================================================================
# 4. EXPORT TO A3 300 DPI PNG
# ==============================================================================
plt.tight_layout()
output_img = "HydroShield_Bhubaneswar_Basin_A3_300DPI.png"
print(f"[3/3] Saving true A3 (420 x 297 mm) 300 DPI map to: {output_img}")
plt.savefig(output_img, dpi=300)
plt.close()
print("Success: Generated print-ready A3 map with prominent DR points and badges!")