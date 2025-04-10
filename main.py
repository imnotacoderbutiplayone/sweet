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
with tabs[0]:
    # Loop through each pod and its players
    for pod_name, players in pods.items():
        st.markdown(f"### 🏌️ Pod: {pod_name}")
        
        # Create a table-style display for each pod's players
        pod_data = []
        
        for player in players:
            if 'name' in player and 'handicap' in player:
                # Add data to the list for later display in a table
                pod_data.append({
                    'Name': player['name'],
                    'Handicap': f"{player['handicap']:.1f}"
                })
            else:
                st.error(f"Player data is missing 'name' or 'handicap' for {player}")
        
        # Convert pod data into a DataFrame for nicer table formatting
        if pod_data:
            df_pod = pd.DataFrame(pod_data)

            # Use streamlit's table with some custom styling
            st.markdown(
                f"""
                <style>
                .table-container {{
                    border: 1px solid #eee;
                    border-radius: 8px;
                    padding: 10px;
                }}
                .table-container th {{
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    text-align: center;
                }}
                .table-container td {{
                    padding: 8px;
                    text-align: center;
                    font-size: 14px;
                }}
                .table-container tr:nth-child(even) {{
                    background-color: #f2f2f2;
                }}
                .table-container tr:hover {{
                    background-color: #ddd;
                }}
                </style>
                <div class="table-container">
                {df_pod.to_html(index=False, escape=False)}
                </div>
                """, unsafe_allow_html=True)




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
