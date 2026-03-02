import streamlit as st
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def _init_tracks():
    if "tracks" not in st.session_state:
        st.session_state["tracks"] = []


def render():
    _init_tracks()
    st.header("Upload Audio")

    track_name = st.text_input("Track name", placeholder="e.g. My Song Take 1")
    uploaded = st.file_uploader(
        "Upload mp3, wav, m4a, or flac", type=["mp3", "wav", "m4a", "flac", "ogg"]
    )

    can_process = uploaded is not None and track_name.strip() != ""
    if not can_process and uploaded:
        st.warning("Enter a track name before processing.")

    if can_process and st.button("Process"):
        with st.spinner("Uploading and processing..."):
            try:
                result = api_client.upload_audio(uploaded.read(), uploaded.name)
                track_entry = {
                    "track_id": result["track_id"],
                    "name": track_name.strip(),
                    "duration_sec": result["duration_sec"],
                    "sample_rate": result["sample_rate"],
                }
                st.session_state["tracks"].append(track_entry)
                st.session_state["active_track_id"] = result["track_id"]
                display = f"{track_name.strip()} ({result['track_id'][:8]}...)"
                st.success(f"Track loaded: {display} — {result['duration_sec']:.1f}s at {result['sample_rate']}Hz")
                st.info("Switch to the Editor tab to view and play your track.")
            except Exception as e:
                st.error(f"Upload failed: {e}")

    # Show uploaded tracks
    tracks = st.session_state.get("tracks", [])
    if tracks:
        st.subheader(f"Tracks ({len(tracks)})")
        for t in tracks:
            st.caption(f"{t['name']} ({t['track_id'][:8]}...) — {t['duration_sec']:.1f}s")
