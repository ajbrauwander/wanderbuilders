import streamlit as st
import requests
import base64
import pandas as pd
import ast

import difflib

# ---------------------------
# Wild Apricot API Functions
# ---------------------------


def fuzzy_match(a, b):
    return difflib.SequenceMatcher(None, str(a), str(b)).ratio() * 100


def find_best_match(wild_poi, pois_df):
    best_score = 0
    best_index = None

    for idx, row in pois_df.iterrows():
        score = 0

        if 'name' in wild_poi and 'name' in row:
            score = max(score, fuzzy_match(wild_poi['name'], row['name']))

        if 'address' in wild_poi and 'address' in row:
            score = max(score, fuzzy_match(
                wild_poi['address'], row['address']))

        if 'website' in wild_poi and 'website' in row:
            score = max(score, fuzzy_match(
                wild_poi['website'], row['website']))

        if 'phone' in wild_poi and 'phone' in row:
            score = max(score, fuzzy_match(wild_poi['phone'], row['phone']))

        if score > best_score:
            best_score = score
            best_index = idx

    return best_index, best_score


def authenticate_wildapricot(api_key):
    log_messages = ["🔐 Authenticating with Wild Apricot API..."]
    auth_url = "https://oauth.wildapricot.org/auth/token"
    auth_string = f"APIKEY:{api_key}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_encoded}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "client_credentials",
        "scope": "auto",
        "obtain_refresh_token": "true"
    }

    response = requests.post(auth_url, headers=headers, data=payload)
    log_messages.append(f"📡 Auth Status Code: {response.status_code}")

    if response.status_code == 200:
        access_token = response.json().get("access_token")
        log_messages.append("✅ Access token retrieved.")
        return access_token, log_messages
    else:
        log_messages.append(
            f"❌ Auth failed: {response.status_code}, {response.text}")
        return None, log_messages


def fetch_account_id(api_base_url, headers):
    response = requests.get(f"{api_base_url}/accounts", headers=headers)
    if response.status_code == 200:
        return response.json()[0]["Id"], None
    return None, f"❌ Failed to fetch account ID: {response.status_code}, {response.text}"


def fetch_contacts(api_base_url, account_id, headers, log_each_page=False):
    log_messages = []
    contacts_endpoint = f"{api_base_url}/accounts/{account_id}/contacts"

    # Start pagination using manual $skip
    skip = 0
    page_number = 1
    total_fetched = 0
    all_contacts = []

    while True:
        params = {
            "$async": "false",
            "$top": 100,
            "$skip": skip,
            "$filter": "IsArchived eq false"
        }

        response = requests.get(
            contacts_endpoint, headers=headers, params=params)
        log_messages.append(f"📄 Fetching page {page_number} with $skip={skip}")

        if response.status_code == 200:
            data = response.json()
            contacts = data.get("Contacts", [])
            count = len(contacts)
            all_contacts.extend(contacts)
            total_fetched += count

            log_messages.append(f"✅ Page {page_number}: {count} contacts")

            if count < 100:
                log_messages.append("🔚 No more contacts to fetch.")
                break  # Last page reached

            skip += 100
            page_number += 1
        else:
            log_messages.append(
                f"❌ Failed to fetch contacts: {response.status_code}, {response.text}")
            break

    log_messages.append(f"🎯 Total contacts fetched: {total_fetched}")
    return all_contacts, log_messages


# ---------------------------
# Data Processing Functions
# ---------------------------

def flatten_field_values(contact):
    field_values = contact.get("FieldValues", [])
    flat_fields = {field["FieldName"]: field["Value"]
                   for field in field_values}
    contact.update(flat_fields)
    contact.pop("FieldValues", None)
    return contact


def process_categories(contact):
    categories = contact.get("Categories", [])
    if isinstance(categories, str):
        try:
            categories = ast.literal_eval(categories)
        except (ValueError, SyntaxError):
            categories = []
    category_labels = [cat.get("Label", "")
                       for cat in categories if cat.get("Label")]
    contact["Categories"] = ", ".join(category_labels)
    return category_labels


def process_contacts(contacts):
    unique_categories = set()
    for contact in contacts:
        flatten_field_values(contact)
        cats = process_categories(contact)
        unique_categories.update(cats)
    df = pd.DataFrame(contacts)
    return df, sorted(unique_categories)


# ---------------------------
# Streamlit Page
# ---------------------------

