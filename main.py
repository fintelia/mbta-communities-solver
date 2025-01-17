#!/bin/python3
import pandas
import geopandas
import matplotlib.pyplot as plt
import math
from os.path import exists

lot_area_per_dus ={
    #'A-1': 6000,
    #'A-2': 4500,
    #'B': 2500,
    'C': 1800,
    'C-1': 1500,
    'C-1A': 1000,
    'C-2': 600,
    'C-2A': 300,
    'C-2B': 300,
    'C-3': 300,
    'C-3A': 300,
    'C-3B': 300,

    # 'BA': 600,
    # 'BA-1': 1200,
    # 'BA-2': 600,
    # 'BA-3': 1500,
    # 'BA-4': 600,
    'BB': 300,
    # 'BB-1': 300,
    # 'BB-2': 300,
    # 'BC': 500,
    # 'BC-1': 450,

    # 'O-1': 1200,
    # 'O-2': 600,
    # 'O-2A': 600,
    # 'O-3': 300,
    # 'O-3A': 300,

    # 'IA-1': 700,
    # # 'IA-2': 1,
}
floor_area_ratios = {
    # 'A-1': 0.5,
    # 'A-2': 0.5,
    # 'B': 0.5,
    'C': 0.6,
    'C-1': 0.75,
    'C-1A': 1.25,
    'C-2': 1.75,
    'C-2A': 2.5,
    'C-2B': 1.75,
    'C-3': 3,
    'C-3A': 3,
    'C-3B': 4,

    'BA': 1.75,
    'BA-1': 0.75,
    'BA-2': 1.75,
    'BA-3': 0.75,
    'BA-4': 1.75,
    'BB': 3,
    'BB-1': 3.25,
    'BB-2': 3,
    'BC': 2,
    'BC-1': 3,

    'O-1': 0.75,
    'O-2': 2,
    'O-2A': 1.5,
    'O-3': 3,
    'O-3A': 3,

    'IA-1': 1.5,
    # 'IA-2': 4,
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
zones = zones[zones.area > 5 * 43560]

assessing_parcels = geopandas.read_file("ASSESSING_ParcelsFY2023.shp.zip").to_crs("EPSG:2249")
assessing_parcels.set_index("LOC_ID", inplace=True, verify_integrity=True)
parcels = parcels.join(assessing_parcels, on="LOC_ID", how="left", rsuffix="_assessing")

properties = pandas.read_csv("Filtered_Cambridge_Property_Database_FY2023.csv.zip")
properties.fillna(0, inplace=True)
properties['existing_units'] = properties.apply(lambda row: 1 if row['PropertyClass'] in ['CONDOMINIUM', 'CNDO LUX'] else row['Interior_NumUnits'], axis=1)
properties = properties[['GISID', 'existing_units']].groupby('GISID').sum()
parcels = parcels.join(properties, on="ML", how="left", rsuffix="_properties")

print(zones['ZONE_TYPE'].unique())

def units_in_zone(zone):
    zone_type = zone['ZONE_TYPE']
    district_parcels = parcels[parcels.geometry.within(zone.geometry)]
    existing_units = district_parcels['existing_units'].sum()
    if zone_type not in lot_area_per_dus:
        return [0, 0, district_parcels['existing_units'].sum()]

    # District parameters
    lot_area_per_du = lot_area_per_dus[zone_type]
    floor_area_ratio = floor_area_ratios[zone_type]
    unit_cap = 11
    if zone_type in ["BA", "BA-4", "BB", "BB-1", "BB-2", "BC", "IA-1", "C-2", "C-2A", "C-2B", "C-3", "C-3A", "C-3B"]:
        unit_cap = 100000

    # Calculate units
    total_units = 0
    station_units = 0
    for _, parcel in district_parcels.iterrows():
        sqft = parcel['SQFT'] - parcel['Tot_Exclud']
        units = min(math.floor(sqft / lot_area_per_du), round(sqft * floor_area_ratio / 1000), unit_cap)
        if units < 3:
            continue
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
zones['density_denominator'] = zones['geometry'].difference(density_deduct['geometry'].unary_union).area / 43560
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
    station_area_acres = district['geometry'].unary_union.intersection(station_area.geometry.unary_union).area / 43560
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

district_parts = geopandas.GeoSeries(district['geometry'].unary_union).explode(index_parts=False)
contiguous_fraction = district_parts.area.max() / district_parts.area.sum()
if contiguous_fraction >= 0.5:
    print("[PASS] Contiguous fraction: %.2f%%" % (contiguous_fraction * 100))
else:
    print("[FAIL] Contiguous fraction: %.2f%%" % (contiguous_fraction * 100))

# Plot the district
origin = zones.unary_union.centroid
ax = boundary.rotate(15, origin=origin).plot(figsize=(16,12), color='white', edgecolor='black', linewidth=2)
district.where(district['ZONE_TYPE'] != 'BB').rotate(15, origin=origin).plot(ax=ax, color='lightblue', edgecolor='black')
district.where(district['ZONE_TYPE'] == 'BB').rotate(15, origin=origin).plot(ax=ax, color='lightblue', edgecolor='black')
station_area.rotate(15, origin=origin).plot(ax=ax, color='grey', alpha=0.5)

ax.axis('off')
ax.margins(0)
plt.savefig("district.png", bbox_inches='tight')
