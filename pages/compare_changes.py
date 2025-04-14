import streamlit as st
import pandas as pd
import requests
import time
import io
from google.cloud import storage
from google.oauth2 import service_account
import json

# ✅ GCP Storage bucket name
CACHE_BUCKET_NAME = "wander_map_cache"

# ✅ Load raw JSON from Streamlit secrets
service_account_str = st.secrets["gcp"]["service_account_json"]

# ✅ Parse JSON once
try:
    service_account_info = json.loads(service_account_str)
except json.JSONDecodeError as e:
    st.error(f"❌ JSON decoding error: {e}")
    st.stop()

# ✅ Use parsed credentials
credentials = service_account.Credentials.from_service_account_info(
    service_account_info)
storage_client = storage.Client(credentials=credentials)
bucket = storage_client.bucket(CACHE_BUCKET_NAME)

st.success("✅ Successfully authenticated with Google Cloud Storage!")

# ✅ Function to fetch POIs using the corrected Wander API request


def fetch_pois(map_id, auth_token, log_expander):
    """Fetch POIs from the corrected Wander API using an empty JSON payload."""
    BASE_URL = "https://wander-api-209737824514.us-central1.run.app"
    url = f"{BASE_URL}/api/pois/map/{map_id}"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://web.wander-app.com"
    }

    # ✅ Sending an **empty JSON payload** to match the working request
    payload = {}

    log_expander.write(
        f"🔍 Fetching POIs for Map ID: `{map_id}` using the updated API...")
    start_time = time.time()

    response = requests.post(url, headers=headers, json=payload)
    elapsed_time = round(time.time() - start_time, 2)

    log_expander.write(
        f"📡 API Response Status: `{response.status_code}` (⏳ {elapsed_time}s)")

    if response.status_code != 200:
        log_expander.write(
            f"❌ API Error: {response.status_code} - {response.text}")
        return None

    data = response.json()
    pois = []

    # ✅ Extract POIs from the "markers" array
    for marker in data.get("markers", []):
        features = marker.get("data", {}).get("features", [])

        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [None, None])

            pois.append({
                "ID": properties.get("id", ""),
                # ✅ Correct ID field
                "External ID": properties.get("external_id", ""),
                "Name": properties.get("name", ""),
                "Description": properties.get("description", ""),
                "Latitude": coordinates[1],
                "Longitude": coordinates[0],
                "Tags": ", ".join(tag["name"] for tag in properties.get("tag_items", [])),
                "First Photo": properties.get("firstPhoto", ""),
            })

    df = pd.DataFrame(pois)
    log_expander.write(
        f"✅ Extracted `{len(df)}` POIs from Wander Map (⏳ {elapsed_time}s).")

    # ✅ Debugging response content
    log_expander.write(f"📜 Response Preview: `{json.dumps(data)[:500]}`...")

    return df

# ✅ Streamlit UI for Fetching & Comparing POIs


def compare_pois_page():
    st.title("Compare Cached POIs with Wander Map")

    log_expander = st.expander("🔎 Debug Logs")  # Debug logs in UI

    # ✅ Fetch POIs from Wander Map using new API
    map_id = st.text_input("Enter Wander Map ID:")
    auth_token = st.text_input("Enter Authorization Token:", type="password")

    if st.button("Fetch POIs"):
        if not map_id or not auth_token:
            st.error("⚠️ Map ID and Authorization Token are required.")
        else:
            wander_df = fetch_pois(map_id, auth_token, log_expander)

            if wander_df is not None and not wander_df.empty:
                st.success(
                    f"✅ Successfully fetched `{len(wander_df)}` POIs from Wander Map.")
                st.write(wander_df)

                # ✅ Download fetched POIs
                csv_data = wander_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download POIs CSV",
                    data=csv_data,
                    file_name="wander_pois.csv",
                    mime="text/csv"
                )

    with log_expander:
        st.write("🔍 Logs will be displayed here as operations progress.")
