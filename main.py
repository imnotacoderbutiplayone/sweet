# main.py (Updated minimal version to test Streamlit's page config)

import os
import sys
sys.path.append(os.path.dirname(__file__))

# First Streamlit command must be st.set_page_config
import streamlit as st
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Test the page configuration by displaying something
st.title("Golf Match Play Tournament")  # Add a simple title to confirm it's rendering
