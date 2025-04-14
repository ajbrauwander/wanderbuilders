import xml.etree.ElementTree as ET
import json
from shapely.geometry import LineString, MultiLineString
import random
import re
import streamlit as st
import numpy as np
import requests


def kml_to_geojson(kml_path):
    tree = ET.parse(kml_path)
    root = tree.getroot()
    kml_ns = "{http://www.opengis.net/kml/2.2}"
    geojson = {"type": "FeatureCollection", "features": []}

    for placemark in root.findall(".//{}Placemark".format(kml_ns)):
        feature = {"type": "Feature", "properties": {}, "geometry": {}}
        polygon = placemark.find(".//{}Polygon".format(kml_ns))
        if polygon is not None:
            feature["geometry"]["type"] = "Polygon"
            outer_boundary = polygon.find(
                "{}outerBoundaryIs/{}LinearRing/{}coordinates".format(kml_ns, kml_ns, kml_ns))
            feature["geometry"]["coordinates"] = [[list(map(float, coord.split(",")))[
                :2] for coord in outer_boundary.text.split()]]
        geojson["features"].append(feature)
    return geojson


def make_random_changes_from_file(gdf, tolerance=0.000007):
    """
    Modify the LineString or MultiLineString geometry in the given GeoDataFrame.

    Parameters:
        gdf (GeoDataFrame): Input GeoDataFrame.
        tolerance (float): Amount by which to randomly alter each coordinate.

    Returns:
        GeoDataFrame: Modified GeoDataFrame.
    """

    def is_linestring_or_multilinestring(geom):
        return isinstance(geom, (LineString, MultiLineString))

    # Filter rows where the geometry is LineString or MultiLineString
    lines = gdf[gdf.geometry.apply(is_linestring_or_multilinestring)]

    # If there are no LineString or MultiLineString geometries, return the original GeoDataFrame
    if lines.shape[0] == 0:
        return gdf

    modified_geoms = []
    for geometry in lines.geometry:
        if isinstance(geometry, LineString):
            coords = list(geometry.coords)
            modified_coords = [(x + random.uniform(-tolerance, tolerance),
                                y + random.uniform(-tolerance, tolerance)) for x, y in coords]
            modified_geoms.append(LineString(modified_coords))
        elif isinstance(geometry, MultiLineString):
            modified_multiline_coords = []
            for linestring in geometry:
                coords = list(linestring.coords)
                modified_coords = [(x + random.uniform(-tolerance, tolerance),
                                    y + random.uniform(-tolerance, tolerance)) for x, y in coords]
                modified_multiline_coords.append(modified_coords)
            modified_geoms.append(
                MultiLineString(modified_multiline_coords))

    # Update the geometry column in the filtered rows
    gdf.loc[lines.index, 'geometry'] = modified_geoms

    return gdf


def convert_arcgis_paths_to_geojson(arcgis_geom):
    """
    Converts an ArcGIS 'paths' geometry object to a GeoJSON structure.

    Parameters:
    arcgis_geom (dict): A dictionary containing the ArcGIS geometry with 'paths'.

    Returns:
    dict: A GeoJSON geometry dictionary.
    """
    paths = arcgis_geom.get('paths', [])

    if len(paths) == 1:
        geojson_geom = LineString(paths[0])
    else:
        geojson_geom = MultiLineString(paths)

    return geojson_geom


def dms_to_decimal(dms_str):
    """
    Convert DMS (degrees, minutes, seconds) format to decimal degrees.

    Parameters:
    dms_str (str): A string in DMS format (e.g., '40° 26′ 46″ N').

    Returns:
    float: Decimal degrees representation of the input coordinate.
    """
    try:
        parts = re.split('[°\'"]+', dms_str.strip())
        if len(parts) >= 3:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            direction = dms_str[-1]
            decimal = degrees + minutes / 60 + seconds / 3600
            if direction in ['W', 'S']:
                decimal = -decimal
            return decimal
        else:
            return None
    except Exception as e:
        st.warning(f"Error converting DMS to decimal: {e}")
        return None


