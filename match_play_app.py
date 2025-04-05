import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import json
import os

st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# ---- File Paths for Persistent Storage ----
MATCH_RESULTS_FILE = "match_results.json"
PREDICTIONS_FILE = "user_predictions.json"

# ---- Load/Save Functions ----
def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ---- Global Password Protection ----
ADMIN_PASSWORD = st.secrets["admin_password"]
GENERAL_PASSWORD = st.secrets["general_password"]

# ---- Persistent Storage ----
if "match_results" not in st.session_state:
    st.session_state.match_results = load_json(MATCH_RESULTS_FILE)
if "user_predictions" not in st.session_state:
    st.session_state.user_predictions = load_json(PREDICTIONS_FILE)

# ---- Initialize Session States ----
st.session_state.setdefault("app_authenticated", False)
st.session_state.setdefault("authenticated", False)

# ---- General Access Password ----
if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament - Restricted Access")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == GENERAL_PASSWORD:
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
        if pwd_input == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.sidebar.success("Logged in as admin.")
        else:
            st.sidebar.error("Incorrect Admin Password.")
else:
    st.sidebar.success("✅ Admin logged in.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False

# ---- Load Pods ----
@st.cache_data
def load_pods_from_secrets():
    raw_pods = st.secrets["pods"]
    parsed_pods = {}
    for pod_key, players in raw_pods.items():
        pod_name = pod_key.replace("_", " ")
        parsed_pods[pod_name] = [
            {
                "name": name.replace("_", " "),
                "handicap": float(hcp) if str(hcp).replace('.', '', 1).lstrip('-').isdigit() else None
            }
            for name, hcp in players.items()
        ]
    return parsed_pods

pods = load_pods_from_secrets()

margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

# ---- Match Simulation ----
def simulate_matches(pod_name, players):
    results = defaultdict(lambda: {"points": 0, "margin": 0})
    match_data = st.session_state.match_results.get(pod_name, {})

    num_players = len(players)
    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1, p2 = players[i], players[j]
            col_key = f"{p1['name']} vs {p2['name']}"
            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] is not None else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] is not None else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if st.session_state.authenticated:
                winner = st.radio(f"Who won?", [p1['name'], p2['name'], "Tie"], key=col_key, index=[p1['name'], p2['name'], "Tie"].index(match_data.get(col_key, {}).get("winner", "Tie")))
                margin = 0
                if winner != "Tie":
                    result_key = col_key + "_result"
                    selected_result = match_data.get(col_key, {}).get("result", "1 up")
                    result_str = st.selectbox("Select Match Result (Win Margin)", options=list(margin_lookup.keys()), key=result_key, index=list(margin_lookup.keys()).index(selected_result))
                    margin = margin_lookup[result_str]
                else:
                    result_str = "Tie"
                match_data[col_key] = {"winner": winner, "result": result_str, "margin": margin}
                st.session_state.match_results[pod_name] = match_data
                save_json(st.session_state.match_results, MATCH_RESULTS_FILE)
            elif col_key in match_data:
                result = match_data[col_key]
                st.info(f"Result: {result['winner']} won ({result['result']})" if result['winner'] != "Tie" else "Match tied.")
                winner = result['winner']
                margin = result['margin']
            else:
                winner = "Tie"
                margin = 0
                st.info("Result not entered yet.")

            if winner == p1['name']:
                results[p1['name']]['points'] += 1
                results[p1['name']]['margin'] += margin
                results[p2['name']]['margin'] -= margin
            elif winner == p2['name']:
                results[p2['name']]['points'] += 1
                results[p2['name']]['margin'] += margin
                results[p1['name']]['margin'] -= margin
            else:
                results[p1['name']]['points'] += 0.5
                results[p2['name']]['points'] += 0.5

    for player in players:
        player.update(results[player['name']])
    return players

# ---- Label Function ----
def label(player):
    return f"{player['name']} ({player['handicap']})"

# ---- Tabs ----
st.title("🏌️ Golf Match Play Tournament Dashboard")
tabs = st.tabs(["📁 Pods Overview", "📊 Group Stage", "📋 Standings", "🏆 Bracket", "📤 Export", "🔮 Predict Bracket"])

if "bracket_data" not in st.session_state:
    st.session_state.bracket_data = pd.DataFrame()

# Tab 0: Pods Overview
with tabs[0]:
    st.subheader("📁 All Pods and Player Handicaps")
    pod_names = list(pods.keys())
    num_cols = 3
    cols = st.columns(num_cols)

    for i, pod_name in enumerate(pod_names):
        col = cols[i % num_cols]
        with col:
            st.markdown(f"##### {pod_name}")
            df = pd.DataFrame(pods[pod_name])[['name', 'handicap']]
            df['handicap'] = df['handicap'].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "N/A")
            st.dataframe(df.rename(columns={"name": "Player", "handicap": "Handicap"}), use_container_width=True)

