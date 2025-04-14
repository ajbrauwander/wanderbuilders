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

################
################

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]


def download_link(object_to_download, download_filename, download_link_text):
    """
    Generates a link to download the given object_to_download.
    """
    if isinstance(object_to_download, pd.DataFrame):
        object_to_download = object_to_download.to_json(orient='records')

    b64 = base64.b64encode(object_to_download.encode()).decode()
    return f'<a href="data:text/json;base64,{b64}" download="{download_filename}"> {download_link_text} </a>'


def csv_download_link(object_to_download, download_filename, download_link_text):
    """
    Generates a link to download the given object_to_download.
    """
    if isinstance(object_to_download, pd.DataFrame):
        object_to_download = object_to_download.to_csv(index=False)

    b64 = base64.b64encode(object_to_download.encode()).decode()
    return f'<a href="data:text/csv;base64,{b64}" download="{download_filename}"> {download_link_text} </a>'


def fetch_google_places(api_url, params):
    all_places = []
    next_page_token = None

    while True:
        # Include the next page token in parameters if it exists
        if next_page_token:
            params['pagetoken'] = next_page_token
        else:
            params.pop('pagetoken', None)

        response = requests.get(api_url, params=params)
        results = response.json()

        all_places.extend(results.get('results', []))

        next_page_token = results.get('next_page_token')
        if not next_page_token:
            break
        else:
            time.sleep(2)

    return all_places


def search_google_pois(place_name, api_key, selected_types=None):
    API_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    # Parameters for the initial place search
    params = {
        'input': place_name,
        'inputtype': 'textquery',
        'fields': 'photos,formatted_address,name,geometry',
        'key': api_key
    }

    # Make the initial search to get the location
    place_response = requests.get(API_URL, params=params).json()
    if place_response.get("candidates"):
        location = place_response['candidates'][0]['geometry']['location']

        # Parameters for nearby search, based on the found location
        nearby_params = {
            'location': f"{location['lat']},{location['lng']}",
            'radius': '30000',
            'type': '|'.join(selected_types),
            'key': api_key
        }

        # Fetch all places using the nearby search API endpoint
        response = requests.get(NEARBY_SEARCH_URL, params=nearby_params)
        results = response.json()

        # Fetch all places using the nearby search API endpoint
        all_places = fetch_google_places(NEARBY_SEARCH_URL, nearby_params)
        st.write(f"Found {len(all_places)} places from Google")
        # Process and display the results as needed
        return all_places
    else:
        return []


