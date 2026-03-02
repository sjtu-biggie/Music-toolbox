import streamlit as st
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def _init_tracks():
    if "tracks" not in st.session_state:
        st.session_state["tracks"] = []


def render():
    _init_tracks()
    st.header("Record from Microphone")
    st.caption("Click the microphone to start recording. Click again to stop.")

    track_name = st.text_input("Track name", placeholder="e.g. My Melody Take 1", key="record_track_name")
    audio_value = st.audio_input("Sing or play your melody")

    if audio_value is not None:
        st.audio(audio_value)  # preview the recording
        can_process = track_name.strip() != ""
        if not can_process:
            st.warning("Enter a track name before processing.")
        if can_process and st.button("Process Recording"):
            with st.spinner("Uploading to backend..."):
                try:
                    result = api_client.record_audio(audio_value.read(), "recording.wav")
                    track_entry = {
                        "track_id": result["track_id"],
                        "name": track_name.strip(),
                        "duration_sec": result["duration_sec"],
                        "sample_rate": result["sample_rate"],
                    }
                    st.session_state["tracks"].append(track_entry)
                    st.session_state["active_track_id"] = result["track_id"]
                    display = f"{track_name.strip()} ({result['track_id'][:8]}...)"
                    st.success(f"Recording processed — {display}, {result['duration_sec']:.1f}s.")
                    st.info("Switch to the Editor tab to view and play your track.")
                except Exception as e:
                    st.error(f"Failed: {e}")

    # Show all tracks
    tracks = st.session_state.get("tracks", [])
    if tracks:
        st.subheader(f"Tracks ({len(tracks)})")
        for t in tracks:
            st.caption(f"{t['name']} ({t['track_id'][:8]}...) — {t['duration_sec']:.1f}s")
