import streamlit as st
import pandas as pd
import requests

# API Endpoint
API_URL = "https://wander-api-dot-wander-production-308019.uc.r.appspot.com/api/places-of-interest/items/all"

# Function to fetch Wander Tags from API


def fetch_wander_tags():
    """Fetch all Wander tags and return structured data along with logs."""
    log_messages = []
    log_messages.append("🔍 Fetching all Wander tags...")

    response = requests.get(API_URL)
    log_messages.append(f"📡 Response Status Code: {response.status_code}")

    if response.status_code != 200:
        log_messages.append(
            f"❌ API Error: {response.status_code} - {response.text}")
        return None, log_messages

    data = response.json()
    log_messages.append(
        f"✅ Successfully retrieved {len(data)} tag categories.")

    # Process hierarchical structure
    categories, subcategories, fields, field_options = [], [], [], []

    for category in data:
        cat_name = category.get("name", "Unknown")
        cat_id = category.get("id", "")
        categories.append({"Category Name": cat_name, "Category ID": cat_id})

        for subcat in category.get("types", []):
            subcat_name = subcat.get("name", "Unknown")
            subcat_id = subcat.get("id", "")
            subcategories.append({
                "Category Name": cat_name,
                "Subcategory Name": subcat_name,
                "Subcategory ID": subcat_id
            })

            for field in subcat.get("fields", []):
                field_name = field.get("name", "Unknown")
                field_id = field.get("id", "")
                fields.append({
                    "Category Name": cat_name,
                    "Subcategory Name": subcat_name,
                    "Field Name": field_name,
                    "Field ID": field_id
                })

                for field_option in field.get("field_options", []):
                    field_option_name = field_option.get("name", "Unknown")
                    field_option_id = field_option.get("id", "")
                    field_options.append({
                        "Category Name": cat_name,
                        "Subcategory Name": subcat_name,
                        "Field Name": field_name,
                        "Field Option Name": field_option_name,
                        "Field Option ID": field_option_id
                    })

    return {
        "categories": pd.DataFrame(categories),
        "subcategories": pd.DataFrame(subcategories),
        "fields": pd.DataFrame(fields),
        "field_options": pd.DataFrame(field_options),
    }, log_messages

# 🎯 **Streamlit Page**


def get_wander_tags_page():
    st.title("Fetch Wander Tags")

    # Initialize session state to store fetched data
    if "wander_data" not in st.session_state:
        st.session_state.wander_data = None
        st.session_state.log_messages = []

    # Fetch Data on Button Click
    if st.button("Fetch Wander Tags"):
        structured_data, log_messages = fetch_wander_tags()
        if structured_data:
            st.session_state.wander_data = structured_data
            st.session_state.log_messages = log_messages
            st.success(
                f"✅ Successfully retrieved {len(structured_data['categories'])} categories.")

    # Ensure data persists between reruns
    if st.session_state.wander_data:
        structured_data = st.session_state.wander_data

        # Search Bar
        search_query = st.text_input(
            "🔎 Search tags, subcategories, or fields:")

        # Display structured hierarchy
        for _, cat_row in structured_data["categories"].iterrows():
            cat_name = cat_row["Category Name"]
            with st.expander(f"📂 {cat_name}"):
                # Filter subcategories
                filtered_subcats = structured_data["subcategories"][structured_data["subcategories"]
                                                                    ["Category Name"] == cat_name]
                if search_query:
                    filtered_subcats = filtered_subcats[filtered_subcats["Subcategory Name"].str.contains(
                        search_query, case=False, na=False)]

                if not filtered_subcats.empty:
                    st.write("📋 **Subcategories:**")
                    st.dataframe(filtered_subcats)

                # Filter fields
                filtered_fields = structured_data["fields"][structured_data["fields"]
                                                            ["Category Name"] == cat_name]
                if search_query:
                    filtered_fields = filtered_fields[filtered_fields["Field Name"].str.contains(
                        search_query, case=False, na=False)]

                if not filtered_fields.empty:
                    st.write("📋 **Fields:**")
                    st.dataframe(filtered_fields)

                # Filter field options
                filtered_field_options = structured_data["field_options"][
                    structured_data["field_options"]["Category Name"] == cat_name]
                if search_query:
                    filtered_field_options = filtered_field_options[filtered_field_options["Field Option Name"].str.contains(
                        search_query, case=False, na=False)]

                if not filtered_field_options.empty:
                    st.write("📋 **Field Options:**")
                    st.dataframe(filtered_field_options)

        # Downloadable CSVs
        st.write("📥 **Download Structured Data**")
        for key, df in structured_data.items():
            csv_data = df.to_csv(index=False)
            st.download_button(f"📥 Download {key.replace('_', ' ').title()}",
                               data=csv_data, file_name=f"{key}.csv", mime="text/csv")

    # 📑 Debug Logs
    with st.expander("🔎 Debug Logs"):
        for log in st.session_state.log_messages:
            st.write(log)
