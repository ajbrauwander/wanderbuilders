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
from utils.geospatial_utils import dms_to_decimal, geocode_address, reverse_geocode


GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]


def geocoding_page():
    st.title("Geocoding & Reverse Geocoding")

    option = st.selectbox("Choose an option", [
        "Geocoding", "Reverse Geocoding"])
    coord_format = st.selectbox("Coordinate Format", ["W, N", "lat, lng"])
    query_type = st.radio("Query Type", ["Single Query", "Upload File"])

    if query_type == "Single Query":
        if option == "Geocoding":
            address = st.text_input("Enter the address:")
            if st.button("Geocode"):
                lat, lng = geocode_address(address, GOOGLE_API_KEY)
                if lat and lng:
                    st.write(f"Coordinates: {lat}, {lng}")
                else:
                    st.write("Address not found.")
        else:
            if coord_format == "W, N":
                w = st.text_input("Enter longitude (W):")
                n = st.text_input("Enter latitude (N):")
                if st.button("Reverse Geocode"):
                    lat = dms_to_decimal(n)
                    lon = dms_to_decimal(w)
                    if lat and lon:
                        address = reverse_geocode(lat, lon, GOOGLE_API_KEY)
                        if address:
                            st.write(f"Address: {address}")
                        else:
                            st.write("Coordinates not found.")
                    else:
                        st.write("Invalid DMS coordinates.")
            else:
                lat = st.number_input("Enter latitude:")
                lon = st.number_input("Enter longitude:")
                if st.button("Reverse Geocode"):
                    address = reverse_geocode(lat, lon, GOOGLE_API_KEY)
                    if address:
                        st.write(f"Address: {address}")
                    else:
                        st.write("Coordinates not found.")
    else:
        uploaded_file = st.file_uploader(
            "Choose a file", type=["csv", "xlsx"])
        if uploaded_file:
            if "csv" in uploaded_file.name:
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            if st.button("Process"):
                if option == "Geocoding":
                    df['Coordinates'] = df.iloc[:, 0].apply(
                        lambda addr: geocode_address(addr, GOOGLE_API_KEY))
                    df['Latitude'] = df['Coordinates'].apply(
                        lambda x: x[0])
                    df['Longitude'] = df['Coordinates'].apply(
                        lambda x: x[1])
                    df.drop(columns=['Coordinates'], inplace=True)
                else:
                    if coord_format == "W, N":
                        df['lat'] = df['n'].astype(
                            str).apply(dms_to_decimal)
                        df['lon'] = df['w'].astype(
                            str).apply(dms_to_decimal)
                        df['Address'] = df.apply(lambda row: reverse_geocode(
                            row['lat'], row['lon'], GOOGLE_API_KEY), axis=1)
                    else:
                        df['Address'] = df.apply(lambda row: reverse_geocode(
                            row[0], row[1], GOOGLE_API_KEY), axis=1)

                st.write(df)

                # Save the DataFrame to a BytesIO object
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                    writer.save()
                output.seek(0)

                st.success(
                    "File processed successfully. Download the output file below.")
                st.download_button(
                    label="Download Output",
                    data=output,
                    file_name="output.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    if st.button('Back to Home'):
        st.session_state.operation = None
        st.rerun()

########### end geocoding ############
