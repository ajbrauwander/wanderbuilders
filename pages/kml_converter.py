import streamlit as st
import geopandas as gpd
import json
import os
import xml.etree.ElementTree as ET
from io import BytesIO
from utils.geospatial_utils import kml_to_geojson, make_random_changes_from_file


def convert_kml_to_geojson():
    st.header("Convert KML to GeoJSON")

    uploaded_file = st.file_uploader("Choose a KML file", type="kml")
    if uploaded_file:
        geojson_data = kml_to_geojson(uploaded_file)

        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

        # Modify geometry if necessary
        if any(gdf["geometry"].geom_type.isin(["LineString", "MultiLineString"])):
            gdf = make_random_changes_from_file(gdf)

        # Extract file name without extension
        file_name = os.path.splitext(uploaded_file.name)[0]

        # Add 'Name' column
        gdf['Name'] = file_name

        # Convert GeoDataFrame to GeoJSON
        geojson_data = json.loads(gdf.to_json())
        geojson_str = json.dumps(geojson_data)

        # Provide download link
        st.download_button(
            label="Download GeoJSON",
            data=geojson_str,
            file_name=f"{file_name}.geojson",
            mime="application/json"
        )

    if st.button('Back to Home'):
        st.session_state.operation = None
        st.rerun()
