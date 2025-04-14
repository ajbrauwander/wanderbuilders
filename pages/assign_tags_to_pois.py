import streamlit as st
import pandas as pd
import json
from openai import OpenAI
import re

# Load API Key from Streamlit secrets
OPENAI_API_KEY = st.secrets["openai"]["api_key"]
client = OpenAI(api_key=OPENAI_API_KEY)

# Function to process the tag mapping CSV


def process_tag_mapping(tag_mapping_df):
    """Convert the Tag Mapping CSV into a dictionary for quick lookup."""
    tag_mapping_df["Tag Name"] = tag_mapping_df["Tag Name"].astype(
        str).str.strip()
    tag_mapping_df["Tag ID"] = tag_mapping_df["Tag ID"].astype(str).str.strip()
    return dict(zip(tag_mapping_df["Tag Name"], tag_mapping_df["Tag ID"])), tag_mapping_df["Tag Name"].tolist()

# Function to find matching Tag IDs


def get_tag_ids(category_names, region_names, title, tag_dict, tag_names):
    """Assign tags based on direct matches and AI inference."""
    matched_tag_ids = set()

    # Ensure non-empty string values
    category_names = str(category_names) if pd.notna(category_names) else ""
    region_names = str(region_names) if pd.notna(region_names) else ""

    # Direct matches from categories
    for category in category_names.split(","):
        category = category.strip()
        if category in tag_dict:
            matched_tag_ids.add(tag_dict[category])

    # Direct matches from regions
    for region in region_names.split(","):
        region = region.strip()
        if region in tag_dict:
            matched_tag_ids.add(tag_dict[region])

    # AI-based tag inference
    if not matched_tag_ids:  # Only use AI if no direct matches found
        prompt_text = f"""
        Based on the following information, determine the most relevant tags a user would use to search for this place of interest:
        Place Name: {title}
        
        Categories: {category_names}
        
        Region: {region_names}

        List of tags to choose from: {', '.join(tag_names)}

        Return a comma-separated list of only the most relevant tags.
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a classification assistant that tags places based on descriptions, categories, and regions."},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=50,
                temperature=0.7
            )

            # Extract AI response
            ai_suggested_tags = response.choices[0].message.content.strip()
            suggested_tags = [tag.strip() for tag in ai_suggested_tags.split(
                ",") if tag.strip() in tag_dict]

            # Add AI suggestions to tag set
            matched_tag_ids.update(tag_dict[tag] for tag in suggested_tags)

            # Log AI response
            st.write(
                f"📌 **{title}** - AI Suggested Tags: {', '.join(suggested_tags)}")

        except Exception as e:
            st.warning(f"⚠️ OpenAI API Error: {e}")

    return ", ".join(matched_tag_ids) if matched_tag_ids else "No Tags Found"


def assign_tags_to_pois_page():
    st.title("🔖 Assign Tags to POIs")

    # File uploaders
    poi_file = st.file_uploader("📂 Upload POI CSV", type=["csv"])
    tag_file = st.file_uploader("📂 Upload Tag Mapping CSV", type=["csv"])

    if poi_file and tag_file:
        poi_df = pd.read_csv(poi_file)
        tag_mapping_df = pd.read_csv(tag_file)

        # Process tag mapping
        tag_dict, tag_names = process_tag_mapping(tag_mapping_df)

        # Validate CSV columns
        required_poi_columns = ["listing_id", "name", "description", "longitude", "latitude", "address",
                                "categories", "sub_categories", "region_names"]
        missing_columns = [
            col for col in required_poi_columns if col not in poi_df.columns]

        if missing_columns:
            st.error(
                f"❌ Missing columns in POI CSV: {', '.join(missing_columns)}")
            return

        # Start tagging process
        if st.button("🚀 Assign Tags"):
            with st.spinner("Processing..."):
                poi_df["Tag IDs"] = poi_df.apply(
                    lambda row: get_tag_ids(row["categories"], row["region_names"], row["name"], tag_dict, tag_names), axis=1
                )

                # Output results
                st.success("✅ Tagging Complete!")

                # Show updated dataframe
                st.write(poi_df)

                # Download updated CSV
                csv_data = poi_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Updated POIs with Tags",
                    data=csv_data,
                    file_name="pois_with_tags.csv",
                    mime="text/csv"
                )
