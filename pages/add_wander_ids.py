import openai
import streamlit as st
import pandas as pd
import requests
import time
import json
from fuzzywuzzy import process
from rapidfuzz import fuzz
import geopy.distance

BARDSTOWN_MAP_ID = "810cf819-eeb0-4ac6-9887-6e5031d575fe"

# Function to fetch Wander POIs


def fetch_bardstown_pois(log_expander):
    BASE_URL = "https://wander-api-209737824514.us-central1.run.app"
    url = f"{BASE_URL}/api/pois/map/{BARDSTOWN_MAP_ID}"

    headers = {"Content-Type": "application/json",
               "Accept": "*/*", "Origin": "https://web.wander-app.com"}
    log_expander.write("🔍 Fetching POIs for Bardstown Wander Map...")

    response = requests.post(url, headers=headers, json={})
    if response.status_code != 200:
        log_expander.write(
            f"❌ API Error: {response.status_code} - {response.text}")
        return None

    pois = []
    for marker in response.json().get("markers", []):
        for feature in marker.get("data", {}).get("features", []):
            properties = feature.get("properties", {})
            coordinates = feature.get("geometry", {}).get(
                "coordinates", [None, None])
            pois.append({
                "Wander ID": properties.get("id", ""),
                "Wander Name": properties.get("name", ""),
                "Latitude": coordinates[1],
                "Longitude": coordinates[0],
                "name_lower": properties.get("name", "").lower()
            })

    df = pd.DataFrame(pois)
    log_expander.write(
        f"✅ Extracted `{len(df)}` POIs from Bardstown Wander Map.")
    return df

# Function to normalize names for better matching


def normalize_name(name):
    return name.lower().replace("llc", "").replace("inc", "").replace("co.", "").replace("&", "and").strip()

# Function to calculate distance between two coordinates


def calculate_distance(coord1, coord2):
    return geopy.distance.geodesic(coord1, coord2).miles

# First-pass fuzzy matching


def match_pois_with_wander_ids(crm_df, wander_df, log_expander, threshold=85):
    log_expander.write("🔄 Performing first-pass matching (one-to-one)...")

    crm_df["name_lower"] = crm_df["Account Name"].astype(
        str).apply(normalize_name)
    wander_df["name_lower"] = wander_df["Wander Name"].astype(
        str).apply(normalize_name)

    best_matches = {}

    for _, wander_row in wander_df.iterrows():
        wander_name = wander_row["name_lower"]
        match_result = process.extractOne(
            wander_name, crm_df["name_lower"], scorer=fuzz.token_set_ratio)

        if match_result and len(match_result) >= 2:
            best_match, score = match_result[:2]
            if score >= threshold:
                matched_crm_row = crm_df[crm_df["name_lower"]
                                         == best_match].iloc[0]
                best_matches[wander_row["Wander ID"]
                             ] = matched_crm_row["Listing ID"]

    crm_df["Wander ID"] = crm_df["Listing ID"].map(lambda x: next(
        (k for k, v in best_matches.items() if v == x), None))
    crm_df["Match Score"] = crm_df["Wander ID"].apply(
        lambda x: 100 if x else 0)
    crm_df["Needs Manual Review"] = crm_df["Wander ID"].isna()

    log_expander.write(
        f"✅ Matched `{crm_df['Wander ID'].notna().sum()}` POIs.")
    log_expander.write(
        f"⚠️ `{crm_df['Wander ID'].isna().sum()}` POIs did not match in first round.")
    return crm_df

# Second-pass matching using distance-based filtering


def second_pass_matching(crm_df, wander_df, log_expander, threshold=80):
    log_expander.write("🔄 Running second-pass matching for unmatched POIs...")
    unmatched_crm = crm_df[crm_df["Wander ID"].isna()]

    for _, crm_row in unmatched_crm.iterrows():
        crm_name = crm_row["name_lower"]
        match_result = process.extractOne(
            crm_name, wander_df["name_lower"], scorer=fuzz.token_sort_ratio)

        if match_result and len(match_result) >= 2:
            best_match, score = match_result[:2]
            if score >= threshold:
                matched_wander_row = wander_df[wander_df["name_lower"]
                                               == best_match].iloc[0]
                distance = calculate_distance(
                    (matched_wander_row["Latitude"],
                     matched_wander_row["Longitude"]),
                    (crm_row["Latitude"], crm_row["Longitude"]
                     ) if "Latitude" in crm_row else (None, None)
                )

                # Apply distance filter
                if distance <= 10:  # Only allow matches within 10 miles
                    crm_df.loc[crm_row.name,
                               "Wander ID"] = matched_wander_row["Wander ID"]
                    crm_df.loc[crm_row.name, "Match Score"] = score
                    crm_df.loc[crm_row.name, "Needs Manual Review"] = False

    log_expander.write(
        f"✅ Additional `{crm_df['Wander ID'].notna().sum()}` POIs matched in second pass.")
    return crm_df

# OpenAI Matching for remaining unmatched entries


def match_using_openai(unmatched_crm_df, wander_df, log_expander):
    log_expander.write(
        "🤖 Using OpenAI API to improve matches for remaining POIs...")

    openai.api_key = "your-api-key-here"  # Ensure API key security

    for index, crm_row in unmatched_crm_df.iterrows():
        prompt_text = f"""
        You are an expert at matching business listings. 
        Find the best match for the following place from the Wander list.

        CRM Business:
        - Name: {crm_row["Account Name"]}
        - Address: {crm_row["Address 1"]}, {crm_row["City"]}

        Wander POI List:
        {wander_df[['Wander Name', 'Latitude', 'Longitude']].to_string(index=False)}

        Return ONLY the name of the best match or "None" if no good match is found.
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt_text}]
            )

            match_result = response["choices"][0]["message"]["content"].strip()

            if match_result and match_result.lower() != "none":
                matched_wander_row = wander_df[wander_df["Wander Name"]
                                               == match_result]
                if not matched_wander_row.empty:
                    wander_id = matched_wander_row.iloc[0]["Wander ID"]
                    unmatched_crm_df.at[index, "Wander ID"] = wander_id
                    unmatched_crm_df.at[index, "Match Score"] = 90
                    unmatched_crm_df.at[index, "Needs Manual Review"] = False
                    log_expander.write(
                        f"✅ Matched {crm_row['Account Name']} → {match_result}")

        except Exception as e:
            log_expander.write(f"❌ OpenAI API error: {str(e)}")

    return unmatched_crm_df

# Streamlit Page


def match_wander_ids_page():
    st.title("Match Wander IDs for Bardstown POIs")
    log_expander = st.expander("🔎 Debug Logs")
    uploaded_file = st.file_uploader(
        "Upload Bardstown Listing Export CSV", type=["csv"])

    if uploaded_file:
        crm_df = pd.read_csv(uploaded_file)
        wander_df = fetch_bardstown_pois(log_expander)

        if wander_df is not None:
            matched_df = match_pois_with_wander_ids(
                crm_df, wander_df, log_expander)
            matched_df = second_pass_matching(
                matched_df, wander_df, log_expander)

            st.success(
                f"✅ Successfully matched `{matched_df['Wander ID'].notna().sum()}` POIs.")
            st.dataframe(matched_df)
            st.download_button("📥 Download Matched POIs CSV", data=matched_df.to_csv(
                index=False), file_name="bardstown_matched_pois.csv", mime="text/csv")
            st.download_button("📥 Download Wander POIs CSV", data=wander_df.to_csv(
                index=False), file_name="bardstown_wander_pois.csv", mime="text/csv")
