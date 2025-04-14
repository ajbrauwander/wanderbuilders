import streamlit as st
import pandas as pd

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

# 🔹 Streamlit Page for Extracting Categories


def get_categories_page():
    st.title("Extract Categories from POI Data")
    uploaded_file = st.file_uploader(
        "Upload CSV in Pre-Processing Format", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        is_valid, message = validate_csv(df)
        st.markdown(message, unsafe_allow_html=True)

        if is_valid and st.button("Extract Categories"):
            with st.spinner("Extracting categories and subcategories..."):
                category_data = extract_categories(df)
                st.success(
                    "✅ Extraction complete! Download category CSV below.")

                # Display extracted categories and subcategories as tables
                st.subheader("Unique Categories and Subcategories")
                st.dataframe(category_data)

                csv_data = category_data.to_csv(index=False)
                st.download_button("📥 Download Categories CSV", data=csv_data,
                                   file_name="categories_extracted.csv", mime="text/csv")

# 🔹 Function to extract unique categories and subcategories


def extract_categories(df):
    """Extract unique categories and subcategories from POI data and sort them alphabetically."""
    category_list = []

    for _, row in df.iterrows():
        categories = str(row["categories"]).split(",")
        sub_categories = str(row["sub_categories"]).split(",")

        for cat, sub_cat in zip(categories, sub_categories):
            category_list.append(
                {"Category": cat.strip(), "Subcategory": sub_cat.strip()})

    category_df = pd.DataFrame(category_list).drop_duplicates(
    ).sort_values(by=["Category"]).reset_index(drop=True)
    return category_df
