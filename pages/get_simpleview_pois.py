import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET
import json
import time


def fetch_simpleview_pois(api_key, api_url):
    """Fetch POIs from Simpleview API and return as DataFrame with logs."""
    log_messages = []
    log_messages.append(f"🔍 Fetching POIs using API Key: {api_key}")

    response = requests.get(api_url.format(api_key=api_key))
    log_messages.append(f"📡 Response Status Code: {response.status_code}")

    if response.status_code != 200:
        log_messages.append(
            f"❌ API Error: {response.status_code} - {response.text}")
        return None, log_messages

    content = response.text.strip()
    log_messages.append(f"📜 Response Sample: {content[:500]}...")

    # Check if API responded with an error
    if "<success>No</success>" in content:
        error_message = ET.fromstring(content).find(".//message").text
        log_messages.append(f"❌ API Rejection: {error_message}")
        return None, log_messages

    # Parse XML
    root = ET.fromstring(content)
    data = []

    for listing in root.findall('.//listing'):
        item = {}

        # Extract required fields and rename them to match Wander’s format
        item["listing_id"] = listing.findtext("listingid")
        item["name"] = listing.findtext("company")
        item["description"] = listing.findtext("description")
        item["longitude"] = listing.findtext("longitude")
        item["latitude"] = listing.findtext("latitude")

        # Construct full address (address1, city, state, zip)
        address1 = listing.findtext("address1", "").strip()
        city = listing.findtext("city", "").strip()
        state = listing.findtext("state", "").strip()
        zip_code = listing.findtext("zip", "").strip()

        # Ensure address formatting is correct
        address_parts = [part for part in [
            address1, city, state, zip_code] if part]
        item["address"] = ", ".join(address_parts) if address_parts else None

        item["website"] = listing.findtext("website")
        item["phone"] = listing.findtext("phone")

        # Extract categories and subcategories separately
        category_names = []
        subcategory_names = []
        for add_cat in listing.findall('.//additionalcategory'):
            category_name = add_cat.findtext("categoryname")
            subcategory_name = add_cat.findtext("subcategoryname")
            if category_name:
                category_names.append(category_name)
            if subcategory_name:
                subcategory_names.append(subcategory_name)
        item["categories"] = ", ".join(filter(None, category_names))
        item["sub_categories"] = ", ".join(filter(None, subcategory_names))

        # Extract media (only URLs)
        media_urls = [
            media.findtext('mediafile')
            for media in listing.findall('.//media')
            if media.findtext('mediafile')
        ]
        item["media_urls"] = ", ".join(media_urls)

        # Extract amenities (only if value is "Yes")
        amenities = [
            amenity.findtext('name')
            for amenity in listing.findall('.//amenity')
            if amenity.findtext('value') and amenity.findtext('value').strip().lower() == "yes"
        ]
        item["amenities"] = ", ".join(filter(None, amenities))

        # Collect other properties in a JSON format
        other_properties = {}
        for child in listing:
            if child.tag not in ["listingid", "company", "description", "longitude", "latitude",
                                 "address1", "city", "state", "zip", "website", "phone"] and len(child) == 0:
                other_properties[child.tag] = child.text.strip(
                ) if child.text else None

        item["other_properties_json"] = json.dumps(
            other_properties, ensure_ascii=False)

        data.append(item)

    # Convert to DataFrame
    df = pd.DataFrame(data)

    # Ensure required columns exist, filling missing ones with empty strings
    required_columns = ["listing_id", "name", "description", "longitude", "latitude", "address",
                        "categories", "sub_categories", "amenities", "website", "phone", "media_urls", "other_properties_json"]
    for col in required_columns:
        if col not in df:
            df[col] = ""

    # Keep only required columns
    df = df[required_columns]

    log_messages.append(
        f"✅ Extracted {len(df)} POIs in Wander’s pre-processing format with full addresses.")

    return df, log_messages


# Define schema mappings for each API source
SCHEMA_MAPPINGS = {
    "White Mountains": {
        "listing_id": "listingid",
        "name": "company",
        "description": "description",
        "longitude": "longitude",
        "latitude": "latitude",
        "address": "address1",
        "categories": "categoryname",
        "sub_categories": "subcategoryname",
        "amenities": "amenitytabs",
        "website": "website",
        "phone": "phone",
        "media_urls": "listingmedia"
    },
    "Raleigh/Wake County": {
        "listing_id": "LISTINGID",
        "name": "COMPANY",
        "description": "DESCRIPTION",
        "longitude": "LONGITUDE",
        "latitude": "LATITUDE",
        "address": "ADDR1",
        "categories": "CATNAME",
        "sub_categories": "SUBCATNAME",
        "website": "WEBURL",
        "phone": "PHONE",
        "media_urls": "IMGPATH"
    }
}

# Hardcoded Wander Pre-Processing Format Columns
WANDER_COLUMNS = [
    "listing_id", "name", "description", "longitude", "latitude", "address",
    "categories", "sub_categories", "amenities", "website", "phone", "media_urls", "other_properties_json"
]


