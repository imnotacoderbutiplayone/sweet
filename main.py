# main.py (Minimal version to test Streamlit's page config)

import os
import sys
sys.path.append(os.path.dirname(__file__))

# First Streamlit command must be st.set_page_config
import streamlit as st
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Now, add only the necessary imports
from supabase import create_client
import pandas as pd
import json
from datetime import datetime
