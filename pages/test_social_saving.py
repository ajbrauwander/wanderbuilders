

import streamlit as st
import requests
import json
import time
import firebase_admin
from firebase_admin import credentials, db
from firebase_admin import initialize_app

# Firebase configuration
FIREBASE_CREDENTIALS = {
    "type": "service_account",
    "project_id": "strange-reducer-305822",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCwQpEm9XmiYND5\ncJP1PPn8LQ6Sq4OETj/F00IZ1IIz3QprJ6RS6SJxWVkmCltRQPcIiklETFpdeQdv\nQK3TugS8CdHkuW+nwGmFckNiUh1c8qGP9+EC6LrBfAHo394OhbbEb2nermnNJXPG\nuwzPHPZ6rOf+RJ3YLBpnHS50pbNtnlOwCBJeNXIRLnyGf47ozM2LAcQcD1GZsNaS\nJHcrv52qnZZt/t5Sbyc1JsVoSHeXe6SfWgWPJNOdxXw1miLQHj0TQWJku/WsVxz1\nPC5L5nx0UrQM04Ku9yqk70+xlwmwClC+90Ad/kvIprTGA673aQcPpXSanS0xZDAo\nfp16zOs9AgMBAAECggEAJF9YPMXjN9LqzM6iebT/kT5rB3FFToQnPNd/iH0F8VXn\n1Hz1t/ZMGT/q2aLBfV7+m1COFf37l9Zl5lteg5aba4JLQfvSQre+Dr+pkByJ2qhn\nFqJ8WHFWOJ8yda/czvpg4OBs5HrxclgMMDJhTkwXwPD1Xs8iE33mZOjssT2QbUoq\natmB3Nb+1G87X2ZjSdvTS4n7WUjhj7Fbdnq0zlMXabMMO9EcfdC9v3qIlKBPCJYa\njCmaZjGv3eK8RJlbyE7GW4dV86ppv1teoCBPOP6KD3DDeqd1xA3zaZycr81dYrfr\nrN1EcCP0+cO4d7P7dR3MzOW2JSLxlB7oStwl5AmegQKBgQDxynHev7SU74ydYPIV\n13IVfRR/yjgbiW2uvtsfOhDpqHT5zbgeGmhfdtv4ulsD99HBjDuvwaEONRhibJE4\nSIQbMQ4MUPP6Q4tgrMyuo10HLJsKE+VuieE0qAEChA6CxaV61guHc846dN9FN+qV\nxIwVtLTjuKrktWLXh7T5XkExaQKBgQC6nkMzueWS8HPqOjCrHLqOHnwXNMLKFHJ+\nrRV9oboag71vccKxs5Ldi7UuXtymHDJr7bYZiSPzJnM2RH+1kmGYyrI11zNShsI7\nuYBlXBraZqHguhrR02Rp/r9jlRNetUqXlGcKQubnWOol0UAvNiu6aL+YUx+Cuonb\nSFdx+7GctQKBgDlZAtkKLxKEHp3VOJXlm7FtEUed9uDRH6qqqd4mL4y738LAAENj\nkA3Uayf7S0sNpDp7wExXaJOuFDKD/Y2T5YFtiR9ys+tPyecMFR/2r0HcWolxXqFx\nInESx+qI18g8iJsx2VovJWLIBYytTn5nN7KOQbkhO6czPlZQYaQjruLBAoGABycp\nzEHD2u38g23Xj7d6LxhcCUesb7J48QIRYM9iIsIJ8MubetQ3POat+ykHrBZImHp0\nEGaBSkCfCeV2P69srj6WthmZjgA8Ua26jigJn3Vvnv2DKafAoY9yJo8APxET2tuF\nV49Y6mUuFGUA4M5ivrJlJaGKA6jCv/T15RiQpkECgYBxX0meuvQoefOTQxqKpy28\niaqh+mljAbfC+aY/HOKGQIboSJzai89moU0ELuFYe9NI8nY79lsnOgla4+GUWzT/\nWz10UWvmsAd+9Lkf+/FLVHHpdxPJ75oOjGzQedPTHmPjK1EeCdw4dGm7B6nqYdE2\n13wCLpFVGc6j387hEhfh0g==\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk-lzc8p@strange-reducer-305822.iam.gserviceaccount.com",
    "client_id": "116595607818088019370",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-lzc8p%40strange-reducer-305822.iam.gserviceaccount.com"
}

FIREBASE_DATABASE_URL = "https://strange-reducer-305822-default-rtdb.firebaseio.com/"


# API configuration
BASE_URL = "http://host.docker.internal:3000"
ENDPOINT = "/api/social-process"
API_URL = f"{BASE_URL}{ENDPOINT}"
HEALTH_URL = f"{BASE_URL}/api/health"

# API headers
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "dd7f2dd2-00fa-4c48-b1b4-7331fbb664c0"  # Replace with actual API key
}

# Initialize Firebase


def init_firebase():
    """Initialize Firebase with credentials"""
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DATABASE_URL
        })


# Initialize Firebase at startup
init_firebase()


