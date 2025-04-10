# main_test.py (Testing st.set_page_config first)

import os
import streamlit as st

# **First Streamlit command**
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test that page config is working
current_dir = os.path.dirname(__file__)  # Gets the current directory
st.write("🗂️ Current directory contents:", os.listdir(current_dir))  # Use the current directory explicitly
