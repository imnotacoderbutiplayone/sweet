# main_test.py (Testing st.set_page_config first)

import streamlit as st

# **First Streamlit command**
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test that page config is working
st.write("🗂️ Current directory contents:", os.listdir())  # This will work now

