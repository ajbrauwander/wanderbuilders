import streamlit as st
import pandas as pd
import json
from openai import OpenAI

# Load API Key from Streamlit secrets
OPENAI_API_KEY = st.secrets["openai"]["api_key"]
client = OpenAI(api_key=OPENAI_API_KEY)


# Function to process the category mapping CSV
def process_category_mapping(category_mapping_df):
    """Convert the Category Mapping CSV into a dictionary for quick lookup."""
    category_mapping_df["Category Name"] = category_mapping_df["Category Name"].astype(
        str).str.strip()
    category_mapping_df["Category ID"] = category_mapping_df["Category ID"].astype(
        str).str.strip()
    return dict(zip(category_mapping_df["Category Name"], category_mapping_df["Category ID"])), category_mapping_df["Category Name"].tolist()


# Function to find the best category match
def get_best_category(category_names, sub_category_names, title, tag_ids, category_dict, category_names_list):
    """Assign the most specific category based on direct matches and AI inference."""
    matched_category = None

    # Convert inputs to string to avoid NaN issues
    category_names = str(category_names) if pd.notna(category_names) else ""
    sub_category_names = str(sub_category_names) if pd.notna(
        sub_category_names) else ""
    tag_ids = str(tag_ids) if pd.notna(tag_ids) else ""

    # Check if sub-category is a more specific match
    for sub_category in sub_category_names.split(","):
        sub_category = sub_category.strip()
        if sub_category in category_dict:
            matched_category = sub_category
            break  # Prefer the most specific match

    # If no match from sub-category, check main categories
    if not matched_category:
        for category in category_names.split(","):
            category = category.strip()
            if category in category_dict:
                matched_category = category

    # If still no match, use AI to infer the best category
    if not matched_category:
        prompt_text = f"""
        Based on the following information, determine the **most specific** category for this place:
        
        - Place Name: {title}
        - Categories: {category_names}
        - Sub-Categories: {sub_category_names}
        - Tag IDs: {tag_ids}

        Choose **only one** category from this list: {', '.join(category_names_list)}.

        Return only the best category name.
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a classification assistant that selects the most specific category for a place."},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=20,
                temperature=0.7
            )

            # Extract AI response
            ai_suggested_category = response.choices[0].message.content.strip()

            # Validate if AI's suggestion is in the category list
            if ai_suggested_category in category_dict:
                matched_category = ai_suggested_category
                st.write(
                    f"📌 **{title}** - AI Selected Category: {matched_category}")
            else:
                st.warning(
                    f"⚠️ AI suggested an unknown category: {ai_suggested_category}")

        except Exception as e:
            st.warning(f"⚠️ OpenAI API Error: {e}")

    return category_dict.get(matched_category, "No Match Found") if matched_category else "No Match Found"


# Streamlit UI
def assign_categories_to_pois_page():
    st.title("🏷️ Assign Most Specific Categories to POIs")

    # File uploaders
    category_file = st.file_uploader(
        "📂 Upload Category Mapping CSV", type=["csv"])
    poi_file = st.file_uploader("📂 Upload POI CSV", type=["csv"])

    if category_file and poi_file:
        category_mapping_df = pd.read_csv(category_file)
        poi_df = pd.read_csv(poi_file)

        # Process category mapping
        category_dict, category_names_list = process_category_mapping(
            category_mapping_df)

        # Validate POI CSV columns
        required_poi_columns = ["listing_id", "name", "description", "longitude", "latitude", "address",
                                "categories", "sub_categories", "amenities", "website", "phone", "media_urls",
                                "region_names", "other_properties_json", "Tag IDs"]
        missing_columns = [
            col for col in required_poi_columns if col not in poi_df.columns]

        if missing_columns:
            st.error(
                f"❌ Missing columns in POI CSV: {', '.join(missing_columns)}")
            return

        # Start category assignment process
        if st.button("🚀 Assign Categories"):
            with st.spinner("Processing..."):
                poi_df["Best Category ID"] = poi_df.apply(
                    lambda row: get_best_category(row["categories"], row["sub_categories"], row["name"],
                                                  row["Tag IDs"], category_dict, category_names_list), axis=1
                )

                # Output results
                st.success("✅ Category Assignment Complete!")

                # Show updated dataframe
                st.write(poi_df)

                # Download updated CSV
                csv_data = poi_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Updated POIs with Best Categories",
                    data=csv_data,
                    file_name="pois_with_best_categories.csv",
                    mime="text/csv"
                )
