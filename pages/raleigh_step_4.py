import streamlit as st
import requests
import pandas as pd
import json
import time
import logging
import re

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s', force=True)


def log_and_flush(message):
    """Logs a message and ensures it's flushed immediately."""
    logging.info(message)
    st.text(message)


# ✅ Define API Endpoint
BASE_URL = "https://wander-api-dot-wander-production-308019.uc.r.appspot.com"

# ✅ Validate URL Function


def is_valid_url(url):
    """Check if a given string is a valid URL."""
    regex = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'(([A-Za-z0-9-]+\.)+[A-Za-z]{2,6})'  # Domain
        r'(:\d{1,5})?'  # Optional port
        r'(/.*)?$',  # Path
        re.IGNORECASE
    )
    return bool(regex.match(url))

# ✅ Validate Auth Token Function


def validate_auth_token(auth_token):
    """Check if the provided auth token is valid by making a test request."""
    url = f"{BASE_URL}/api/maps"
    headers = {
        "Authorization": f"Bearer {auth_token}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        log_and_flush("✅ Auth token is valid!")
        return True
    else:
        log_and_flush(
            f"❌ Invalid auth token: HTTP {response.status_code} - {response.text}")
        return False

# ✅ Update POI Photos Function (PATCH request)


def update_poi_photos(map_id, poi_id, poi_name, image_urls, auth_token):
    """Update POI with images in the Wander database using PATCH request."""
    valid_urls = [url.strip()
                  for url in image_urls if is_valid_url(url.strip())]

    if not valid_urls:
        log_and_flush(
            f"⚠️ Skipping POI {poi_id} ({poi_name}): No valid image URLs found.")
        return

    log_and_flush(
        f"🔍 Preparing to update POI {poi_id} ({poi_name}) with {len(valid_urls)} images...")
    log_and_flush(f"📸 Image URLs: {valid_urls}")

    url = f"{BASE_URL}/api/maps/{map_id}/markers/{poi_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    payload = {
        "marker": {
            "poi_medias": [
                {"media": url, "is_highlight": i == 0, "sort_order": i}
                for i, url in enumerate(valid_urls)
            ]
        }
    }

    response = requests.patch(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        log_and_flush(
            f"✅ Successfully updated POI {poi_id} ({poi_name}) with images.")
    else:
        log_and_flush(
            f"❌ Failed to update POI {poi_id} ({poi_name}), HTTP {response.status_code}: {response.text}")

# ✅ Streamlit UI for POI Update


def raleigh_page_4():
    st.title("Update POIs with Images")

    map_id = st.text_input("Enter Map ID")
    auth_token = st.text_input("Enter Auth Token", type="password")
    uploaded_file = st.file_uploader("Upload CSV with POI Data", type=["csv"])

    if uploaded_file and map_id and auth_token:
        df = pd.read_csv(uploaded_file)
        required_columns = ["ID", "Name", "image_urls"]
        missing_columns = [
            col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"❌ Missing columns: {', '.join(missing_columns)}")
            return

        # if not validate_auth_token(auth_token):
        #     st.error("❌ Invalid Auth Token! Please check and try again.")
        #     return

        if st.button("Start Updating POIs"):
            with st.spinner("Updating POIs in Wander database..."):
                for index, row in df.iterrows():
                    poi_id = row["ID"]
                    poi_name = row["Name"]
                    image_urls = str(row["image_urls"]).split(", ")
                    update_poi_photos(map_id, poi_id, poi_name,
                                      image_urls, auth_token)
                    time.sleep(1)  # Avoid excessive API calls

                st.success("✅ POI updates completed!")
