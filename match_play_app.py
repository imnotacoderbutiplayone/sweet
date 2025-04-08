import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import json
import re
import hashlib

# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- Admin Authentication (Simple Password-Based) ---
admin_password = st.secrets["admin_password"]

# Initialize Session States
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Admin login
if not st.session_state.authenticated:
    st.sidebar.header("🔐 Admin Login")
    pwd_input = st.sidebar.text_input("Enter Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.sidebar.success("✅ Logged in as admin.")
            st.rerun()
        else:
            st.sidebar.error("❌ Incorrect Admin Password.")
else:
    st.sidebar.success("✅ Admin logged in.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# --- Save Match Result (Only for Admins) ---
def save_match_result(pod, player1, player2, winner, margin_text):
    from datetime import datetime

    data = {
        "pod": pod,
        "player1": player1,
        "player2": player2,
        "winner": winner,
        "margin": margin_text,
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        # Only allow admins to save results
        if st.session_state.authenticated:
            response = supabase.table("match_results").insert(data).execute()
            return response
        else:
            st.error("❌ You must be logged in as admin to save match results.")
    except Exception as e:
        st.error("❌ Error saving match result to Supabase")
        st.code(str(e))
        return None

# --- Load Match Results ---
def load_match_results():
    try:
        response = supabase.table("match_results").select("*").order("created_at", desc=True).execute()
        match_dict = {}
        for r in response.data:
            match_key = f"{r['pod']}|{r['player1']} vs {r['player2']}"
            match_dict[match_key] = {
                "winner": r["winner"],
                "margin": r["margin"]
            }
        return match_dict
    except Exception as e:
        st.error("❌ Error loading match results")
        st.code(str(e))
        return {}

# --- Render Match Results ---
def render_match(p1, p2, winner_name="", readonly=False, key_prefix=""):
    label1 = f"{p1['name']} ({p1['handicap']})"
    label2 = f"{p2['name']} ({p2['handicap']})"
    match_label = f"🏌️ {label1} vs {label2}"

    if readonly:
        if winner_name == p1['name']:
            result_text = f"✔️ **{label1}** defeated **{label2}**"
        elif winner_name == p2['name']:
            result_text = f"✔️ **{label2}** defeated **{label1}**"
        else:
            result_text = f"❓ No winner recorded"
        st.markdown(result_text)
        return None
    else:
        choice = st.radio(match_label, [label1, label2], key=f"{key_prefix}_{p1['name']}_vs_{p2['name']}")
        return p1 if choice == label1 else p2

# --- Load Bracket Data ---
def load_bracket_data():
    try:
        response = supabase.table("bracket_data").select("json_data").order("created_at", desc=True).limit(1).execute()

        if response.data and len(response.data) > 0:
            return pd.read_json(response.data[0]["json_data"], orient="split")
        else:
            st.info("ℹ️ No bracket data found in Supabase.")
            return pd.DataFrame()

    except Exception as e:
        st.error("❌ Supabase error loading bracket data")
        st.code(str(e))
        return pd.DataFrame()

# --- Save Bracket Data ---
def save_bracket_data(df):
    try:
        json_data = df.to_json(orient="split")
        response = supabase.table("bracket_data").insert({"json_data": json_data}).execute()
        return response
    except Exception as e:
        st.error("❌ Failed to save bracket data to Supabase")
        st.code(str(e))
        return None

# --- Bracket Progress ---
def save_bracket_progression_to_supabase(data):
    try:
        response = supabase.table("bracket_progression").insert(data).execute()
        return response
    except Exception as e:
        st.error("❌ Error saving bracket progression to Supabase")
        st.code(str(e))

def load_bracket_progression_from_supabase():
    try:
        response = supabase.table("bracket_progression").select("*").order("created_at", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]
        else:
            return None
    except Exception as e:
        st.error("❌ Error loading bracket progression from Supabase")
        st.code(str(e))
        return None

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# Tab setup for viewing and interacting with the tournament
tabs = st.tabs([
    "📁 Tournament Overview",
    "📊 Match Results",
    "🏆 Bracket",
    "📤 Export Bracket",
    "🔮 Predict Bracket",
    "🗃️ Results Log",
    "🏅 Leaderboard"
])

# Tournament Overview Tab (Public Access)
with tabs[0]:
    st.subheader("📁 Tournament Overview")
    st.write("Welcome to the public tournament view! Here you can view the tournament bracket and match results.")

# Match Results Tab (Public Access)
with tabs[1]:
    st.subheader("📊 Match Results")
    match_results = load_match_results()
    if match_results:
        for match_key, result in match_results.items():
            st.write(f"{match_key} - Winner: {result['winner']} - Margin: {result['margin']}")
    else:
        st.write("No match results available.")

# Bracket Tab (Admin Access)
with tabs[2]:
    st.subheader("🏆 Bracket")
    bracket_df = load_bracket_data()
    if st.session_state.authenticated:
        st.info("🔐 Admin mode: Enter results and save")
        # Admin interface to enter match results and update bracket
        st.write(bracket_df)
        # Add code to modify and save bracket data
    else:
        st.write(bracket_df)

# Export Bracket Tab (Public Access)
with tabs[3]:
    st.subheader("📤 Export Bracket")
    if not bracket_df.empty:
        csv = bracket_df.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# Predict Bracket Tab (Public Access)
with tabs[4]:
    st.subheader("🔮 Predict Bracket")
    st.write("Here you can predict the outcomes of the tournament. Your predictions will be saved.")

# Results Log Tab (Admin Access)
with tabs[5]:
    st.subheader("🗃️ Match Results Log")
    if st.session_state.authenticated:
        st.write("Log of all match results will be shown here for admins.")
    else:
        st.write("No match results available yet.")

# Leaderboard Tab (Public Access)
with tabs[6]:
    st.subheader("🏅 Leaderboard")
    st.write("Leaderboard will be shown here based on bracket predictions.")
