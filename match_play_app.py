import streamlit as st
import pandas as pd
from collections import defaultdict
import json
import os

# --- Utility functions for persistence ---
def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None

# --- Streamlit App Config and File Paths ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

# Load shared bracket data
if "bracket_data" not in st.session_state:
    bracket_raw = load_json(BRACKET_FILE)
    if bracket_raw:
        st.session_state.bracket_data = pd.read_json(bracket_raw, orient="split")
    else:
        st.session_state.bracket_data = pd.DataFrame()

# Load match results (optional extension later)
if "match_results" not in st.session_state:
    st.session_state.match_results = load_json(RESULTS_FILE) or {}

# ---- Global Password Protection ----
admin_password = st.secrets["admin_password"]
general_password = st.secrets["general_password"]

# Initialize Session States
if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# ---- General Access Password ----
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

# ---- Sidebar Admin Login ----
st.sidebar.header("🔐 Admin Login")
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("Enter Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.sidebar.success("Logged in as admin.")
        else:
            st.sidebar.error("Incorrect Admin Password.")
else:
    st.sidebar.success("✅ Admin logged in.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False


# Correct Pod assignments from PDF
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
    # Add other pods...
}

margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None


# --- Simulation Function ---
def simulate_matches(players, key_prefix=""):
    results = defaultdict(lambda: {"points": 0, "margin": 0})
    num_players = len(players)
    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1, p2 = players[i], players[j]
            col = f"{p1['name']} vs {p2['name']}"
            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] is not None else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] is not None else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if st.session_state.authenticated:
                entry_key = key_prefix + col + "_entered"
                entered = st.checkbox("Enter result for this match", key=entry_key)

                if entered:
                    match_key = key_prefix + col
                    stored_result = st.session_state.match_results.get(match_key, {})
                    winner_default = stored_result.get("winner", "Tie")
                    margin_default = stored_result.get("margin", 0)

                    winner = st.radio(f"Who won?", [p1['name'], p2['name'], "Tie"], index=[p1['name'], p2['name'], "Tie"].index(winner_default), key=match_key)
                    margin = 0
                    if winner != "Tie":
                        margin_options = list(margin_lookup.keys())
                        margin_str_default = [k for k, v in margin_lookup.items() if v == margin_default]
                        default_index = margin_options.index(margin_str_default[0]) if margin_str_default else 0
                        result_str = st.selectbox("Select Match Result (Win Margin)", options=margin_options, index=default_index, key=match_key + "_result")
                        margin = margin_lookup[result_str]

                    # Save match result to session and file
                    st.session_state.match_results[match_key] = {"winner": winner, "margin": margin}
                    save_json(RESULTS_FILE, st.session_state.match_results)

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
            else:
                st.info("🔒 Only admin can enter match results.")

    for player in players:
        player["points"] = 0
        player["margin"] = 0
        player.update(results[player["name"]])
    return players

# --- Tabs Setup ---
tabs = st.tabs(["Pods Overview", "Group Stage", "Standings", "Bracket", "Export", "Predict Bracket"])

# --- Pod Overview Tab ---
with tabs[0]:
    st.subheader("📂 Pod Overview")
    if "pod_results" not in st.session_state:
        st.session_state.pod_results = {}

    for pod_name, players in pods.items():
        with st.expander(pod_name):
            updated_players = simulate_matches(players, key_prefix=pod_name + "_")
            st.session_state.pod_results[pod_name] = pd.DataFrame(updated_players)
            st.write(st.session_state.pod_results[pod_name])

# --- Group Stage Results Tab ---
with tabs[1]:
    if "pod_results" not in st.session_state:
        st.session_state.pod_results = {}

    st.subheader("📊 Group Stage - Match Results")
    for pod_name, players in pods.items():
        with st.container():
            st.markdown(f"### {pod_name}")
            updated_players = simulate_matches(players, key_prefix=pod_name + "_")
            st.session_state.pod_results[pod_name] = pd.DataFrame(updated_players)


# --- Pod Winners Calculation ---
if st.session_state.authenticated:
    if st.button("Calculate Pod Winners"):
        winners, second_place = [], []
        for pod_name, df in st.session_state.pod_results.items():
            if "points" not in df.columns or df["points"].sum() == 0:
                continue  # skip pods with no entered matches
            sorted_players = df.sort_values(by=["points", "margin"], ascending=False).reset_index(drop=True)
            winners.append({"pod": pod_name, **sorted_players.iloc[0].to_dict()})
            second_place.append(sorted_players.iloc[1].to_dict())

        top_3 = sorted(second_place, key=lambda x: (x["points"], x["margin"]), reverse=True)[:3]
        final_players = winners + top_3
        bracket_df = pd.DataFrame(final_players)
        bracket_df.index = [f"Seed {i+1}" for i in range(len(bracket_df))]
        st.session_state.bracket_data = bracket_df
        save_json(BRACKET_FILE, bracket_df.to_json(orient="split"))
        st.success("✅ Pod winners and bracket seeded.")
else:
    st.info("🔒 Only admin can calculate pod winners.")


