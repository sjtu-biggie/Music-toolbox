import streamlit as st
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
import api_client


def render():
    st.header("Editor")
    track_id = st.session_state.get("track_id")
    if not track_id:
        st.info("Upload a track first.")
        return

    st.caption(f"Track ID: `{track_id}`")

    # Instrument selector
    try:
        inst_data = api_client.list_instruments()
        instruments = inst_data["instruments"]
        default_idx = instruments.index(inst_data["default"])
    except Exception:
        instruments = ["piano", "violin", "cello"]
        default_idx = 0
    selected_instrument = st.selectbox("Instrument", instruments, index=default_idx)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Extract MIDI"):
            with st.spinner("Extracting pitch and rhythm (may take 30s)..."):
                try:
                    result = api_client.extract_midi(track_id)
                    st.session_state["notes"] = result["notes"]
                    st.success(f"Extracted {len(result['notes'])} notes")
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

    with col2:
        if st.button("Synthesize & Play"):
            with st.spinner(f"Synthesizing with {selected_instrument}..."):
                try:
                    api_client.synthesize(track_id, instrument=selected_instrument)
                    st.success(f"Done! Instrument: {selected_instrument}")
                except Exception as e:
                    st.error(f"Synthesis failed: {e}")

    # Waveform plot
    try:
        wf = api_client.get_waveform(track_id)
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.plot(wf["times"], wf["amplitudes"], linewidth=0.5, color="steelblue")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude")
        ax.set_title("Waveform")
        st.pyplot(fig)
        plt.close(fig)
    except Exception:
        pass

    # Playback
    st.subheader("Playback")
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.caption("Original")
        st.audio(api_client.get_playback_url(track_id))
    with pcol2:
        st.caption("Synthesized (after Extract + Synthesize)")
        st.audio(api_client.get_synth_playback_url(track_id))

    # Note editor
    notes = st.session_state.get("notes", [])
    if notes:
        st.subheader(f"Notes ({len(notes)})")
        for note in notes[:50]:
            with st.expander(f"Note {note['pitch_midi']} | {note['start_sec']:.2f}s – {note['end_sec']:.2f}s"):
                new_pitch = st.number_input("Pitch (MIDI 0-127)", 0, 127, note["pitch_midi"], key=f"p_{note['id']}")
                new_start = st.number_input("Start (s)", 0.0, value=note["start_sec"], step=0.01, key=f"s_{note['id']}")
                new_end = st.number_input("End (s)", 0.0, value=note["end_sec"], step=0.01, key=f"e_{note['id']}")
                if st.button("Update", key=f"u_{note['id']}"):
                    api_client.update_note(track_id, note["id"], {
                        "pitch_midi": new_pitch, "start_sec": new_start, "end_sec": new_end
                    })
                    st.success("Updated — click Synthesize to hear changes")
