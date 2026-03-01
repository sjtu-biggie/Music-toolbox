import streamlit as st

st.set_page_config(page_title="AI Music", layout="wide")
st.title("AI Music")

tab_upload, tab_editor = st.tabs(["Upload / Record", "Editor"])

with tab_upload:
    from pages.upload import render
    render()

with tab_editor:
    from pages.editor import render
    render()
