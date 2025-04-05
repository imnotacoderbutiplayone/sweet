import streamlit as st
import pandas as pd
from collections import defaultdict
import json
import os
import tempfile
import shutil

# --- Utility functions for persistence ---
def safe_save(file_path, data):
    """Safely write JSON to a file using atomic write."""
    try:
        temp_file = tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(file_path))
        json.dump(data, temp_file)
        temp_file.close()
        shutil.move(temp_file.name, file_path)
    except Exception as e:
        st.error(f"Error saving file: {e}")

def save_json(file_path, data):
    """Save JSON to a file."""
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_json(file_path):
    """Load JSON from a file."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}

# --- Streamlit App Config and File Paths ---
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

# --- Load match results into session state (on app startup) ---
if "match_results" not in st.session_state:
    st.session_state.match_results = load_json(RESULTS_FILE)

# --- Load shared bracket data ---
if "bracket_data" not in st.session_state:
    if os.path.exists(BRACKET_FILE):
        st.session_state.bracket_data = pd.read_json(BRACKET_FILE, orient="split")
    else:
        st.session_state.bracket_data = pd.DataFrame()

# ---- Global Password Protection ----
admin_password = st.secrets["admin_password"]
general_password = st.secrets["general_password"]

# Initialize Session States
if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- General Access Password ---
if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament - Restricted Access")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == general_password:
            st.session_state.app_authenticated = True
            st.success("Welcome! Refreshing...")
            st.rerun()
        else:
            st.error("Incorrect tournament password.")
    st.stop()

# --- Admin Login ---
if not st.session_state.authenticated:
    st.sidebar.header("🔐 Admin Login")
    admin_pwd = st.sidebar.text_input("Enter Admin Password", type="password")
    if st.sidebar.button("Login"):
        if admin_pwd == admin_password:
            st.session_state.authenticated = True
            st.sidebar.success("✅ Logged in as admin.")
        else:
            st.sidebar.error("❌ Incorrect admin password.")
else:
    st.sidebar.success("✅ Admin logged in.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.sidebar.success("Logged out.")

# Admin Actions - Reset Data
if st.session_state.authenticated:
    st.sidebar.subheader("Admin Actions")
    if st.sidebar.button("Clear All Match Data"):
        st.session_state.bracket_data = pd.DataFrame()
        st.session_state.match_results = {}
        save_json(RESULTS_FILE, {})
        st.success("Data has been refreshed. Please refresh your browser.")
        st.stop()

# --- Pod Assignments ---
pods = {
    "Pod 1": [
        {"name": "Wade Bowlin", "handicap": 5.4},
        {"name": "Chip Nemesi", "handicap": 8.2},
        {"name": "Anand Saranathan", "handicap": None},
        {"name": "Tim Coyne", "handicap": 14.0},
    ],
    "Pod 2": [
        {"name": "Tim Stubenrouch", "handicap": 6.8},
        {"name": "David Gornet", "handicap": 12.4},
        {"name": "Ken Wood", "handicap": 21.3},
        {"name": "William Dicks", "handicap": 20.3},
    ],
    "Pod 3": [
        {"name": "Austen Flatt", "handicap": 5.5},
        {"name": "Robert Polk", "handicap": 11.8},
        {"name": "Pravin Patel", "handicap": 16.5},
        {"name": "Benjamin Dickinson", "handicap": 16.3},
    ],
    "Pod 4": [
        {"name": "Anup Aggrawal", "handicap": 11.4},
        {"name": "Pratish Lad", "handicap": 11.5},
        {"name": "Kevin Sutton", "handicap": 12.5},
        {"name": "Raj Patel", "handicap": 11.8},
    ],
    "Pod 5": [
        {"name": "Russell Clingman", "handicap": 12.7},
        {"name": "Tom Duffy", "handicap": 15.7},
        {"name": "Charles Ferdin", "handicap": 25.2},
        {"name": "Danny Delgado", "handicap": 16.6},
    ],
    "Pod 6": [
        {"name": "Paul Till", "handicap": 1.3},
        {"name": "Daniel Nowak", "handicap": 9.0},
        {"name": "Avo Mavilian", "handicap": 19.4},
        {"name": "Jason Case", "handicap": 12.6},
    ],
    "Pod 7": [
        {"name": "Keith Borgfeldt", "handicap": 9.8},
        {"name": "Danny Rice", "handicap": 11.1},
        {"name": "Keith Patel", "handicap": 17.7},
        {"name": "Sanjay Lad", "handicap": 15.2},
    ],
    "Pod 8": [
        {"name": "Michael Trevino", "handicap": 9.9},
        {"name": "Brad Sinclair", "handicap": 13.0},
        {"name": "Bill Ostrowski", "handicap": 16.0},
        {"name": "Aldo Rodriguez", "handicap": 13.6},
    ],
    "Pod 9": [
        {"name": "Rob Calvo", "handicap": 2.7},
        {"name": "Randy Tate", "handicap": 7.1},
        {"name": "Michael Kuznar", "handicap": 17.1},
        {"name": "Mel Davis", "handicap": 8.5},
    ],
    "Pod 10": [
        {"name": "Craig McGaughy", "handicap": 7.2},
        {"name": "Brian Burr", "handicap": 7.3},
        {"name": "Andy Grote", "handicap": 13.3},
        {"name": "Larry Hawkins", "handicap": 12.5},
    ],
    "Pod 11": [
        {"name": "Andrew Escamilla", "handicap": -0.8},
        {"name": "Jay Jones", "handicap": 5.4},
        {"name": "Kevin Sareen", "handicap": 16.6},
        {"name": "Alexander Roman", "handicap": 5.4},
    ],
    "Pod 12": [
        {"name": "Will Main", "handicap": 2.2},
        {"name": "Todd Riddle", "handicap": 7.5},
        {"name": "Kolbe Curtice", "handicap": 12.9},
        {"name": "Sunil Patel", "handicap": 11.6},
    ],
    "Pod 13": [
        {"name": "Tony Delgado", "handicap": 3.1},
        {"name": "Pawan Nerusu", "handicap": 9.9},
        {"name": "Marcus Peet", "handicap": 22.5},
        {"name": "Ed Gifford", "handicap": 10.3},
    ],
}

margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

# --- Match Simulation ---
def simulate_matches(players, pod_name):
    results = st.session_state.match_results.get(pod_name, defaultdict(lambda: {"points": 0, "margin": 0}))
    updated_players = []

    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            p1, p2 = players[i], players[j]
            col = f"{p1['name']} vs {p2['name']}"
            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] is not None else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] is not None else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if st.session_state.authenticated:
                entry_key = col + "_entered"
                entered = st.checkbox("Enter result for this match", key=entry_key)

                if entered:
                    winner = st.radio(f"Who won?", [p1['name'], p2['name'], "Tie"], index=2, key=col)
                    margin = 0
                    if winner != "Tie":
                        result_str = st.selectbox("Select Match Result (Win Margin)", options=list(margin_lookup.keys()), key=col + "_result")
                        margin = margin_lookup[result_str]

                    if winner == p1['name']:
                        results[p1['name']]['points'] += 1
                        results[p1['name']]['margin'] += margin
                        results[p2['name']]['margin'] -= margin
                    elif winner == p2['name']:
                        results[p2['name']]['points'] += 1
                        results[p2['name']]['margin'] += margin
                        results[p1['name']]['margin'] -= margin
                    else:  # Tie
                        results[p1['name']]['points'] += 0.5
                        results[p2['name']]['points'] += 0.5

                    st.session_state.match_results[pod_name] = results
                    safe_save(RESULTS_FILE, st.session_state.match_results)
                    st.success("Result saved.")

            else:
                st.info("🔒 Only admin can enter match results.")

    for player in players:
        player_results = results.get(player['name'], {"points": 0, "margin": 0})
        updated_player = {**player, **player_results}
        updated_players.append(updated_player)

    return updated_players

# --- Streamlit App Configuration ---
st.title("🏌️‍♂️ Golf Match Play Tournament Dashboard")
tabs = st.tabs(["📁 Pods Overview", "📊 Group Stage", "📈 Standings", "🏆 Bracket", "📥 Export", "🔮 Predict Bracket"])

if "bracket_data" not in st.session_state:
    st.session_state.bracket_data = pd.DataFrame()

# --- Pods Overview ---
with tabs[0]:
    st.subheader("📁 All Pods and Player Handicaps")
    pod_names = list(pods.keys())
    for i, pod_name in enumerate(pod_names):
        st.markdown(f"#### {pod_name}")
        df = pd.DataFrame(pods[pod_name])[["name", "handicap"]]
        df["handicap"] = df["handicap"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "N/A")
        df.rename(columns={"name": "Player", "handicap": "Handicap"}, inplace=True)
        st.dataframe(df)

# --- Group Stage ---
with tabs[1]:
    st.subheader("📊 Group Stage - Match Results")
    pod_results = {}
    for pod_name, players in pods.items():
        with st.expander(pod_name):
            if isinstance(players, list) and len(players) > 0:
                updated_players = simulate_matches(players, pod_name)
                pod_results[pod_name] = pd.DataFrame(updated_players)

# --- Standings ---
with tabs[2]:
    st.subheader("📈 Standings")
    if st.session_state.match_results:
        all_results = []
        for pod_name, pod_results in st.session_state.match_results.items():
            for player, stats in pod_results.items():
                all_results.append({"Pod": pod_name, "Player": player, "Points": stats["points"], "Margin": stats["margin"]})

        standings = pd.DataFrame(all_results)
        if standings.empty:
            st.info("No matches have been played yet.")
        else:
            standings = standings.sort_values(by=["Points", "Margin"], ascending=[False, False])
            st.dataframe(standings)
    else:
        st.info("No matches have been played yet.")

# --- Bracket ---
with tabs[3]:
    st.subheader("🏆 Bracket")
    if st.session_state.bracket_data.empty:
        st.warning("Please calculate bracket seeding from the Group Stage tab first.")
    else:
        bracket_df = st.session_state.bracket_data
        left = bracket_df.iloc[0:8].reset_index(drop=True)
        right = bracket_df.iloc[8:16].reset_index(drop=True)
        st.write(bracket_df)

# --- Export ---
with tabs[4]:
    st.subheader("📥 Export")
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# --- Predict Bracket ---
with tabs[5]:
    st.subheader("🔮 Predict Bracket")
    if st.session_state.bracket_data.empty:
        st.warning("Bracket prediction will be available once the field of 16 is set.")
    else:
        username = st.text_input("Enter your name or initials:")
        if username:
            st.markdown("Make your picks before the tournament begins.")
            bracket_df = st.session_state.bracket_data
            left = bracket_df.iloc[0:8].reset_index(drop=True)
            right = bracket_df.iloc[8:16].reset_index(drop=True)

            # Left Side Predictions
            st.markdown("### 🔵 Left Side Predictions")
            pred_qf_left = []
            for i in range(0, 8, 2):
                p1, p2 = left.iloc[i], left.iloc[i + 1]
                pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PL16_{i}_{username}")
                pred_qf_left.append(p1 if pick == label(p1) else p2)

            pred_sf_left = []
            for i in range(0, len(pred_qf_left), 2):
                p1, p2 = pred_qf_left[i], pred_qf_left[i + 1]
                pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PLQF_{i}_{username}")
                pred_sf_left.append(p1 if pick == label(p1) else p2)

            finalist_left = st.radio(f"Left Finalist:", [label(pred_sf_left[0]), label(pred_sf_left[1])], key=f"PLSF_{username}")
            finalist_left = pred_sf_left[0] if finalist_left == label(pred_sf_left[0]) else pred_sf_left[1]

            # Right Side Predictions
            st.markdown("### 🔴 Right Side Predictions")
            pred_qf_right = []
            for i in range(0, 8, 2):
                p1, p2 = right.iloc[i], right.iloc[i + 1]
                pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PR16_{i}_{username}")
                pred_qf_right.append(p1 if pick == label(p1) else p2)

            pred_sf_right = []
            for i in range(0, len(pred_qf_right), 2):
                p1, p2 = pred_qf_right[i], pred_qf_right[i + 1]
                pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PRQF_{i}_{username}")
                pred_sf_right.append(p1 if pick == label(p1) else p2)

            finalist_right = st.radio(f"Right Finalist:", [label(pred_sf_right[0]), label(pred_sf_right[1])], key=f"PRSF_{username}")
            finalist_right = pred_sf_right[0] if finalist_right == label(pred_sf_right[0]) else pred_sf_right[1]

            # Champion Prediction
            champion = st.radio(f"🏆 Predict the Champion:", [label(finalist_left), label(finalist_right)], key=f"PickChamp_{username}")
            champion_final = finalist_left if champion == label(finalist_left) else finalist_right

            if st.button("Submit My Bracket"):
                st.session_state.user_predictions[username] = {
                    "finalist_left": finalist_left['name'],
                    "finalist_right": finalist_right['name'],
                    "champion": champion_final['name']
                }
                st.success("Your bracket has been submitted!")

        if st.session_state.user_predictions:
            st.subheader("📊 Current Predictions")
            for user, picks in st.session_state.user_predictions.items():
                st.markdown(f"**{user}** picked _{picks['champion']}_ to win")
