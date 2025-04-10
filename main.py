import os
import sys

# Add the directory of the current file to the path for imports
sys.path.append(os.path.dirname(__file__))

# Import Streamlit and other libraries
import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

# Import helpers
from bracket_helpers import *
from app_helpers import *  # Ensure app_helpers is in the same directory

st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
st.title("Golf Match Play Tournament")
