#!/bin/python3
import pandas
import geopandas
import matplotlib.pyplot as plt
import math
from os.path import exists

# lot_area_per_dus ={
#     #'A-1': 6000,
#     #'A-2': 4500,
#     #'B': 2500,
#     'C': 1800,
#     'C-1': 1500,
#     'C-1A': 1000,
#     'C-2': 600,
#     'C-2A': 300,
#     'C-2B': 300,
#     'C-3': 300,
#     'C-3A': 300,
#     'C-3B': 300,

#     # 'BA': 600,
#     # 'BA-1': 1200,
#     # 'BA-2': 600,
#     # 'BA-3': 1500,
#     # 'BA-4': 600,
#     'BB': 300,
#     # 'BB-1': 300,
#     # 'BB-2': 300,
#     # 'BC': 500,
#     # 'BC-1': 450,

#     # 'O-1': 1200,
#     # 'O-2': 600,
#     # 'O-2A': 600,
#     # 'O-3': 300,
#     # 'O-3A': 300,

#     # 'IA-1': 700,
#     # # 'IA-2': 1,
# }
open_space = {
    'A-1': 0.3,
    'A-2': 0.3,
    'B': 0.3,
    'C': 0.3,
    'C-1': 0.3,
    'C-1A': 0.15,
    'C-2': 0.15,
    'C-2A': 0.1,
    'C-2B': 0.15,
    'C-3': 0.1,
    'C-3A': 0.1,
    'C-3B': 0.1,

    'BA': 0,
    'BA-1': 0,
    'BA-2': 0,
    'BA-3': 0.3,
    'BA-4': 0,
    'BB': 0,
    'BB-1': .3,
    'BB-2': .3,
    'BC': 0,

    'O-1': 0.15,
    'O-2': 0.15,
    'O-2A': 0.15,
    'O-3': 0.1,
    'O-3A': 0.1,

    'IA-1': 0,
    'IA-2': 0,
}

stories = {
    'C-1A': 6,
    'C-2': 7,
    'C-2A': 6,
    'C-2B': 6,
    'C-3': 10,
    'C-3A': 10,
    'C-3B': 10,

    'BA': 6,
    'BA-1': 6,
    'BA-2': 6,
    'BA-3': 6,
    'BA-4': 6,
    'BB': 7,
    'BB-1': 8,
    'BB-2': 6,
    'BC': 6,

    'O-1': 6,
    'O-2': 7,
    'O-2A': 6,
    'O-3': 10,
    'O-3A': 10,

    'IA-1': 6,
    'IA-2': 6,
}

pandas.set_option("display.precision", 2)

# Load shapefiles and do some preliminary processing
boundary = geopandas.read_file("BOUNDARY_CityBoundary.shp.zip").to_crs("EPSG:2249")
station_area = geopandas.read_file('Transit_Station_Points.zip').to_crs("EPSG:2249")
station_area.geometry = station_area.buffer(2640)
station_area = station_area.overlay(boundary).dissolve()
if exists("Cambridge_Density_Denominator_Deductions.shp.zip"):
    density_deduct = geopandas.read_file("Cambridge_Density_Denominator_Deductions.shp.zip").to_crs("EPSG:2249")
else:
    density_deduct = geopandas.read_file('Density_Denominator_Deductions.zip').to_crs("EPSG:2249")
    density_deduct = density_deduct.clip(boundary.geometry.total_bounds)
    density_deduct.to_file("Cambridge_Density_Denominator_Deductions.shp.zip")
density_deduct = density_deduct.overlay(boundary).dissolve()
parcels = geopandas.read_file("49_CAMBRIDGE_basic.zip").to_crs("EPSG:2249")
parcels.geometry = parcels.buffer(-1)
zones = geopandas.read_file("CDD_ZoningDistricts.shp.zip").to_crs("EPSG:2249")
#zones = zones[zones.area > 5 * 43560]

assessing_parcels = geopandas.read_file("ASSESSING_ParcelsFY2023.shp.zip").to_crs("EPSG:2249")
assessing_parcels.set_index("LOC_ID", inplace=True, verify_integrity=True)
parcels = parcels.join(assessing_parcels, on="LOC_ID", how="left", rsuffix="_assessing")

properties = pandas.read_csv("Filtered_Cambridge_Property_Database_FY2023.csv.zip")
properties.fillna(0, inplace=True)
properties['existing_units'] = properties.apply(lambda row: 1 if row['PropertyClass'] in ['CONDOMINIUM', 'CNDO LUX'] else row['Interior_NumUnits'], axis=1)
properties = properties[['GISID', 'existing_units']].groupby('GISID').sum()
parcels = parcels.join(properties, on="ML", how="left", rsuffix="_properties")

print("Small parcels: %d" % len(parcels[parcels['SQFT'] < 5000]))
print("Large parcels: %d" % len(parcels[parcels['SQFT'] >= 5000]))

