import streamlit as st
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def render():
    st.header("Upload Audio")
    uploaded = st.file_uploader(
        "Upload mp3, wav, m4a, or flac", type=["mp3", "wav", "m4a", "flac", "ogg"]
    )
    if uploaded and st.button("Process"):
        with st.spinner("Uploading and processing..."):
            try:
                result = api_client.upload_audio(uploaded.read(), uploaded.name)
                st.session_state["track_id"] = result["track_id"]
                st.success(f"Track loaded — {result['duration_sec']:.1f}s at {result['sample_rate']}Hz")
                st.info("Switch to the Editor tab to view and play your track.")
            except Exception as e:
                st.error(f"Upload failed: {e}")