def get_wildapricot_contacts_page():
    st.title("📇 Fetch Wild Apricot Contacts")
    st.subheader(
        "Authenticate and download full contact list (pagination handled)")

    api_key = st.text_input("🔑 Enter Wild Apricot API Key:", type="password")
    show_page_logs = st.checkbox("🔍 Log each page fetch", value=True)

    if "contacts_df" not in st.session_state:
        st.session_state.contacts_df = None

    if st.button("🚀 Fetch Contacts"):
        api_base_url = "https://api.wildapricot.org/v2.2"

        access_token, auth_logs = authenticate_wildapricot(api_key)
        for msg in auth_logs:
            st.write(msg)

        if access_token:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }

            account_id, error = fetch_account_id(api_base_url, headers)
            if error:
                st.error(error)
                return

            contacts, fetch_logs = fetch_contacts(
                api_base_url, account_id, headers, show_page_logs)
            for msg in fetch_logs:
                st.write(msg)

            if contacts:
                df, unique_categories = process_contacts(contacts)
                st.session_state.contacts_df = df

                st.success(f"✅ Retrieved {len(df)} contacts.")
                st.write(df.head())
                st.write(f"📚 Unique Categories: {unique_categories}")

                csv_data = df.to_csv(index=False)
                st.download_button("📥 Download Contacts CSV", data=csv_data,
                                   file_name="wild_apricot_contacts.csv", mime="text/csv")
            else:
                st.warning("⚠️ No contacts returned.")

        # Upload and compare
    # Upload and compare
    st.markdown("---")
    st.header("📊 Compare with Existing POIs")
    uploaded_csv = st.file_uploader(
        "Upload POIs CSV for comparison", type="csv")

    if uploaded_csv and st.session_state.contacts_df is not None:
        pois_df = pd.read_csv(uploaded_csv)
        wild_df = st.session_state.contacts_df.copy()

        # Normalize columns
        pois_df.columns = [col.strip().lower().replace(" ", "_")
                           for col in pois_df.columns]
        wild_df.columns = [col.strip().lower().replace(" ", "_")
                           for col in wild_df.columns]

        wild_df['name'] = wild_df['organization']
        wild_df['address'] = wild_df[['address1', 'city', 'state', 'zip']].fillna(
            '').agg(', '.join, axis=1).str.strip(', ')

        # Ensure optional column exists
        if 'hours_of_operation' not in wild_df.columns:
            wild_df['hours_of_operation'] = ''

        # Fields to compare for changes
        compare_fields = ['description', 'website', 'phone',
                          'name', 'membershipenabled', 'hours_of_operation']

        new_or_updated = []
        unmatched = []

        for _, wild_row in wild_df.iterrows():
            match_idx, score = find_best_match(wild_row, pois_df)
            if score >= 85 and match_idx is not None:
                pois_row = pois_df.loc[match_idx]
                changes = {
                    col: (wild_row.get(col, ''), pois_row.get(col, ''))
                    for col in compare_fields
                    if col in wild_row and col in pois_row and str(wild_row[col]).strip() != str(pois_row[col]).strip()
                }

                # Normalize membershipenabled comparison
                if "membershipenabled" in wild_row and str(wild_row["membershipenabled"]).lower() in ["false", "no", "0"]:
                    changes['membershipenabled'] = (
                        wild_row.get("membershipenabled", ""), "True")

                if changes:
                    new_or_updated.append({
                        "wild_apricot_name": wild_row.get("name", ""),
                        "matched_poi_name": pois_row.get("name", ""),
                        "score": round(score, 1),
                        "differences": changes
                    })
            else:
                closest_match = pois_df.loc[match_idx] if match_idx is not None else {
                }
                unmatched.append({
                    "wild_apricot_name": wild_row.get("name", ""),
                    "wild_apricot_address": wild_row.get("address", ""),
                    "wild_apricot_website": wild_row.get("website", ""),
                    "wild_apricot_phone": wild_row.get("phone", ""),
                    "closest_poi_match_name": closest_match.get("name", ""),
                    "closest_score": round(score, 1)
                })

        if new_or_updated:
            st.subheader("📝 POIs with New or Updated Info")
            st.write(pd.DataFrame(new_or_updated))

        if unmatched:
            st.subheader("🆕 Potential New POIs (Unmatched)")
            st.write(pd.DataFrame(unmatched))
