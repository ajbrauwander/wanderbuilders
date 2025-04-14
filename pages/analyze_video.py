import time
from google.cloud import videointelligence, bigquery, firestore
import streamlit as st
import json
import tempfile
from google.cloud import storage
from google.oauth2 import service_account
import pandas as pd
import os
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI

# Load Google Cloud credentials
service_account_str = st.secrets["gcp"]["service_account_json"]

# Initialize OpenAI Client
openai_api_key = st.secrets["openai"]["api_key"]
openai_client = OpenAI(api_key=openai_api_key)

# Parse JSON
try:
    service_account_info = json.loads(service_account_str)
except json.JSONDecodeError as e:
    st.error(f"❌ JSON decoding error: {e}")
    st.stop()

# Initialize Google Cloud Clients
credentials = service_account.Credentials.from_service_account_info(
    service_account_info)
storage_client = storage.Client(credentials=credentials)
video_client = videointelligence.VideoIntelligenceServiceClient(
    credentials=credentials)
bigquery_client = bigquery.Client(credentials=credentials)
firestore_client = firestore.Client(credentials=credentials)

# Initialize Pinecone with API Key
pc = Pinecone(api_key=st.secrets["pinecone"]["api_key"])

# Define index name and embedding dimension
INDEX_NAME = "video-metadata"
EMBEDDING_DIM = 3072
DATASET_NAME = "video_analysis_aj_test"
TABLE_NAME = "video_metadata"

# Ensure Pinecone index exists
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

# Connect to Pinecone index
pinecone_index = pc.Index(INDEX_NAME)

# ✅ Function with Execution Timing & Logging


