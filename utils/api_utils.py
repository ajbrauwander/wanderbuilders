import time
import requests
import os
import streamlit as st

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]


def geocode_address(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_API_KEY}"
    response = requests.get(url).json()
    return response['results'][0]['geometry']['location'].values() if response['status'] == 'OK' else (None, None)


def reverse_geocode(lat, lng):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={GOOGLE_API_KEY}"
    response = requests.get(url).json()
    return response['results'][0]['formatted_address'] if response['status'] == 'OK' else None


def query_api(endpoint, params):
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error querying API: {e}")
        return None


def fetch_google_places(api_url, params):
    """
    Fetches Google Places API results, handling pagination.
    """
    all_places = []
    next_page_token = None

    while True:
        # If a next page token exists, add it to parameters
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
            # Google API requires delay before using next_page_token
            time.sleep(2)

    return all_places


def search_google_pois(place_name, api_key, selected_types=None):
    """
    Searches for Points of Interest (POIs) using the Google Places API.
    """
    API_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    # Step 1: Get place location
    params = {
        'input': place_name,
        'inputtype': 'textquery',
        'fields': 'geometry',
        'key': api_key
    }

    response = requests.get(API_URL, params=params).json()
    if response.get("candidates"):
        location = response['candidates'][0]['geometry']['location']

        # Step 2: Search for POIs nearby
        nearby_params = {
            'location': f"{location['lat']},{location['lng']}",
            'radius': '30000',
            'type': '|'.join(selected_types) if selected_types else "",
            'key': api_key
        }

        all_places = fetch_google_places(NEARBY_SEARCH_URL, nearby_params)
        st.write(f"Found {len(all_places)} places from Google")
        return all_places

    return []