def check_far_splitted(geometry, threshold=50):
    """
    Check if any segments in the LineString or MultiLineString geometry are far splitted.

    Parameters:
    geometry: Shapely geometry (LineString or MultiLineString)
    threshold: Distance in meters beyond which segments are considered far-splitted

    Returns:
    str: 'yes' if the geometry is far splitted, 'no' otherwise.
    """
    if isinstance(geometry, LineString):
        segments = [geometry]
    elif isinstance(geometry, MultiLineString):
        segments = list(geometry.geoms)
    else:
        return 'no'  # If not a LineString or MultiLineString

    for i in range(len(segments) - 1):
        # Get the end point of the current segment and the start point of the next segment
        end_point = segments[i].coords[-1]
        start_point = segments[i + 1].coords[0]

        # Calculate the Euclidean distance between these points
        distance = np.sqrt(
            (end_point[0] - start_point[0])**2 + (end_point[1] - start_point[1])**2)

        if distance > threshold:
            return 'yes'

    return 'no'


def geocode_address(address, api_key):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
    response = requests.get(url).json()
    if response['status'] == 'OK':
        location = response['results'][0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        return None, None


def reverse_geocode(lat, lng, api_key):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={api_key}"
    response = requests.get(url).json()
    if response['status'] == 'OK':
        address = response['results'][0]['formatted_address']
        return address
    else:
        return None


# Function to extract coordinates from KML
def extract_coordinates(coordinates):
    coords = coordinates.text.split()
    coord_list = []
    for coord in coords:
        lon, lat, _ = coord.split(",")
        coord_list.append([float(lon), float(lat)])
    return coord_list


def kml_to_geojson(kml_path):
    # Parse the KML file
    tree = ET.parse(kml_path)
    root = tree.getroot()

    # Define the KML namespace
    kml_ns = "{http://www.opengis.net/kml/2.2}"

    # Define the base structure for the GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    # Function to extract coordinates from KML
    def extract_coordinates(coordinates):
        coords = coordinates.text.split()
        coord_list = []
        for coord in coords:
            lon, lat, _ = coord.split(",")
            coord_list.append([float(lon), float(lat)])
        return coord_list

    # Iterate over Placemark elements in the KML
    for placemark in root.findall(".//{}Placemark".format(kml_ns)):
        # Create a base feature structure
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {}
        }

        # Extract Polygon geometries
        polygon = placemark.find(".//{}Polygon".format(kml_ns))
        if polygon is not None:
            feature["geometry"]["type"] = "Polygon"
            outer_boundary = polygon.find(
                "{}outerBoundaryIs/{}LinearRing/{}coordinates".format(kml_ns, kml_ns, kml_ns))
            feature["geometry"]["coordinates"] = [
                extract_coordinates(outer_boundary)]

        # Extract LineString geometries
        linestring = placemark.find(".//{}LineString".format(kml_ns))
        if linestring is not None:
            feature["geometry"]["type"] = "LineString"
            coordinates = linestring.find("{}coordinates".format(kml_ns))
            feature["geometry"]["coordinates"] = extract_coordinates(
                coordinates)

        # If we've defined a geometry, add the feature to the list
        if "type" in feature["geometry"]:
            geojson["features"].append(feature)

    return geojson


def convert_kml_to_geojson():
    st.header("Convert KML to GeoJSON")

    uploaded_file = st.file_uploader("Choose a KML file", type="kml")
    if uploaded_file:
        geojson_data = kml_to_geojson(uploaded_file)

        # Convert the GeoJSON data to a GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

        # Check if the geometry type is LineString or MultiLineString
        if any(gdf["geometry"].geom_type.isin(["LineString", "MultiLineString"])):
            # Alter the geometry with the provided function
            gdf = make_random_changes_from_file(gdf)

        # Extract the file name without the extension and keep the spaces
        file_name_without_extension = os.path.splitext(uploaded_file.name)[
            0]

        # Add the 'Name' column to the GeoDataFrame
        gdf['Name'] = file_name_without_extension

        # Convert the modified GeoDataFrame back to GeoJSON
        geojson_data = json.loads(gdf.to_json())

        # Convert GeoJSON data to a string and then encode it
        geojson_str = json.dumps(geojson_data)
        geojson_bytes = geojson_str.encode('utf-8')

        # Use BytesIO to hold the byte data
        buffer = BytesIO()
        buffer.write(geojson_bytes)
        buffer.seek(0)

        # Create a download link for the GeoJSON data
        fname = file_name_without_extension + ".geojson"
        st.markdown(
            f"<a href='data:application/json;charset=utf-8;,{geojson_str}' download='{fname}'>Click here to download the modified GeoJSON file</a>",
            unsafe_allow_html=True
        )

    if st.button('Back to Home'):
        st.session_state.operation = None
        st.rerun()


def is_lat_lon(value):
    try:
        lat, lon = map(float, value.split(','))
        return True
    except:
        return False