def log_time(func):
    """Decorator for logging execution time of functions."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        st.write(f"⏳ {func.__name__} started...")
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = round(end_time - start_time, 2)
        st.write(f"✅ {func.__name__} completed in {execution_time} seconds.")
        return result
    return wrapper

# ✅ Upload to GCS


@log_time
def upload_to_gcs(file_path, bucket_name, destination_blob_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(file_path)
    return f"gs://{bucket_name}/{destination_blob_name}"

# ✅ Analyze Video


@log_time
def analyze_video_separately(gcs_uri):
    """Processes labels, objects, and transcription separately."""
    def process_feature(feature, video_context=None):
        try:
            request = {"features": [feature], "input_uri": gcs_uri}
            if video_context:
                request["video_context"] = video_context
            operation = video_client.annotate_video(request=request)
            result = operation.result(timeout=900)
            return json.loads(result.annotation_results[0].__class__.to_json(result.annotation_results[0]))
        except Exception as e:
            st.error(f"❌ Error processing {feature.name}: {e}")
            return {}

    label_response = process_feature(videointelligence.Feature.LABEL_DETECTION)
    labels = label_response.get(
        "segmentLabelAnnotations", []) + label_response.get("frameLabelAnnotations", [])
    label_metadata = [{"description": label["entity"]["description"], "confidence": round(
        label.get("confidence", 0) * 100, 2)} for label in labels if "entity" in label]

    object_response = process_feature(
        videointelligence.Feature.OBJECT_TRACKING)
    objects = object_response.get("objectAnnotations", [])
    object_metadata = [{"description": obj["entity"]["description"], "confidence": round(
        obj.get("confidence", 0) * 100, 2)} for obj in objects if "entity" in obj]

    transcription_response = process_feature(
        videointelligence.Feature.SPEECH_TRANSCRIPTION)
    transcriptions = transcription_response.get("speechTranscriptions", [])
    transcription_text = "\n".join([alt["transcript"] for trans in transcriptions for alt in trans.get(
        "alternatives", []) if alt["transcript"].strip()])

    return label_metadata, object_metadata, transcription_text

# ✅ Store Data in BigQuery


@log_time
def store_in_bigquery(video_id, label_metadata, object_metadata, transcription_text, embedding, description=""):
    dataset_ref = bigquery.DatasetReference(
        bigquery_client.project, DATASET_NAME)
    table_ref = bigquery.TableReference(dataset_ref, TABLE_NAME)

    rows_to_insert = [{
        "video_id": video_id,
        "labels": [l["description"] for l in label_metadata],
        "objects": [o["description"] for o in object_metadata],
        "description": description,  # ✅ Store user input
        "transcription": transcription_text,
        "embedding": embedding,
    }]

    errors = bigquery_client.insert_rows_json(table_ref, rows_to_insert)
    if errors:
        st.error(f"❌ Failed to insert into BigQuery: {errors}")
    else:
        st.success(f"✅ Data stored successfully in BigQuery for {video_id}")

# ✅ Store Embeddings


@log_time
def store_embeddings(video_id, filename, label_metadata, object_metadata, transcription_text, description, model="text-embedding-3-large"):
    """Converts metadata into embeddings and stores in Pinecone."""

    embedding_input = f"""
    Labels: {', '.join([l['description'] for l in label_metadata])}
    Objects: {', '.join([o['description'] for o in object_metadata])}
    Transcription: {transcription_text}
    Description: {description}
    """

    # Generate Embedding
    try:
        response = openai_client.embeddings.create(
            model=model, input=embedding_input)
        embedding = response.data[0].embedding
    except Exception as e:
        st.error(f"❌ Error generating embedding: {e}")
        return None

    # ✅ Debug Log: Check Embedding
    st.write(
        f"🔹 Generated Embedding for {video_id}: {embedding[:5]}... (truncated)")
    print(f"[LOG] Generated Embedding: {embedding[:5]}... (truncated)")

    # ✅ Convert Metadata for Pinecone (Ensure proper format)
    metadata = {
        "filename": filename,  # ✅ Store full filename
        "labels": [l["description"] for l in label_metadata],
        "objects": [o["description"] for o in object_metadata],
        "transcription": transcription_text,
        "description": description
    }

    # ✅ Debug Log: Metadata Before Upsert
    st.write(f"🔹 Metadata for {video_id}: {metadata}")
    print(f"[LOG] Metadata for Pinecone: {metadata}")

    # ✅ Check if Pinecone Index Exists
    if INDEX_NAME not in pc.list_indexes().names():
        st.error(
            f"❌ Pinecone index '{INDEX_NAME}' not found. Check your Pinecone setup.")
        return None

    try:
        # ✅ Ensure Metadata Values Are Strings or Numbers
        formatted_metadata = {k: str(v) if isinstance(
            v, list) else v for k, v in metadata.items()}

        # ✅ Debug Log: Upsert Call
        st.write(f"⏳ Storing Embeddings in Pinecone for {video_id}...")
        pinecone_index.upsert([(video_id, embedding, formatted_metadata)])
        st.success(f"✅ Embeddings stored in Pinecone for {video_id}")
        return embedding

    except Exception as e:
        st.error(f"❌ Error storing embeddings in Pinecone: {e}")
        print(f"[ERROR] Pinecone Upsert Error: {e}")
        return None

# ✅ Main Function


def video_analysis_page():
    st.title("📽️ Video Analysis & Storage")

    uploaded_file = st.file_uploader(
        "Upload a video file", type=["mp4", "mov", "avi"])
    video_description = st.text_area(
        "Add a description for this video (optional)", "")

    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False) as temp_video:
            temp_video.write(uploaded_file.read())
            temp_video_path = temp_video.name

        st.video(temp_video_path)

        if st.button("Analyze & Store Video"):
            with st.spinner("Processing..."):
                try:
                    filename = uploaded_file.name  # ✅ Store full filename
                    video_id = filename.split('.')[0]
                    bucket_name = "wander_video_content"
                    gcs_uri = upload_to_gcs(
                        temp_video_path, bucket_name, filename)

                    label_metadata, object_metadata, transcription_text = analyze_video_separately(
                        gcs_uri)

                    # ✅ Pass video_description to store_embeddings()
                    embedding = store_embeddings(
                        video_id, filename, label_metadata, object_metadata, transcription_text, video_description
                    )

                    store_in_bigquery(video_id, label_metadata, object_metadata,
                                      transcription_text, embedding, video_description)

                    st.success("✅ Video processed and stored successfully!")
                except Exception as e:
                    st.error(f"❌ An unexpected error occurred: {e}")
