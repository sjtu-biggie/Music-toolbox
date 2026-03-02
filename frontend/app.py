import streamlit as st

st.set_page_config(page_title="AI Music", layout="wide")
st.title("AI Music")

tab_record, tab_upload, tab_editor = st.tabs(["Record", "Upload", "Editor"])

with tab_record:
    from components.record import render
    render()

with tab_upload:
    from components.upload import render
    render()

with tab_editor:
    from components.editor import render
    render()