# Tab 2: Bracket
with tabs[3]:
    st.subheader("🏆 Bracket")
    if st.session_state.bracket_data.empty:
        st.warning("Please calculate bracket seeding from the Group Stage tab first.")
    else:
        bracket_df = st.session_state.bracket_data
        left = bracket_df.iloc[0:8].reset_index(drop=True)
        right = bracket_df.iloc[8:16].reset_index(drop=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🟦 Left Side")
            st.markdown("#### 🏁 Round of 16")
            qf_left = []
            for i in range(0, 8, 2):
                p1, p2 = left.iloc[i], left.iloc[i + 1]
                winner = st.radio(
                    f"{label(p1)} vs {label(p2)}",
                    [label(p1), label(p2)],
                    key=f"R16L_{i}"
                )
                qf_left.append(p1 if winner == label(p1) else p2)

            st.markdown("#### 🥈 Quarterfinals")
            sf_left = []
            for i in range(0, len(qf_left), 2):
                p1, p2 = qf_left[i], qf_left[i + 1]
                winner = st.radio(
                    f"QF: {label(p1)} vs {label(p2)}",
                    [label(p1), label(p2)],
                    key=f"QFL_{i}"
                )
                sf_left.append(p1 if winner == label(p1) else p2)

            st.markdown("#### 🥇 Semifinal Winner")
            finalist_left = st.radio(
                "🏅 Left Finalist:",
                [label(sf_left[0]), label(sf_left[1])],
                key="LFinal"
            )
            finalist_left = sf_left[0] if finalist_left == label(sf_left[0]) else sf_left[1]

        with col2:
            st.markdown("### 🟥 Right Side")
            st.markdown("#### 🏁 Round of 16")
            qf_right = []
            for i in range(0, 8, 2):
                p1, p2 = right.iloc[i], right.iloc[i + 1]
                winner = st.radio(
                    f"{label(p1)} vs {label(p2)}",
                    [label(p1), label(p2)],
                    key=f"R16R_{i}"
                )
                qf_right.append(p1 if winner == label(p1) else p2)

            st.markdown("#### 🥈 Quarterfinals")
            sf_right = []
            for i in range(0, len(qf_right), 2):
                p1, p2 = qf_right[i], qf_right[i + 1]
                winner = st.radio(
                    f"QF: {label(p1)} vs {label(p2)}",
                    [label(p1), label(p2)],
                    key=f"QFR_{i}"
                )
                sf_right.append(p1 if winner == label(p1) else p2)

            st.markdown("#### 🥇 Semifinal Winner")
            finalist_right = st.radio(
                "🏅 Right Finalist:",
                [label(sf_right[0]), label(sf_right[1])],
                key="RFinal"
            )
            finalist_right = sf_right[0] if finalist_right == label(sf_right[0]) else sf_right[1]

        st.markdown("### 🏁 Final Match")
        champion = st.radio(
            "🏆 Champion:",
            [label(finalist_left), label(finalist_right)],
            key="Champ"
        )
        winner = finalist_left if champion == label(finalist_left) else finalist_right
        st.success(f"🎉 Champion: {winner['name']} ({winner['handicap']})")

# Tab 3: Standings
with tabs[2]:
    st.subheader("\U0001F4CB Standings")
    if not st.session_state.bracket_data.empty:
        st.dataframe(st.session_state.bracket_data)

# Tab 4: Export
with tabs[4]:
    st.subheader("\U0001F4E4 Export")
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# Tab 5: Predict Bracket
with tabs[5]:
    st.subheader("\U0001F52E Predict Bracket")
    if st.session_state.bracket_data.empty:
        st.warning("Bracket prediction will be available once the field of 16 is set.")
    else:
        username = st.text_input("Enter your name or initials:")
        if username:
            st.markdown("Make your picks before the tournament begins. We'll compare them against actual results!")
            bracket_df = st.session_state.bracket_data
            left = bracket_df.iloc[0:8].reset_index(drop=True)
            right = bracket_df.iloc[8:16].reset_index(drop=True)

            st.markdown("### \U0001F7E6 Left Side Predictions")
            pred_qf_left = []
            for i in range(0, 8, 2):
                p1, p2 = left.iloc[i], left.iloc[i+1]
                pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PL16_{i}_{username}")
                pred_qf_left.append(p1 if pick == label(p1) else p2)

            pred_sf_left = []
            for i in range(0, len(pred_qf_left), 2):
                p1, p2 = pred_qf_left[i], pred_qf_left[i+1]
                pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PLQF_{i}_{username}")
                pred_sf_left.append(p1 if pick == label(p1) else p2)

            finalist_left = st.radio(f"Left Finalist:", [label(pred_sf_left[0]), label(pred_sf_left[1])], key=f"PLSF_{username}")
            finalist_left = pred_sf_left[0] if finalist_left == label(pred_sf_left[0]) else pred_sf_left[1]

            st.markdown("### \U0001F7E5 Right Side Predictions")
            pred_qf_right = []
            for i in range(0, 8, 2):
                p1, p2 = right.iloc[i], right.iloc[i+1]
                pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PR16_{i}_{username}")
                pred_qf_right.append(p1 if pick == label(p1) else p2)

            pred_sf_right = []
            for i in range(0, len(pred_qf_right), 2):
                p1, p2 = pred_qf_right[i], pred_qf_right[i+1]
                pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PRQF_{i}_{username}")
                pred_sf_right.append(p1 if pick == label(p1) else p2)

            finalist_right = st.radio(f"Right Finalist:", [label(pred_sf_right[0]), label(pred_sf_right[1])], key=f"PRSF_{username}")
            finalist_right = pred_sf_right[0] if finalist_right == label(pred_sf_right[0]) else pred_sf_right[1]

            champion = st.radio(f"\U0001F3AF Predict the Champion:", [label(finalist_left), label(finalist_right)], key=f"PickChamp_{username}")
            champion_final = finalist_left if champion == label(finalist_left) else finalist_right

            if st.button("Submit My Bracket"):
                st.session_state.user_predictions[username] = {
                    "finalist_left": finalist_left['name'],
                    "finalist_right": finalist_right['name'],
                    "champion": champion_final['name']
                }
                st.success("Your bracket has been submitted!")

        if st.session_state.user_predictions:
            st.subheader("\U0001F4C8 Current Predictions")
            for user, picks in st.session_state.user_predictions.items():
                st.markdown(f"**{user}** picked _{picks['champion']}_ to win")
