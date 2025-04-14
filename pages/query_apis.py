import streamlit as st
import geopandas as gpd
import xml.etree.ElementTree as ET
import os
from io import BytesIO
import json
import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib import style
# from streamlit_folium import folium_static
# from streamlit_folium import st_folium
# import folium
import base64
import pandas as pd
import numpy as np
import time
from shapely.geometry import Point
import random
from shapely.geometry import MultiLineString, LineString, shape, Point
from shapely.ops import split
import shutil
import requests
import re
from datetime import datetime
from utils.api_utils import query_api
from utils.geospatial_utils import convert_arcgis_paths_to_geojson, check_far_splitted
print("Watching this file")


def query_apis_page():
    st.title("Query APIs")

    # Dropdown menu for API selection
    api_choice = st.selectbox(
        "Select API to Query:",
        ("Wake Forest - Greenways API", "Wake Forest - Multi Use Paths API",
            "Wake Forest - Parks and Facilities API")
    )

    # Input for Layer ID
    layer_id = st.text_input("Enter Layer ID:", value="0")

    # Determine the endpoint based on user selection
    if api_choice == "Wake Forest - Greenways API":
        endpoint = f"https://twfgis.wakeforestnc.gov/server/rest/services/Greenways_Wake_Forest/MapServer/{layer_id}/query"
        dissolve_column = "Name"
    elif api_choice == "Wake Forest - Multi Use Paths API":
        endpoint = f"https://twfgis.wakeforestnc.gov/server/rest/services/MultiUsePath/MapServer/{layer_id}/query"
        dissolve_column = "Street"
    elif api_choice == "Wake Forest - Parks and Facilities API":
        endpoint = f"https://twfgis.wakeforestnc.gov/server/rest/services/ParksAndFacilities/MapServer/{layer_id}/query"
        dissolve_column = None  # No need to dissolve for points

    # Parameters to send with the API request
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "json"
    }

    # Query the API when the button is clicked
    if st.button("Query API"):
        data = query_api(endpoint, params)
        if data:
            st.success("API queried successfully!")

            features = data['features']
            geometries = []
            attributes = []
            spatial_ref = None

            # Extract spatial reference information
            if 'spatialReference' in data:
                spatial_ref = data['spatialReference']['latestWkid']
            else:
                if 'features' in data and data['features']:
                    spatial_ref = data['features'][0]['geometry'].get(
                        'spatialReference', {}).get('latestWkid', None)

            for feature in features:
                geom = feature['geometry']

                # Check if the geometry is valid
                if geom is None:
                    continue

                try:
                    # Convert geometry based on the API
                    if api_choice == "Wake Forest - Greenways API" or api_choice == "Wake Forest - Multi Use Paths API":
                        if 'paths' in geom:
                            geom_geojson = convert_arcgis_paths_to_geojson(
                                geom)
                        else:
                            geom_geojson = shape(geom)
                        shapely_geom = shape(geom_geojson)
                    elif api_choice == "Wake Forest - Parks and Facilities API":
                        if 'x' in geom and 'y' in geom:
                            shapely_geom = Point(geom['x'], geom['y'])
                        else:
                            st.warning(
                                "Skipping a feature with unknown geometry format.")
                            continue

                    geometries.append(shapely_geom)
                    attributes.append(feature['attributes'])
                except Exception as e:
                    st.warning(
                        f"Skipping a feature due to geometry processing error: {e}")
                    continue

            # Log the number of geometries and attributes
            st.write(f"Number of geometries: {len(geometries)}")
            # st.write(f"Number of attributes: {len(attributes)}")

            # Create a DataFrame for attributes
            df = pd.DataFrame(attributes)

            if dissolve_column and dissolve_column in df.columns:
                # Ensure column exists before using it
                mask = df[dissolve_column].notna()
                df = df[mask]
                geometries = [geometry for i, geometry in enumerate(
                    geometries) if mask.iloc[i]]
            else:
                st.warning(
                    f"Column '{dissolve_column}' not found in the dataset. Skipping dissolve operation.")

                # Ensure the number of geometries and attributes still match
                if len(df) != len(geometries):
                    st.error(
                        "Mismatch between number of geometries and attributes after processing. Please check the data.")
                    return

            # Create a GeoDataFrame by combining the attributes with the geometries
            gdf = gpd.GeoDataFrame(df, geometry=geometries)

            # Set the CRS based on the spatial reference from the API response
            if spatial_ref:
                gdf.set_crs(epsg=spatial_ref, inplace=True)

            if dissolve_column:
                # Perform the dissolve operation by the appropriate column
                if dissolve_column in df.columns:
                    dissolved_gdf = gdf.dissolve(
                        by=dissolve_column, aggfunc='first')
                    dissolved_gdf.reset_index(inplace=True)
                else:
                    st.warning(
                        f"'{dissolve_column}' column not found. Skipping dissolve operation.")
                    dissolved_gdf = gdf
            else:
                dissolved_gdf = gdf  # For points, no dissolve needed

            # Rename 'Name' or 'Street' to 'name'
            if dissolve_column:
                dissolved_gdf.rename(
                    columns={dissolve_column: 'name'}, inplace=True)
            elif api_choice == "Parks and Facilities API":
                dissolved_gdf.rename(
                    columns={'LABEL': 'name'}, inplace=True)

            # Convert 'name' column to lowercase and filter out non-logical names
            if 'name' in dissolved_gdf.columns:
                dissolved_gdf['name'] = dissolved_gdf['name'].str.lower()
                non_logical_names = [
                    "no name trail", "unknown", "no name", "null", "undefined",
                    "trail", "n/a", "na", "-", "", None
                ]

                dissolved_gdf = dissolved_gdf[~dissolved_gdf['name'].isin(
                    non_logical_names)]

                # making name titles --> capitalizing each word
                dissolved_gdf['name'] = dissolved_gdf['name'].str.title()

            if api_choice != "Parks and Facilities API":
                # Check geometries for being far splitted
                dissolved_gdf['far_splitted'] = dissolved_gdf['geometry'].apply(
                    check_far_splitted)

            # Transform the CRS to EPSG:4326 (WGS 84)
            dissolved_gdf = dissolved_gdf.to_crs(epsg=4326)

            # Generate a timestamp for the filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create filenames based on the API name and timestamp
            excel_filename = f"{api_choice.replace(' ', '_').lower()}_{timestamp}.xlsx"
            geojson_filename = f"{api_choice.replace(' ', '_').lower()}_{timestamp}.geojson"

            # Provide options to download the result as an Excel or GeoJSON file
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                dissolved_gdf.to_excel(
                    writer, index=False, sheet_name='Sheet1')

            output.seek(0)

            st.download_button(
                label="Download as Excel",
                data=output,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Convert the dissolved GeoDataFrame to GeoJSON format
            geojson = dissolved_gdf.to_json()
            st.download_button(
                label="Download as GeoJSON",
                data=geojson,
                file_name=geojson_filename,
                mime="application/json"
            )

    if st.button('Back to Home'):
        st.session_state.operation = None
        st.rerun()


# def extract_geometry(features, api_choice):
#     """Extract geometries while ensuring a match with attributes."""
#     geometries, valid_features = [], []

#     for feature in features:
#         if "geometry" in feature:
#             if api_choice in ["Greenways API", "Multi Use Paths API"]:
#                 if "paths" in feature["geometry"]:
#                     for path in feature["geometry"]["paths"]:
#                         geometries.append(LineString(path))
#                         valid_features.append(feature)  # Keep only valid ones
#             elif api_choice == "Parks and Facilities API":
#                 if "x" in feature["geometry"] and "y" in feature["geometry"]:
#                     geometries.append(
#                         Point(feature["geometry"]["x"], feature["geometry"]["y"]))
#                     valid_features.append(feature)  # Keep only valid ones

#     return geometries, valid_features


# def query_apis_page():
#     st.title("Query APIs")

#     api_choice = st.selectbox("Select API to Query:", [
#                               "Greenways API", "Multi Use Paths API", "Parks and Facilities API"])
#     layer_id = st.text_input("Enter Layer ID:", value="0")

#     endpoints = {
#         "Greenways API": f"https://twfgis.wakeforestnc.gov/server/rest/services/Greenways_Wake_Forest/MapServer/{layer_id}/query",
#         "Multi Use Paths API": f"https://twfgis.wakeforestnc.gov/server/rest/services/MultiUsePath/MapServer/{layer_id}/query",
#         "Parks and Facilities API": f"https://twfgis.wakeforestnc.gov/server/rest/services/ParksAndFacilities/MapServer/{layer_id}/query"
#     }

#     if st.button("Query API"):
#         endpoint = endpoints[api_choice]
#         params = {"where": "1=1", "outFields": "*", "f": "json"}
#         data = query_api(endpoint, params)

#         st.write("API Response:", data)  # Debugging output

#         if data and "features" in data:
#             # Extract only features with valid geometries
#             geometries, valid_features = extract_geometry(
#                 data["features"], api_choice)

#             if not geometries:
#                 st.error("No valid geometries found. Check API response.")
#                 return

#             # Extract attributes only from valid features
#             attributes = [feature["attributes"] for feature in valid_features]
#             df = pd.DataFrame(attributes)

#             # Ensure matching lengths before creating GeoDataFrame
#             if len(df) != len(geometries):
#                 st.error(
#                     f"Mismatch: {len(df)} attributes, {len(geometries)} geometries")
#                 return

#             # Create GeoDataFrame
#             gdf = gpd.GeoDataFrame(df, geometry=geometries, crs="EPSG:4326")
#             # Ensure the CRS is set and transformed to WGS84
#             if gdf.crs is None:
#                 gdf.set_crs(epsg=4326, inplace=True)  # Set if missing
#             else:
#                 gdf = gdf.to_crs(epsg=4326)  # Convert if different

#             st.write("Extracted GeoDataFrame:", gdf)

#             # ✅ Extract lat/lon for Streamlit map
#             if not gdf.geometry.is_empty.all():
#                 if api_choice in ["Greenways API", "Multi Use Paths API"]:
#                     gdf["lat"] = gdf.geometry.apply(
#                         lambda geom: geom.coords[0][1] if geom and len(geom.coords) > 0 else None)
#                     gdf["lon"] = gdf.geometry.apply(
#                         lambda geom: geom.coords[0][0] if geom and len(geom.coords) > 0 else None)
#                 elif api_choice == "Parks and Facilities API":
#                     gdf["lat"] = gdf.geometry.y
#                     gdf["lon"] = gdf.geometry.x

#                 # Drop rows where lat/lon could not be extracted
#                 gdf = gdf.dropna(subset=["lat", "lon"])

#                 # ✅ Display map using extracted lat/lon
#                 st.map(gdf[["lat", "lon"]])

#             # Convert to GeoJSON for download
#             geojson_data = gdf.to_json()
#             st.download_button("Download GeoJSON", geojson_data,
#                                "output.geojson", "application/json")