def fetch_raleigh_pois():
    """Fetch POIs from Raleigh/Wake County Simpleview API with pagination support and detailed logging."""
    log_messages = []
    log_messages.append(
        "🔍 Fetching POIs from Raleigh/Wake County Simpleview API...")

    url = "https://raleigh.simpleviewcrm.com/webapi/listings/xml/listings.cfm"
    params = {
        'USERNAME': "WonderMaps_CRMapi",
        'PASSWORD': "api^m@ps1",
        'ACTION': "getListings",
        'PAGENUM': 1,
        'PAGESIZE': 50
    }

    all_listings = []
    total_pages = None
    total_time = 0  # Track total API fetch time

    progress_bar = st.progress(0)
    progress_text = st.empty()

    while True:
        start_time = time.time()  # ✅ Track request time
        response = requests.post(url, data=params)
        elapsed_time = time.time() - start_time  # ✅ Measure time taken
        total_time += elapsed_time

        log_messages.append(
            f"📡 Request for Page {params['PAGENUM']} took {elapsed_time:.2f} seconds.")

        if response.status_code == 200:
            root = ET.fromstring(response.text)

            # Retrieve total results count and calculate total pages
            if total_pages is None:
                total_results = int(root.find(".//RESULTS").text)
                total_pages = (total_results // params['PAGESIZE']) + 1
                log_messages.append(
                    f"📊 Total Results: {total_results}, Total Pages: {total_pages}")

            # Iterate over each LISTING element
            for listing in root.findall(".//LISTING"):
                listing_data = {child.tag: child.text for child in listing}
                all_listings.append(listing_data)

            progress_text.text(
                f"📥 Fetching page {params['PAGENUM']} of {total_pages}... (Time: {elapsed_time:.2f}s)")
            progress_bar.progress(params['PAGENUM'] / total_pages)

            if params['PAGENUM'] >= total_pages:
                break
            params['PAGENUM'] += 1
        else:
            log_messages.append(
                f"❌ Error querying API: {response.status_code}")
            return None, log_messages

    df = pd.DataFrame(all_listings)
    log_messages.append(f"✅ Extracted {len(df)} POIs from Raleigh API.")
    log_messages.append(f"⏳ Total Time Taken: {total_time:.2f} seconds.")
    return df, log_messages


def transform_to_wander_format(df, api_source):
    """Transform fetched POI data into the Wander Pre-Processing format with logs."""
    log_messages = []
    try:
        if df is None or df.empty:
            raise ValueError("No data available for transformation.")

        log_messages.append(
            f"🔄 Transforming data using {api_source} schema...")
        transformed_df = pd.DataFrame(columns=WANDER_COLUMNS)

        schema = SCHEMA_MAPPINGS.get(api_source, {})
        mapped_columns = set(schema.values())

        for wander_col, source_col in schema.items():
            if source_col in df.columns:
                transformed_df[wander_col] = df[source_col]

        # Capture unmapped columns as JSON
        other_properties = []
        for _, row in df.iterrows():
            extra_data = {col: row[col]
                          for col in df.columns if col not in mapped_columns}
            other_properties.append(json.dumps(extra_data))

        transformed_df["other_properties_json"] = other_properties

        log_messages.append(
            f"✅ Transformation complete. {len(transformed_df)} POIs processed.")
        return transformed_df, log_messages
    except Exception as e:
        log_messages.append(f"❌ Transformation failed: {str(e)}")
        return None, log_messages

# 🎯 **Streamlit Page**


def get_simpleview_pois_page():
    st.title("Fetch POIs from Simpleview API")
    st.subheader("Get POIs from Simpleview API and output pois in Wander's Pre-Processing Format: https://docs.google.com/spreadsheets/d/1DOwsbV-bmOe4am6d_y5mRddFWVomJ74TWje0NInm4bk/edit?usp=sharing")

    # Predefined API connections
    predefined_apis = {
        "White Mountains": {
            "api_key": "083075F3-825C-4F89-9C612632C94802AC",
            "api_url": "http://cs.simpleviewinc.com/feeds/listings.cfm?apikey={api_key}"
        },
        "Raleigh/Wake County": {}  # No API key needed for Raleigh
    }

    # User selection
    option = st.selectbox("Choose API Connection or Enter Manually", [
                          "Select..."] + list(predefined_apis.keys()) + ["Enter Manually"])

    api_key = ""
    api_url = ""
    if option in predefined_apis:
        if option == "Raleigh/Wake County":
            api_key = None  # No API key required
        else:
            api_key = predefined_apis[option]["api_key"]
            api_url = predefined_apis[option]["api_url"]
    elif option == "Enter Manually":
        api_key = st.text_input("Enter Simpleview API Key:")
        api_url = st.text_input("Enter Simpleview API URL:")

    if "df" not in st.session_state:
        st.session_state.df = None

    if st.button("Fetch POIs"):
        if option == "Raleigh/Wake County":
            df, log_messages = fetch_raleigh_pois()
        else:
            df, log_messages = fetch_simpleview_pois(api_key, api_url)

        if df is not None and not df.empty:
            st.session_state.df = df
            st.success(f"✅ Successfully fetched {len(df)} POIs.")
            st.write(df)

            csv_data = df.to_csv(index=False)
            st.download_button("📥 Download CSV", data=csv_data,
                               file_name="simpleview_pois.csv", mime="text/csv")

        with st.expander("🔎 Debug Logs"):
            for log in log_messages:
                st.write(log)

    if st.session_state.df is not None and not st.session_state.df.empty:
        if st.button("Transform to Wander Format"):
            transformed_df, transform_logs = transform_to_wander_format(
                st.session_state.df, option)
            if transformed_df is not None and not transformed_df.empty:
                st.success(
                    "✅ Successfully transformed POIs into Wander Pre-Processing format.")
                st.write(transformed_df)

                transformed_csv_data = transformed_df.to_csv(index=False)
                st.download_button("📥 Download Transformed CSV", data=transformed_csv_data,
                                   file_name="wander_preprocessing_pois.csv", mime="text/csv")

            with st.expander("🔎 Transformation Logs"):
                for log in transform_logs:
                    st.write(log)