# Tab 1: Group Stage
with tabs[1]:
    st.subheader("📊 Group Stage - Match Results")
    pod_results = {}
    for pod_name, players in pods.items():
        with st.expander(pod_name):
            updated_players = simulate_matches(pod_name, players)
            pod_results[pod_name] = pd.DataFrame(updated_players)

    if st.session_state.authenticated:
        if st.button("Calculate Pod Winners"):
            winners, second_place = [], []
            for pod_name, df in pod_results.items():
                sorted_players = df.sort_values(by=["points", "margin"], ascending=False).reset_index(drop=True)
                winners.append({"pod": pod_name, **sorted_players.iloc[0].to_dict()})
                second_place.append(sorted_players.iloc[1].to_dict())
            top_3 = sorted(second_place, key=lambda x: (x["points"], x["margin"]), reverse=True)[:3]
            final_players = winners + top_3
            bracket_df = pd.DataFrame(final_players)
            bracket_df.index = [f"Seed {i+1}" for i in range(16)]
            st.session_state.bracket_data = bracket_df
            st.success("Pod winners and bracket seeded.")
    else:
        st.info("🔒 Only admin can calculate pod winners.")

# Tab 2: Standings
with tabs[2]:
    st.subheader("📋 Standings")
    if not st.session_state.bracket_data.empty:
        st.dataframe(st.session_state.bracket_data, use_container_width=True)

# Tab 4: Export
with tabs[4]:
    st.subheader("📤 Export")
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# Tab 5: Predict Bracket
with tabs[5]:
    st.subheader("🔮 Predict Bracket")
    if st.session_state.bracket_data.empty:
        st.warning("Bracket prediction will be available once the field of 16 is set.")
    else:
        username = st.text_input("Enter your name or initials:")
        if username:
            bracket_df = st.session_state.bracket_data
            left = bracket_df.iloc[0:8].reset_index(drop=True)
            right = bracket_df.iloc[8:16].reset_index(drop=True)

            pred_qf_left, pred_sf_left = [], []
            for i in range(0, 8, 2):
                p1, p2 = left.iloc[i], left.iloc[i+1]
                pick = st.radio(f"L16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PL16_{i}_{username}")
                pred_qf_left.append(p1 if pick == label(p1) else p2)
            for i in range(0, len(pred_qf_left), 2):
                p1, p2 = pred_qf_left[i], pred_qf_left[i+1]
                pick = st.radio(f"LQF: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PLQF_{i}_{username}")
                pred_sf_left.append(p1 if pick == label(p1) else p2)
            finalist_left = pred_sf_left[0] if st.radio("Finalist (Left):", [label(pred_sf_left[0]), label(pred_sf_left[1])], key=f"PLSF_{username}") == label(pred_sf_left[0]) else pred_sf_left[1]

            pred_qf_right, pred_sf_right = [], []
            for i in range(0, 8, 2):
                p1, p2 = right.iloc[i], right.iloc[i+1]
                pick = st.radio(f"R16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PR16_{i}_{username}")
                pred_qf_right.append(p1 if pick == label(p1) else p2)
            for i in range(0, len(pred_qf_right), 2):
                p1, p2 = pred_qf_right[i], pred_qf_right[i+1]
                pick = st.radio(f"RQF: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PRQF_{i}_{username}")
                pred_sf_right.append(p1 if pick == label(p1) else p2)
            finalist_right = pred_sf_right[0] if st.radio("Finalist (Right):", [label(pred_sf_right[0]), label(pred_sf_right[1])], key=f"PRSF_{username}") == label(pred_sf_right[0]) else pred_sf_right[1]

            champion_final = finalist_left if st.radio("🏹 Predict Champion:", [label(finalist_left), label(finalist_right)], key=f"PickChamp_{username}") == label(finalist_left) else finalist_right

            if st.button("Submit My Bracket"):
                st.session_state.user_predictions[username] = {
                    "finalist_left": finalist_left['name'],
                    "finalist_right": finalist_right['name'],
                    "champion": champion_final['name']
                }
                save_json(st.session_state.user_predictions, PREDICTIONS_FILE)
                st.success("Your bracket has been submitted!")

        if st.session_state.user_predictions:
            st.subheader("📈 Current Predictions")
            for user, picks in st.session_state.user_predictions.items():
                st.markdown(f"**{user}** picked _{picks['champion']}_ to win")