def search_pois():
    st.header("Search for Points of Interest")
    place_name = st.text_input("Enter a place name or address:")
    search_type = st.radio("Select Search Type", ["OSM", "Google POIs"])

    google_types = [
        "accounting", "airport", "amusement_park", "aquarium", "art_gallery", "atm",
        "bakery", "bank", "bar", "beauty_salon", "bicycle_store", "book_store",
        "bowling_alley", "bus_station", "cafe", "campground", "car_dealer", "car_rental",
        "car_repair", "car_wash", "casino", "cemetery", "church", "city_hall",
        "clothing_store", "convenience_store", "courthouse", "dentist", "department_store",
        "doctor", "drugstore", "electrician", "electronics_store", "embassy",
        "fire_station", "florist", "funeral_home", "furniture_store", "gas_station", "gym",
        "hair_care", "hardware_store", "hindu_temple", "home_goods_store", "hospital",
        "insurance_agency", "jewelry_store", "laundry", "lawyer", "library",
        "light_rail_station", "liquor_store", "local_government_office", "locksmith",
        "lodging", "meal_delivery", "meal_takeaway", "mosque", "movie_rental",
        "movie_theater", "moving_company", "museum", "night_club", "painter", "park",
        "parking", "pet_store", "pharmacy", "physiotherapist", "plumber", "police",
        "post_office", "primary_school", "real_estate_agency", "restaurant",
        "roofing_contractor", "rv_park", "school", "secondary_school", "shoe_store",
        "shopping_mall", "spa", "stadium", "storage", "store", "subway_station",
        "supermarket", "synagogue", "taxi_stand", "tourist_attraction", "train_station",
        "transit_station", "travel_agency", "university", "veterinary_care", "zoo"
    ]

    if search_type == "OSM":
        # Define categories and corresponding OSM tags
        category_tags = {
            "Lodging": [{"tourism": ["hotel", "motel", "guest_house", "hostel"]}],
            "Food & Drink": [{"amenity": ["restaurant", "cafe", "pub", "bar"]}],
            "Shopping": [{"shop": True}],
            "Things To Do": [{"tourism": "attraction"}, {"leisure": ["park", "sports_centre"]}],
            "Museums": [{"tourism": "museum"}]
        }

        # Implement the multiselect widget for category selection
        selected_categories = st.multiselect(
            'Select Categories to Search For:',
            options=list(category_tags.keys()),  # Display category names
            default=['Food & Drink']  # Default selection
        )

        # Build list of tags based on selected categories
        tags = {}
        for category in selected_categories:
            for tag in category_tags[category]:
                tags.update(tag)

    elif search_type == "Google POIs":
        selected_types = st.multiselect(
            'Select Types to Search For:', google_types, ['restaurant'])

    if st.button("Search"):
        if search_type == "OSM" and place_name:
            # Using OSMnx to search for amenities based on selected tags
            gdf = ox.geometries_from_place(place_name, tags=tags)
            # Dissolve by 'name' to aggregate geometries and filter for Points
            gdf_dissolved = gdf.dissolve(
                by='name')[['geometry']].reset_index()
            gdf_dissolved = gdf_dissolved[gdf_dissolved['geometry'].geom_type == 'Point']

            # Convert to GeoJSON
            geojson_str = gdf_dissolved.to_json()
            csv_text = gdf_dissolved.to_csv(index=False)

            # Generate download link for the GeoJSON file
            b64 = base64.b64encode(geojson_str.encode()).decode()
            href = f'<a href="data:file/json;base64,{b64}" download="{place_name}_{selected_categories}_OSM_POIs.geojson">Download GeoJSON file</a>'
            st.markdown(href, unsafe_allow_html=True)

            # Generate download link for the CSV file
            b64 = base64.b64encode(csv_text.encode()).decode()
            href = f'<a href="data:file/json;base64,{b64}" download="{place_name}_{selected_categories}_OSM_POIs.csv">Download CSV file</a>'
            st.markdown(href, unsafe_allow_html=True)

        elif search_type == "Google POIs" and place_name:
            places = search_google_pois(
                place_name, GOOGLE_API_KEY, selected_types)
            if places:
                # Process places to a GeoJSON format
                features = [{
                    "type": "Feature",
                    "properties": {"name": place.get("name")},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [place.get("geometry", {}).get("location", {}).get("lng"),
                                        place.get("geometry", {}).get("location", {}).get("lat")]
                    }
                } for place in places]

                geojson = {
                    "type": "FeatureCollection",
                    "features": features
                }

                # Convert to GeoJSON string and encode for download
                geojson_str = json.dumps(geojson)
                b64 = base64.b64encode(geojson_str.encode()).decode()
                href = f'<a href="data:file/json;base64,{b64}" download="{place_name}_{selected_types}_Google_POIs.geojson">Download GeoJSON file</a>'
                st.markdown(href, unsafe_allow_html=True)

##############################

                # Convert each place to a simplified dictionary for CSV conversion
                places_dicts = [{
                    "Name": place.get("name"),
                    "Latitude": place.get("geometry", {}).get("location", {}).get("lat"),
                    "Longitude": place.get("geometry", {}).get("location", {}).get("lng")
                } for place in places]  # `places` should be defined elsewhere in your actual request handling

                # Create a DataFrame
                df = pd.DataFrame(places_dicts)

                # Generate download link for the CSV
                href = csv_download_link(
                    df, f"{place_name.replace(' ', '_')}_{selected_types}_Google_POIs.csv", "Download CSV")
                st.markdown(href, unsafe_allow_html=True)

##############################
            else:
                st.write("No POIs found.")

        # OSM search logic remains unchanged

    if st.button('Back to Home'):
        st.session_state.operation = None
        st.rerun()
##################
# search POIs page
