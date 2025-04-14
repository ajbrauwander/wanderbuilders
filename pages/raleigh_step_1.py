import streamlit as st
import pandas as pd
import requests
import json
import time
from openai import OpenAI

# ✅ Define API Endpoints
BASE_URL = "https://wander-api-dot-wander-production-308019.uc.r.appspot.com"

# ✅ Initialize OpenAI Client
openai_api_key = st.secrets["openai"]["api_key"]
openai_client = OpenAI(api_key=openai_api_key)

# ✅ Define Available Maps (Dropdown Options)
MAP_OPTIONS = {
    "Raleigh/Wake County": "5b40717c-59b6-42a3-ba2c-499b176cf810",
    "Yosemite Mariposa": "62322d4a-2688-406a-8138-2dc2e8976a6a",
    "Paris Must-Visit": "map_789",
}

# ✅ Extract POIs Function


def extract_pois(poi_type, data):
    """Extract POIs from API response and handle geometry types."""
    pois = []

    # 🔹 Debug: Check Data Type
    st.write(f"🔍 Extracting `{poi_type}` - Raw Data Type:", type(data))

    if isinstance(data, dict):  # Ensure consistency
        data = [data]

    if not isinstance(data, list):
        st.error(
            f"❌ Unexpected response format for `{poi_type}`: {type(data)}")
        return pois

    for item in data:
        if not isinstance(item, dict):
            st.warning(f"⚠️ Unexpected list element in `{poi_type}`: {item}")
            continue

        features = item.get("data", {}).get("features", [])
        st.write(f"✅ `{poi_type}` - Number of Features:", len(features))

        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            latitude, longitude = None, None

            # ✅ Handle Different Geometry Types
            if geometry.get("type") == "Point":
                if isinstance(coordinates, list) and len(coordinates) >= 2:
                    latitude, longitude = coordinates[1], coordinates[0]
            elif geometry.get("type") in ["MultiLineString", "Polygon"]:
                if isinstance(coordinates, list) and len(coordinates) > 0:
                    first_segment = coordinates[0]
                    if isinstance(first_segment, list) and len(first_segment) > 0:
                        first_point = first_segment[0]
                        if isinstance(first_point, list) and len(first_point) >= 2:
                            latitude, longitude = first_point[1], first_point[0]

            pois.append({
                "Type": poi_type[:-1].capitalize(),
                "ID": properties.get("id", ""),
                "External ID": properties.get("external_id", ""),
                "Name": properties.get("name", ""),
                "Description": properties.get("description", ""),
                "Latitude": latitude,
                "Longitude": longitude,
                "Tags": ", ".join(tag["name"] for tag in properties.get("tag_items", [])),
                "First Photo": properties.get("firstPhoto", ""),
                "Website": properties.get("website", ""),
            })

    # 🔹 Debug: Check Extracted POIs
    st.write(f"✅ `{poi_type}` Extracted POIs:", len(pois))

    return pois

# ✅ Fetch POIs Function


def fetch_pois(map_id):
    """Fetch POIs (Markers & Paths) from Wander API and return as DataFrame."""
    headers = {"Content-Type": "application/json"}
    all_pois = []
    full_api_responses = {}

    for poi_type in ["markers", "paths"]:
        url = f"{BASE_URL}/api/maps/{map_id}/{poi_type}"
        start_time = time.time()
        response = requests.get(url, headers=headers)
        elapsed_time = round(time.time() - start_time, 2)

        st.write(
            f"📡 Fetching `{poi_type}`... (Took {elapsed_time}s) - HTTP {response.status_code}")

        if response.status_code != 200:
            st.warning(
                f"⚠️ Failed to fetch {poi_type}: HTTP {response.status_code}")
            continue

        try:
            if isinstance(response.text, str):
                data = json.loads(response.text)
            else:
                data = response.json()

            full_api_responses[poi_type] = data

            # 🔹 Debug: Print API Response Structure
            st.write(f"🔍 `{poi_type}` API Response Structure:", type(data))
            st.write(f"📌 `{poi_type}` Sample Data:",
                     json.dumps(data, indent=2)[:500])

        except json.JSONDecodeError:
            st.error(f"❌ Error decoding JSON response for `{poi_type}`")
            continue

        pois = extract_pois(poi_type, data)
        all_pois.extend(pois)

    # 🔹 Debug: Final POI Count
    st.write(f"✅ Total POIs Extracted (Markers + Paths):", len(all_pois))

    # ✅ Convert extracted POIs to DataFrame
    pois_df = pd.DataFrame(all_pois)

    # ✅ Save Full API Response as JSON
    json_filename = f"wander_pois_{map_id}.json"
    st.download_button(
        label="📥 Download Full API Response (JSON)",
        data=json.dumps(full_api_responses, indent=2),
        file_name=json_filename,
        mime="application/json"
    )

    return pois_df

# ✅ Streamlit UI for POI Fetching & Scraping


def raleigh_page_1():
    st.title("📍 Wander Map POI Viewer & Scraper")

    if "pois_df" not in st.session_state:
        st.session_state.pois_df = None

    selected_map = st.selectbox(
        "Select a Wander Map:", options=list(MAP_OPTIONS.keys()))
    map_id = MAP_OPTIONS[selected_map]

    if st.button("Fetch POIs"):
        with st.spinner(f"Fetching POIs for **{selected_map}**..."):
            pois_df = fetch_pois(map_id)
            if not pois_df.empty:
                st.session_state.pois_df = pois_df
                st.success(
                    f"✅ Retrieved `{len(pois_df)}` POIs from **{selected_map}**.")
                st.dataframe(pois_df)

    if st.session_state.pois_df is not None:
        # 🔹 Debug: Display Final DataFrame
        st.write(f"📊 Final DataFrame Shape:", st.session_state.pois_df.shape)
        st.write(st.session_state.pois_df.head())

        st.download_button(
            label="📥 Download POIs CSV",
            data=st.session_state.pois_df.to_csv(index=False),
            file_name="wander_pois.csv",
            mime="text/csv"
        )

    st.info("Select a map and click **Fetch POIs** to view data.")
