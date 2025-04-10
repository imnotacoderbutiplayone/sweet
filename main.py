import os
import sys

# Add the current directory to sys.path so Python can find local modules
sys.path.append(os.path.dirname(__file__))

# Debugging line to check contents of current directory
current_dir_contents = os.listdir()

# Print directory contents to Streamlit log (console output)
print("🗂️ Current directory contents:", current_dir_contents)

# Try importing app_helpers and bracket_helpers
try:
    import app_helpers
    print("app_helpers imported successfully")
except ImportError as e:
    print(f"Error importing app_helpers: {e}")

# Streamlit and other necessary imports
import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

# Set up Streamlit configuration
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
st.title("Golf Match Play Tournament")
