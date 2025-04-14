import streamlit as st
import requests
import pandas as pd
import os
import json
from bs4 import BeautifulSoup
from tqdm import tqdm
from google.cloud import storage
from google.oauth2 import service_account
from datetime import timedelta
from PIL import Image
from io import BytesIO

# Load raw JSON from Streamlit secrets
service_account_str = st.secrets["gcp"]["service_account_json"]

# ✅ Parse JSON once
try:
    service_account_info = json.loads(service_account_str)
except json.JSONDecodeError as e:
    st.error(f"❌ JSON decoding error: {e}")
    st.stop()  # Prevent further execution if JSON is invalid

# ✅ Use parsed credentials
credentials = service_account.Credentials.from_service_account_info(
    service_account_info)
storage_client = storage.Client(credentials=credentials)
bucket_name = "downloaded_poi_images"
bucket = storage_client.bucket(bucket_name)

st.success("✅ Successfully authenticated Google Cloud Storage!")

# 🔹 Function to generate a public URL


def get_public_url(bucket_name, blob_name):
    """Returns a permanent public URL for an object in Google Cloud Storage."""
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

# 🔹 Function to validate the uploaded CSV


def validate_csv(df):
    """Check if the uploaded CSV matches the required format."""
    required_columns = ["listing_id", "name", "description", "longitude", "latitude", "address",
                        "categories", "sub_categories", "amenities", "website", "phone", "media_urls", "other_properties_json"]
    missing_columns = [
        col for col in required_columns if col not in df.columns]
    if missing_columns:
        return False, f"❌ Missing columns: {', '.join(missing_columns)}. Please use the correct template: [CSV Template](https://docs.google.com/spreadsheets/d/1E9MYXIJbyamvT0HE92NtPV8J_bCqsoOG1qWFxh1MEqo/edit?usp=sharing)"
    return True, "✅ CSV format is correct."

# 🔹 Streamlit Page for Scraping POI Images


def scrape_images(df):
    """Scrape images from POI websites and upload to GCP with progress feedback, ensuring public URLs."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
    updated_rows = []
    total_images_uploaded = 0
    pois_with_images = 0
    pois_without_images = 0
    successful_websites = 0
    max_images_per_poi = 10  # Limit to 10 images per POI

    for index, row in df.iterrows():
        poi_name, poi_url = row["name"], row["website"]

        # Ensure URL has http or https
        if isinstance(poi_url, str) and not poi_url.startswith(("http", "https")):
            poi_url = "https://" + poi_url

        if not isinstance(poi_url, str) or not poi_url.startswith(("http", "https")):
            pois_without_images += 1
            updated_rows.append(row.to_dict())
            continue

        try:
            response = requests.get(poi_url, headers=headers, timeout=10)
            if response.status_code != 200:
                pois_without_images += 1
                updated_rows.append(row.to_dict())
                continue

            successful_websites += 1
            soup = BeautifulSoup(response.text, "html.parser")
            image_elements = [img for img in soup.find_all(
                "img") if img.get("class")]

            # Limit the number of images per POI
            image_elements = image_elements[:max_images_per_poi]

            if not image_elements:
                pois_without_images += 1
            else:
                pois_with_images += 1

            image_urls = []
            for img_index, img in enumerate(image_elements, start=1):
                img_url = img.get("src")
                if img_url and img_url.startswith("http"):
                    img_data = requests.get(
                        img_url, headers=headers, timeout=10).content

                    # Upload to GCP
                    gcs_file_name = f"{poi_name.replace(' ', '_')}_{img_index}.jpg"
                    blob = bucket.blob(gcs_file_name)
                    blob.upload_from_string(
                        img_data, content_type="image/jpeg")

                    # ✅ Use public URL instead of signed URL
                    gcs_url = get_public_url(bucket_name, gcs_file_name)
                    image_urls.append(gcs_url)
                    total_images_uploaded += 1

            row_dict = row.to_dict()
            row_dict["media_urls"] = ", ".join(image_urls)  # Store public URLs
            updated_rows.append(row_dict)

        except Exception:
            pois_without_images += 1
            updated_rows.append(row.to_dict())

    return pd.DataFrame(updated_rows), total_images_uploaded, pois_with_images, pois_without_images, successful_websites


def scrape_poi_images_page():
    st.title("Scrape POI Images")
    uploaded_file = st.file_uploader(
        "Upload CSV in Pre-Processing Format", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        is_valid, message = validate_csv(df)
        st.markdown(message, unsafe_allow_html=True)

        if is_valid and st.button("Start Scraping"):
            with st.spinner("Scraping images and uploading to GCP..."):
                updated_df, total_images_uploaded, pois_with_images, pois_without_images, successful_websites = scrape_images(
                    df)

                st.success("✅ Scraping complete! Download updated CSV below.")

                csv_data = updated_df.to_csv(index=False)
                st.download_button("📥 Download Updated CSV", data=csv_data,
                                   file_name="poi_images_updated.csv", mime="text/csv")

                # Ensure that numbers align correctly
                total_pois_processed = pois_with_images + pois_without_images

                st.write(f"📊 **Scraping Summary:**")
                st.write(
                    f"📸 **Total Images Uploaded:** {total_images_uploaded}")
                st.write(f"✅ **POIs with Images:** {pois_with_images}")
                st.write(f"⚠️ **POIs without Images:** {pois_without_images}")
                st.write(
                    f"🌍 **Successfully Accessed Websites:** {successful_websites}")
                st.write(
                    f"🔍 **Total POIs Processed:** {total_pois_processed} / {len(df)}")
                st.write(f"📥 **Total POIs Uploaded:** {len(updated_df)}")
