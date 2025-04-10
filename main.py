import os
import streamlit as st

# **First Streamlit command**
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test that page config is working
current_dir = os.getcwd()
directory_contents = os.listdir(current_dir)
st.write("🗂️ Current directory contents:", directory_contents)

# Try importing the helpers (for testing)
try:
    import app_helpers
    st.write("app_helpers imported successfully")
except Exception as e:
    st.error(f"Error importing app_helpers: {e}")
