import streamlit as st
from openai import OpenAI
import pandas as pd
import pinecone
from pinecone import Pinecone
import time

# ✅ Define Google Cloud Storage bucket name
BUCKET_NAME = "wander_video_content"

# ✅ Initialize OpenAI Client
openai_api_key = st.secrets["openai"]["api_key"]
openai_client = OpenAI(api_key=openai_api_key)

# ✅ Initialize Pinecone Client
pinecone_api_key = st.secrets["pinecone"]["api_key"]
pc = Pinecone(api_key=pinecone_api_key)

# ✅ Define Index Name (Ensure it matches your Pinecone index!)
INDEX_NAME = "video-metadata"

# ✅ Connect to Pinecone Index
pinecone_index = pc.Index(INDEX_NAME)

# ✅ Function with Execution Timing & Logging


def log_time(func):
    """Decorator for logging execution time of functions."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        st.write(f"⏳ {func.__name__} started...")
        print(f"[LOG] {func.__name__} started...")
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = round(end_time - start_time, 2)
        st.write(f"✅ {func.__name__} completed in {execution_time} seconds.")
        print(f"[LOG] {func.__name__} completed in {execution_time} seconds.")
        return result
    return wrapper

# ✅ Query Function


@log_time
def search_videos(query, top_k=5):
    """Converts query to embedding, searches Pinecone, and returns matches."""

    # 🔹 Generate Embedding
    response = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=query
    )
    query_embedding = response.data[0].embedding

    # 🔹 Query Pinecone
    search_results = pinecone_index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True  # Retrieve metadata for better display
    )

    # 🔹 Format Results
    results = []
    for match in search_results["matches"]:
        video_id = match["id"]
        score = round(match["score"], 3)  # Similarity score
        metadata = match.get("metadata", {})

        # ✅ Retrieve Filename from metadata
        filename = metadata.get("filename", None)

        # ✅ Construct Video URL dynamically
        video_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}" if filename else "N/A"

        results.append({
            "Video ID": video_id,
            "Similarity Score": score,
            "Labels": metadata.get("labels", "N/A"),
            "Objects": metadata.get("objects", "N/A"),
            "Description": metadata.get("description", "N/A"),
            "Transcription": metadata.get("transcription", "N/A"),
            "Video URL": video_url  # ✅ Use constructed Video URL
        })

    return results

# ✅ Display Results in a Structured Table


def display_results(results):
    """Formats and displays search results in a table, with embedded videos below."""

    if results:
        st.subheader("🔎 Search Results")

        # Convert results into a DataFrame for structured display
        df = pd.DataFrame(results)

        # ✅ Ensure "Video URL" column exists before dropping it from the table
        if "Video URL" in df.columns:
            st.table(df.drop(columns=["Video URL"]))
        else:
            st.table(df)

        # ✅ Embed videos below the table with URLs printed above
        st.subheader("🎬 Matching Videos")
        for result in results:
            st.write(
                f"### {result['Video ID']} (Similarity Score: {result['Similarity Score']})"
            )

            video_url = result.get("Video URL", "N/A")

            if video_url and video_url != "N/A":
                # ✅ Print the video URL above the embedded video
                st.markdown(
                    f"[🔗 **Video URL**]({video_url})", unsafe_allow_html=True
                )
                st.video(video_url)
            else:
                st.warning(f"⚠️ No video available for {result['Video ID']}.")

# ✅ Query Page Function


def query_video_data_page():
    st.title("🔍 Search Video Data")
    st.write("Enter a query to find videos that match your search.")

    # 🔹 Query Input
    query = st.text_input("Enter your search query:")

    # 🔹 Number of Results
    top_k = st.slider("Number of results to return:", 1, 10, 5)

    # 🔹 Search Button
    if st.button("Search"):
        if query.strip():
            with st.spinner("Searching..."):
                results = search_videos(query, top_k)
                display_results(results)
        else:
            st.warning("⚠️ Please enter a query.")
