# main.py (Updated import path if needed)
import sys
import os

# Add the directory of the current file to the path for imports
sys.path.append(os.path.dirname(__file__))

# Import Streamlit and other libraries
import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

# Import helpers (bracket_helpers and app_helpers)
from bracket_helpers import *
from app_helpers import *  # Check that app_helpers.py is in the same directory or adjust the path

st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
st.title("Golf Match Play Tournament")