def listen_for_completion(process_id, user_id):
    """Listen for process completion using Firebase."""
    st.info("🔄 Waiting for video extraction to complete...")
    status_placeholder = st.empty()

    # Reference to the process status in Firebase
    ref = db.reference(f'social-process/{user_id}/{process_id}')

    def on_status_change(event):
        if event.data:
            status = event.data.get('status')
            url = event.data.get('url')

            if status == 'COMPLETED':
                status_placeholder.success("✅ Extraction completed!")
                if url:
                    st.markdown(f"📺 [Click here to view video]({url})")
                return True
            elif status == 'FAILED':
                status_placeholder.error("❌ Extraction failed")
                return True
            else:
                status_placeholder.info(f"Status: {status}")
                return False

    # Listen for changes
    ref.listen(on_status_change)


def process_social_url(source_url, user_id, source):
    """Modified to use Firebase for status updates."""
    log_messages = []
    log_messages.append(f"🔍 Processing URL: {source_url}")

    if not check_api_health():
        st.error(
            "⚠️ API Server is unreachable. Please ensure the backend is running.")
        return None, log_messages

    payload = {
        "source_url": source_url.strip(),
        "user_id": user_id.strip(),
        "source": source
    }

    try:
        response = requests.post(
            API_URL, json=payload, headers=HEADERS, timeout=10)
        log_messages.append(f"📡 Response Status Code: {response.status_code}")

        if response.status_code == 201:
            process_data = response.json()
            process_id = process_data.get('id')

            if process_id:
                st.info("🔄 Process created, waiting for completion notification...")
                listen_for_completion(process_id, user_id)

            return process_data, log_messages
        else:
            st.error(f"❌ API Error: {response.status_code} - {response.text}")
            return None, log_messages

    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}")
        log_messages.append(f"⚠️ Error: {str(e)}")
        return None, log_messages

# Rest of your code remains the same...


def check_api_health():
    """Check if the API server is reachable and responding with 'ok': true."""
    try:
        response = requests.get(HEALTH_URL, timeout=5)
        st.write(response.json())
        # Ensure the response contains JSON and the "ok" field is true
        if response.status_code == 200:
            health_data = response.json()
            # Returns True only if "ok" is true
            return health_data.get("ok", False)

    except requests.exceptions.ConnectionError:
        return False
    except requests.exceptions.RequestException:
        return False

    return False  # Default to False if unexpected response


# ... (keep your existing imports and configurations)


def check_process_status(process_id, user_id):
    """Check the status of a social process."""
    try:
        # You might need to adjust this endpoint based on your API
        status_url = f"{BASE_URL}/api/social-process/{process_id}"
        response = requests.get(
            status_url,
            headers=HEADERS
        )
        if response.status_code == 200:
            process_data = response.json()
            return process_data.get('status'), process_data.get('url')
        return None, None
    except Exception as e:
        st.error(f"Error checking status: {e}")
        return None, None


def wait_for_extraction(process_id, user_id):
    """Wait for the extraction process to complete with a progress bar."""
    progress_text = "Extraction in progress. Please wait..."
    progress_bar = st.progress(0)
    status_placeholder = st.empty()

    # Maximum number of attempts (30 * 2 seconds = 60 seconds timeout)
    max_attempts = 120
    attempt = 0

    while attempt < max_attempts:
        status, video_url = check_process_status(process_id, user_id)

        progress = min(attempt / max_attempts, 0.99)
        progress_bar.progress(progress)

        if status == 'COMPLETED':
            progress_bar.progress(1.0)
            status_placeholder.success("✅ Extraction completed!")
            return video_url
        elif status == 'FAILED':
            progress_bar.empty()
            status_placeholder.error("❌ Extraction failed")
            return None

        status_message = f"Status: {status or 'Processing'} (Attempt {attempt + 1}/{max_attempts})"
        status_placeholder.info(status_message)

        time.sleep(2)  # Wait 2 seconds between checks
        attempt += 1

    progress_bar.empty()
    status_placeholder.warning(
        "⚠️ Timeout: Process taking longer than expected")
    return None


def test_social_saving_page():
    st.title("🔗 Test Social Saving API")

    # Add input fields
    url_input = st.text_input(
        "📋 Paste the URL to process:",
        placeholder="https://www.instagram.com/reel/..."
    )

    user_id = st.text_input(
        "👤 User ID:",
        value="e7hL00MBOtaZJoBCiegCz61oVQI2"
    )

    source = st.selectbox(
        "🌍 Select Source",
        ["instagram", "facebook", "tiktok"]
    )

    # Process button and rest of your code
    if st.button("🚀 Process URL"):
        if not url_input:
            st.error("⚠️ Please enter a valid URL before submitting.")
        else:
            with st.spinner("Processing..."):
                response_data, log_messages = process_social_url(
                    url_input, user_id, source)

                if response_data:
                    # Display process details in a nice format
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("### Process Details")
                        st.write(f"🆔 Process ID: `{response_data.get('id')}`")
                        st.write(
                            f"📊 Status: `{response_data.get('status', 'Processing')}`")
                    with col2:
                        st.markdown("### Extracted Content")
                        if response_data.get('extracted_url'):
                            st.write("🎥 Video URL:")
                            st.code(response_data['extracted_url'])

                # Debug logs
                with st.expander("🔎 Debug Logs"):
                    for log in log_messages:
                        st.write(log)
