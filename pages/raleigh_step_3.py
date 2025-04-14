import streamlit as st
import requests
import pandas as pd
import json
from bs4 import BeautifulSoup
from google.cloud import storage
from google.oauth2 import service_account
import time
import logging
from PIL import Image
from io import BytesIO
from datetime import datetime

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s', force=True)


def log_and_flush(message):
    """Logs a message and ensures it's flushed immediately."""
    logging.info(message)
    st.text(message)


# ✅ Load GCP Credentials
service_account_str = st.secrets["gcp"]["service_account_json"]
try:
    service_account_info = json.loads(service_account_str)
except json.JSONDecodeError as e:
    st.error(f"❌ JSON decoding error: {e}")
    st.stop()

credentials = service_account.Credentials.from_service_account_info(
    service_account_info)
storage_client = storage.Client(credentials=credentials)
bucket_name = "downloaded_poi_images"
bucket = storage_client.bucket(bucket_name)
st.success("✅ Successfully authenticated Google Cloud Storage!")

# 🔹 Function to generate a public URL


def get_public_url(bucket_name, blob_name):
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

# 🔹 Function to upload CSV to GCP bucket


def upload_csv_to_gcp(batch_df, batch_number, map_name):
    if batch_df.empty:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{map_name}_poi_images_batch_{batch_number}_{timestamp}.csv"
    blob = bucket.blob(csv_filename)
    blob.upload_from_string(batch_df.to_csv(
        index=False), content_type="text/csv")
    return get_public_url(bucket_name, csv_filename)

# ✅ Scrape Images Function


def scrape_images(df, map_name):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
    updated_rows = []
    max_images_per_poi = 6  # Limit to 6 images per POI
    batch_size = 100
    batch_number = 1
    batch_dfs = []
    batch_urls = []
    progress_bar = st.progress(0)
    total_pois = len(df)
    image_display = st.empty()

    for index, row in df.iterrows():
        poi_name, poi_url = row["Name"], row["Website"]

        # Skip POIs that already have images
        if pd.notna(row.get("First Photo")) and row["First Photo"]:
            log_and_flush(f"Skipping {poi_name}: Already has images")
            updated_rows.append(row.to_dict())
            continue

        if isinstance(poi_url, str) and not poi_url.startswith(("http", "https")):
            poi_url = "https://" + poi_url

        if not isinstance(poi_url, str) or not poi_url.startswith(("http", "https")):
            log_and_flush(f"Skipping {poi_name}: Invalid URL")
            updated_rows.append(row.to_dict())
            continue

        try:
            response = requests.get(poi_url, headers=headers, timeout=10)
            if response.status_code != 200:
                log_and_flush(f"Skipping {poi_name}: Unable to access website")
                updated_rows.append(row.to_dict())
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            image_elements = [img for img in soup.find_all(
                "img") if img.get("src")]
            image_elements = image_elements[:max_images_per_poi]

            image_urls = []
            for img_index, img in enumerate(image_elements, start=1):
                img_url = img.get("src")
                if img_url and img_url.startswith("http"):
                    img_data = requests.get(
                        img_url, headers=headers, timeout=10).content
                    gcs_file_name = f"{poi_name.replace(' ', '_')}_{img_index}.jpg"
                    blob = bucket.blob(gcs_file_name)
                    blob.upload_from_string(
                        img_data, content_type="image/jpeg")
                    gcs_url = get_public_url(bucket_name, gcs_file_name)
                    image_urls.append(gcs_url)

                    # Display only the current image in Streamlit
                    image = Image.open(BytesIO(img_data))
                    image_display.image(
                        image, caption=f"{poi_name} - Image {img_index}", use_column_width=True)
                    log_and_flush(
                        f"Uploaded image {img_index} for {poi_name}: {gcs_url}")
                    time.sleep(1)

            row_dict = row.to_dict()
            row_dict["image_urls"] = ", ".join(image_urls)
            updated_rows.append(row_dict)
            log_and_flush(
                f"Processed {poi_name}: Uploaded {len(image_urls)} images")
            progress_bar.progress((index + 1) / total_pois)

            # Save batches every batch_size POIs
            if len(updated_rows) % batch_size == 0:
                batch_df = pd.DataFrame(updated_rows)
                batch_dfs.append((batch_number, batch_df))
                batch_url = upload_csv_to_gcp(batch_df, batch_number, map_name)
                if batch_url:
                    batch_urls.append(batch_url)
                batch_number += 1
                updated_rows = []

        except Exception as e:
            log_and_flush(f"Skipping {poi_name}: Error - {str(e)}")
            updated_rows.append(row.to_dict())

    # Display batch download buttons
    for i, batch_url in enumerate(batch_urls):
        st.markdown(f"[📥 Download Batch {i+1}]( {batch_url} )")

    return pd.DataFrame(updated_rows)

# ✅ Streamlit UI for Image Scraping


def raleigh_page_3():
    st.title("Scrape POI Images")
    uploaded_file = st.file_uploader("Upload CSV with POI Data", type=["csv"])
    map_name = st.text_input("Enter Map Name")

    if uploaded_file and map_name:
        df = pd.read_csv(uploaded_file)
        required_columns = ["Type", "ID", "External ID", "Name", "Description",
                            "Latitude", "Longitude", "Tags", "First Photo", "Website"]
        missing_columns = [
            col for col in required_columns if col not in df.columns]

        if missing_columns:
            st.error(f"❌ Missing columns: {', '.join(missing_columns)}")
            return

        if st.button("Start Scraping"):
            with st.spinner("Scraping images and uploading to GCP..."):
                updated_df = scrape_images(df, map_name)
                st.success("✅ Scraping complete! Download updated CSV below.")
                csv_data = updated_df.to_csv(index=False)
                st.download_button("📥 Download Complete CSV", data=csv_data,
                                   file_name=f"{map_name}_poi_images_updated.csv", mime="text/csv")
