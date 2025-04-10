# main.py (Clean and Modular)
import streamlit as st
from supabase import create_client
from bracket_helpers import *
from app_helpers import *  # where render_match and get_winner_player live
import pandas as pd
import json
from datetime import datetime

# --- Config ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# --- Supabase Init ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_supabase()

# --- Auth ---
admin_password = st.secrets["admin_password"]["password"]
general_password = st.secrets["general_password"]["password"]

# Initialize session state variables
if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Check if the user is authenticated
if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament Login")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == general_password:
            st.session_state.app_authenticated = True
            st.rerun()  # Refresh to show logged-in state
        else:
            st.error("Incorrect password.")
    st.stop()  # Stop further execution until the user is authenticated

# Sidebar Admin Login
st.sidebar.header("🔐 Admin Login")
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.rerun()  # Refresh to show logged-in state
        else:
            st.sidebar.error("Wrong password.")
else:
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()  # Refresh to show logged-out state

# --- Tabs ---
tabs = st.tabs(["📁 Pods Overview", "📊 Group Stage", "📋 Standings", "🏆 Bracket", "🔮 Predict Bracket", "🏅 Leaderboard", "📘 How It Works"])

# --- Shared Data ---
players_response = supabase.table("players").select("*").execute()
players_df = pd.DataFrame(players_response.data)
pods = group_players_by_pod(players_df)

# --- Tab 0: Pods Overview ---
# --- Tab 0: Pods Overview ---
with tabs[0]:
    st.title("🏌️ Pods Overview")
    
    # Example styling for a section title
    st.markdown("### Grouped by Pods")

    # Loop through each pod and display players
    for pod_name, players in pods.items():
        with st.expander(f"📦 {pod_name} Players", expanded=False):  # Use Expander for each Pod
            # Prepare a DataFrame to display
            players_df = pd.DataFrame(players)

            # Display table with styling
            st.dataframe(
                players_df.style
                    .set_properties(**{'background-color': '#f0f0f0', 'color': '#000'})
                    .set_table_styles([{
                        'selector': 'thead th', 
                        'props': [('background-color', '#3E6B71'), ('color', 'white')]
                    }])
                    .hide(axis='index')
            )

            # Add some player info with markdown
            for player in players:
                st.markdown(f"**{player['Name']}** (Handicap: {player['Handicap']})")

            st.write("---")  # A horizontal line to separate pods

# --- Tab 1: Group Stage ---
with tabs[1]:
    run_group_stage(pods, supabase)

# --- Tab 2: Standings ---
with tabs[2]:
    show_standings(pods, supabase)

# --- Tab 3: Bracket ---
with tabs[3]:
    run_bracket_stage(players_df, supabase)

# --- Tab 4: Predict Bracket ---
with tabs[4]:
    run_predictions_tab(supabase)

# --- Tab 5: Leaderboard ---
with tabs[5]:
    show_leaderboard(supabase)

# --- Tab 6: How It Works ---
with tabs[6]:
    show_how_it_works()
