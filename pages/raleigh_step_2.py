import streamlit as st
import pandas as pd
import requests
import json
import time
import logging

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s', force=True)


def log_and_flush(message):
    """Logs a message and ensures it's flushed immediately."""
    logging.info(message)
    st.text(message)


# ✅ Define API Endpoint
BASE_URL = "https://wander-api-dot-wander-production-308019.uc.r.appspot.com"

# ✅ Fetch POI Details Function


def fetch_poi_details(poi_id):
    """Fetch POI details from Wander API."""
    url = f"{BASE_URL}/api/places-of-interest/id/{poi_id}"
    headers = {"Content-Type": "application/json"}

    log_and_flush(f"Fetching details for POI ID: {poi_id} from {url}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        try:
            poi_data = response.json()
            website = poi_data.get("data", {}).get("website", "")
            if website:
                log_and_flush(
                    f"Retrieved website URL for POI ID {poi_id}: {website}")
            else:
                log_and_flush(f"POI ID {poi_id} does not have a website URL")

            return poi_data
        except json.JSONDecodeError:
            log_and_flush(f"JSON decoding failed for POI ID: {poi_id}")
            return None
    else:
        log_and_flush(
            f"Failed to fetch POI details for ID {poi_id}, HTTP Status: {response.status_code}, Response: {response.text}")
    return None

# ✅ Process Uploaded CSV


def process_uploaded_csv(uploaded_file):
    """Process the uploaded CSV file and return a DataFrame."""
    log_and_flush("Processing uploaded CSV file.")
    df = pd.read_csv(uploaded_file)
    return df

# ✅ Generate POI Report


def generate_poi_report(df):
    """Identify missing images and descriptions, fetch details, and create a report."""
    missing_data_pois = df[(df["First Photo"].isna()) |
                           (df["Description"].isna())]
    updated_pois = []

    log_and_flush(
        f"Identified {len(missing_data_pois)} POIs with missing data.")

    for index, row in missing_data_pois.iterrows():
        poi_id = row["ID"]
        log_and_flush(f"Fetching missing details for POI ID: {poi_id}")
        details = fetch_poi_details(poi_id)

        if details:
            data = details.get("data", {})  # Extracting directly from "data"
            row["Description"] = row["Description"] if pd.notna(
                row["Description"]) else data.get("description", "")
            row["First Photo"] = row["First Photo"] if pd.notna(
                row["First Photo"]) else data.get("photos", "")
            row["Website"] = data.get("website", "")

        updated_pois.append(row)
        log_and_flush(
            f"Completed processing POI {index + 1} out of {len(missing_data_pois)}")
        time.sleep(1)  # Avoid excessive API calls

    log_and_flush("POI report generation complete.")
    return pd.DataFrame(updated_pois)

# ✅ Streamlit UI for POI Report


def raleigh_page_2():
    st.title("📍 POI Data Completeness Report")

    uploaded_file = st.file_uploader("Upload a POI CSV File", type=["csv"])

    if uploaded_file is not None:
        df = process_uploaded_csv(uploaded_file)

        missing_images = df["First Photo"].isna().sum()
        missing_descriptions = df["Description"].isna().sum()
        total_pois = len(df)

        st.write(f"### Report Summary")
        st.write(f"- Total POIs: {total_pois}")
        st.write(f"- POIs Missing Images: {missing_images}")
        st.write(f"- POIs Missing Descriptions: {missing_descriptions}")

        log_and_flush(
            f"Total POIs: {total_pois}, Missing Images: {missing_images}, Missing Descriptions: {missing_descriptions}")

        if st.button("Fetch Missing Data"):
            with st.spinner("Fetching missing details..."):
                log_and_flush("Starting to fetch missing details for POIs...")
                updated_df = generate_poi_report(df)
                st.success("Data retrieval complete!")
                log_and_flush("Data retrieval completed successfully.")

                # Show table
                st.dataframe(updated_df)

                # Download button
                csv = updated_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Updated POI Data",
                    data=csv,
                    file_name="updated_pois.csv",
                    mime="text/csv"
                )
                log_and_flush("Download link for updated POI data generated.")