def units_in_zone(zone):
    zone_type = zone['ZONE_TYPE']
    district_parcels = parcels[parcels.geometry.within(zone.geometry)]
    existing_units = district_parcels['existing_units'].sum()
    if zone_type == "OS":
        return [0, 0, district_parcels['existing_units'].sum()]


    # Calculate units
    total_units = 0
    station_units = 0
    for _, parcel in district_parcels.iterrows():
        sqft = parcel['SQFT'] - parcel['Tot_Exclud']

        height = 4
        if sqft >= 5000:
            height = 6
        height = stories.get(zone_type, height)

        max_coverage = 1 - max(open_space.get(zone_type, 0.3), .2)
        floor_area = min(sqft * max_coverage * height, 75000)

        if floor_area < 2500:
            continue

        units = max(math.floor(floor_area / 1000), 3)

        # if units <= parcel['existing_units']:
        #     continue
        # if parcel['existing_units'] > 20:
        #     continue
        # if units > 150 and zone_type in ['BA', 'BB', 'IA-1']:
        #     print(units, zone_type, units / (sqft/43560),  parcel['Address'])
        #     continue
        #units -= min(units, parcel['existing_units'])
        # if units < 20:
        #     units = min(units, 9)
        total_units += units
        if parcel['TRANSIT'] == 'N':
            station_units += units
    return [total_units, station_units, existing_units]

zones[['units', 'station_units', 'existing_units']] = zones.apply(units_in_zone, axis=1, result_type='expand')
zones['density_denominator'] = zones['geometry'].difference(density_deduct['geometry'].union_all()).area / 43560
zones['density'] = zones['units'] / zones['density_denominator']

print("Total possible units:", zones['units'].sum())

multifamily_zones = zones[zones['units'] > 0].sort_values(by="density", ascending=False)
multifamily_zones['cumulative_units'] = multifamily_zones['units'].cumsum()
multifamily_zones['cumulative_station_units'] = multifamily_zones['station_units'].cumsum()
multifamily_zones['cumulative_density_denominator'] = multifamily_zones['density_denominator'].cumsum()
multifamily_zones['cumulative_density'] = multifamily_zones['cumulative_units'] / multifamily_zones['cumulative_density_denominator']
district = multifamily_zones[multifamily_zones['cumulative_density'] > 15]

district = district.sort_values(by="station_units", ascending=False)
district['cumulative_units'] = district['units'].cumsum()
district['cumulative_station_units'] = district['station_units'].cumsum()
# idx = district.where(district['cumulative_station_units'] >= 12129).where(district['cumulative_units'] >= 13477).first_valid_index()
# if idx is not None:
#     district = district.loc[:idx]

# print(district.where(district['ZONE_TYPE'] == 'C-1A')['density'])

print("Subdistricts: %d" % len(district))
print("Zones: ", ", ".join(sorted(district['ZONE_TYPE'].unique())))

station_units = district['station_units'].sum()
if station_units >= 12129:
    print("[PASS] Station units: %d" % station_units)
else:
    print("[FAIL] Station units: %d" % station_units)

total_units = district['units'].sum()
if total_units >= 13477:
    print("[PASS] Total units: %d" % total_units)
else:
    print("[FAIL] Total units: %d" % total_units)

try:
    station_area_acres = district['geometry'].union_all().intersection(station_area.geometry.union_all()).area / 43560
except:
    station_area_acres = 0
if station_area_acres >= 32 * 0.9:
    print("[PASS] Station area: %d acres" % station_area_acres)
else:
    print("[FAIL] Station area: %d acres" % station_area_acres)

total_area = district['geometry'].area.sum() / 43560
if total_area >= 32:
    print("[PASS] Total area: %d acres" % total_area)
else:
    print("[FAIL] Total area: %d acres" % total_area)

total_density = total_units / district['density_denominator'].sum()
if total_density >= 15:
    print("[PASS] Density: %.2f units/acre" % total_density)
else:
    print("[FAIL] Density: %.2f units/acre" % total_density)

district_parts = geopandas.GeoSeries(district['geometry'].union_all()).explode(index_parts=False)
contiguous_fraction = district_parts.area.max() / district_parts.area.sum()
if contiguous_fraction >= 0.5:
    print("[PASS] Contiguous fraction: %.2f%%" % (contiguous_fraction * 100))
else:
    print("[FAIL] Contiguous fraction: %.2f%%" % (contiguous_fraction * 100))

# Plot the district
origin = zones.union_all().centroid
ax = boundary.rotate(15, origin=origin).plot(figsize=(16,12), color='white', edgecolor='black', linewidth=2)
zones.rotate(15, origin=origin).plot(ax=ax, color='lightgrey', edgecolor='black')
# district.where(district['ZONE_TYPE'] != 'BB').rotate(15, origin=origin).plot(ax=ax, color='lightblue', edgecolor='black')
# district.where(district['ZONE_TYPE'] == 'BB').rotate(15, origin=origin).plot(ax=ax, color='lightblue', edgecolor='black')
station_area.rotate(15, origin=origin).plot(ax=ax, color='grey', alpha=0.5)

ax.axis('off')
ax.margins(0)
plt.savefig("district.png", bbox_inches='tight')
