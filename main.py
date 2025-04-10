# main.py (After adding helpers)

import os
import sys
sys.path.append(os.path.dirname(__file__))

# First Streamlit command must be st.set_page_config
import streamlit as st
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test the page configuration by displaying something
st.title("Golf Match Play Tournament")  # Simple title to confirm rendering

# Now, add the helper imports one by one
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

# Import helpers (bracket_helpers and app_helpers)
from bracket_helpers import *  # where render_match and get_winner_player live
from app_helpers import *  # where other helper functions live
