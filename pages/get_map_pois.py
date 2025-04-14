import streamlit as st
import pandas as pd
import requests


def fetch_pois(map_id, auth_token):
    """Fetch POIs from Wander API and display logs in Streamlit UI."""

    url = f"https://wander-api-dot-wander-production-308019.uc.r.appspot.com/api/maps/{map_id}/markers"
    headers = {
        # Ensure it's a properly formatted Bearer token
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    log_messages = []  # List to store logs for Streamlit UI logging
    log_messages.append(f"🔍 Fetching POIs for map_id: {map_id}")

    response = requests.get(url, headers=headers)

    # log_messages.append(f"Data: {response.json()}")

    log_messages.append(f"📡 Response Status Code: {response.status_code}")
    # First 500 chars
    log_messages.append(f"📜 Response JSON Preview: {response.text[:500]}...")

    if response.status_code != 200:
        st.error(
            f"❌ Error fetching POIs: {response.status_code} - {response.text}")
        log_messages.append(
            f"❌ API Error: {response.status_code} - {response.text}")
        return None, log_messages

    # Parse JSON response
    data = response.json()

    features = []
    if isinstance(data, list):
        for item in data:
            feature_collection = item.get("data", {})
            # Collect from all elements
            features.extend(feature_collection.get("features", []))
    else:
        feature_collection = data.get("data", {})
        features = feature_collection.get("features", [])

    log_messages.append(f"✅ Extracted {len(features)} POIs.")

    # Extract relevant fields from features
    pois = []
    for feature in features:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        poi_data = {
            "ID": properties.get("id", ""),
            "Name": properties.get("name", ""),
            "Description": properties.get("description", ""),
            "Latitude": geometry.get("coordinates", [None, None])[1],
            "Longitude": geometry.get("coordinates", [None, None])[0],
            "Tags": ", ".join(tag["name"] for tag in properties.get("tag_items", [])),
            "First Photo": properties.get("firstPhoto", ""),
        }
        pois.append(poi_data)

        # Append debug log for each extracted POI
        log_messages.append(
            f"📍 Extracted POI: {poi_data['Name']} ({poi_data['Latitude']}, {poi_data['Longitude']})")

    df = pd.DataFrame(pois)
    log_messages.append(f"📊 Final POI DataFrame shape: {df.shape}")

    return df, log_messages


# 🎯 **Streamlit Page**
def fetch_pois_page():
    st.title("Fetch POIs from Wander Map")

    # Input fields
    map_id = st.text_input("Enter Map ID:")
    auth_token = st.text_input("Enter Authorization Token:", type="password")

    if st.button("Fetch POIs"):
        if not map_id or not auth_token:
            st.error("⚠️ Map ID and Authorization Token are required.")
        else:
            df, log_messages = fetch_pois(map_id, auth_token)
            if df is not None and not df.empty:
                st.success(f"✅ Successfully fetched {len(df)} POIs.")
                st.write(df)

                # Allow user to download the POIs as a CSV file
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name="pois.csv",
                    mime="text/csv"
                )

            # **📑 Debug Logs in UI**
            with st.expander("🔎 Debug Logs"):
                for log in log_messages:
                    st.write(log)
