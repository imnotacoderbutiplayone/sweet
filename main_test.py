# main_test.py (Testing st.set_page_config first)

import os
import streamlit as st

# **First Streamlit command**
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test that page config is working
try:
    # Use a fallback for os.listdir() to get the files in the working directory
    current_dir = os.getcwd()  # Get current working directory in Streamlit Cloud
    directory_contents = os.listdir(current_dir)
    st.write("🗂️ Current directory contents:", directory_contents)
except Exception as e:
    st.error(f"Error: {e}")
