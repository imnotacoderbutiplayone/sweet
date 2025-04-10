import os
import sys

# Add the current directory to sys.path so Python can find local modules
sys.path.append(os.path.dirname(__file__))

# Debugging: Check the current working directory
current_dir = os.getcwd()
print(f"Current working directory: {current_dir}")

# List the contents of the current directory to ensure app_helpers.py exists
print("🗂️ Current directory contents:", os.listdir(current_dir))

# Try importing app_helpers
try:
    import app_helpers
    print("app_helpers imported successfully")
except ImportError as e:
    print(f"Error importing app_helpers: {e}")

# Continue with your Streamlit app
import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
st.title("Golf Match Play Tournament")
