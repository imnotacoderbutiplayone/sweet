import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import json
import os
import tempfile
import shutil

def safe_save(file_path, data):
    """Safely write JSON to a file using atomic write."""
    temp_file = tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(file_path))
    json.dump(data, temp_file)
    temp_file.close()
    shutil.move(temp_file.name, file_path)


# --- Utility functions for persistence ---
def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f)

def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


# --- Streamlit App Config and File Paths ---
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

# --- Load match results into session state (on app startup) ---
if "match_results" not in st.session_state:
    # Load results from file to session state
    st.session_state.match_results = load_json(RESULTS_FILE)  # This loads the saved results if they exist




# --- Load shared bracket data ---
# Load bracket properly
if "bracket_data" not in st.session_state:
    if os.path.exists(BRACKET_FILE):
        with open(BRACKET_FILE, "r") as f:
            json_str = f.read()
            st.session_state.bracket_data = pd.read_json(json_str, orient="split")
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

# ---- Admin Login ----
if not st.session_state.authenticated:
    st.sidebar.header("🔐 Admin Login")
    
    # Show the input box for admin login
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


# Sidebar Admin Login - Add Refresh Data Button
if st.session_state.authenticated:
    st.sidebar.subheader("Admin Actions")
    # Add the Refresh Data button
    if st.sidebar.button("Clear all Match Data "):
        # Reset session state
        st.session_state.bracket_data = pd.DataFrame()
        st.session_state.match_results = {}
        with open(BRACKET_FILE, "w") as f:
            f.write("{}")  # Safe empty content for pd.read_json
  # Clear the saved bracket data
        save_json(RESULTS_FILE, {})  # Clear the saved match results
        st.success("Data has been refreshed. All saved data cleared.  Please refresh your browswer.")
        
        # Clear the query params (instead of deprecated method)
        st.query_params = {}  # Reset any query parameters (useful if your app depends on them)

        # Stop execution to allow the admin to refresh manually
        st.stop()


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



# --- Streamlit App Configuration ---
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

# --- Load match results into session state (on app startup) ---
if "match_results" not in st.session_state:
    st.session_state.match_results = load_json(RESULTS_FILE)  # Load saved match results from file


# --- Admin logic (simulate matches and save results) ---
# Function to simulate matches and save results
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

                    # Save immediately after entry
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





# --- Label Helper ---
def label(player):
    return f"{player['name']} ({player['handicap']})"


st.title("\U0001F3CC️ Golf Match Play Tournament Dashboard")
tabs = st.tabs(["\U0001F4C1 Pods Overview", "\U0001F4CA Group Stage", "\U0001F4CB Standings", "\U0001F3C6 Bracket", "\U0001F4E4 Export", "\U0001F52E Predict Bracket"])

if "bracket_data" not in st.session_state:
    st.session_state.bracket_data = pd.DataFrame()
if "user_predictions" not in st.session_state:
    st.session_state.user_predictions = {}

# Tab 0: Pods Overview (Styled & No Index - Fixed)
with tabs[0]:
    st.subheader("📁 All Pods and Player Handicaps")
    pod_names = list(pods.keys())
    num_cols = 3
    cols = st.columns(num_cols)

    # CSS style for headers and alternating rows
    def style_table(df):
        styled = df.style.set_table_styles([
            {'selector': 'th',
             'props': [('background-color', '#4CAF50'),
                       ('color', 'white'),
                       ('font-size', '16px')]},
            {'selector': 'td',
             'props': [('font-size', '14px')]}
        ]).set_properties(**{
            'text-align': 'left',
            'padding': '6px'
        }).apply(lambda x: ['background-color: #f9f9f9' if i % 2 else 'background-color: white' for i in range(len(x))])
        return styled.hide(axis='index')  # Hide the index explicitly here

    for i, pod_name in enumerate(pod_names):
        col = cols[i % num_cols]
        with col:
            st.markdown(f"##### {pod_name}")
            df = pd.DataFrame(pods[pod_name])[["name", "handicap"]]
            df["handicap"] = df["handicap"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "N/A")
            df.rename(columns={"name": "Player", "handicap": "Handicap"}, inplace=True)
            styled_df = style_table(df)
            st.write(styled_df.to_html(escape=False), unsafe_allow_html=True)

# Tab 1: Group Stage
with tabs[1]:
    st.subheader("\U0001F4CA Group Stage - Match Results")
    pod_results = {}
    for pod_name, players in pods.items():
        with st.expander(pod_name):
            # Proceed without debug output
            if isinstance(players, list) and len(players) > 0:
                # If players is a non-empty list, proceed
                updated_players = simulate_matches(players, pod_name)
                pod_results[pod_name] = pd.DataFrame(updated_players)
            else:
                st.error(f"Error: Players list for {pod_name} is empty or not a list.")


    # Only allow Admin to calculate pod winners
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

        # Save properly
        with open(BRACKET_FILE, "w") as f:
            f.write(bracket_df.to_json(orient="split"))

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

    if st.session_state.match_results:  # Only display if match results are available
        all_results = []

        # Go through each pod's results and accumulate them
        for pod_name, pod_results in st.session_state.match_results.items():
            for player, stats in pod_results.items():
                all_results.append({
                    "Pod": pod_name,
                    "Player": player,
                    "Points": stats["points"],
                    "Margin": stats["margin"]
                })

        # Convert the results into a DataFrame
        standings = pd.DataFrame(all_results)

        if standings.empty:
            st.info("No matches have been played yet. Standings will update after the first match.")
        else:
            # Sort standings by points first, then margin
            standings = standings.sort_values(by=["Points", "Margin"], ascending=[False, False])
            st.dataframe(standings)
    else:
        st.info("No matches have been played yet. Standings will update after the first match.")



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
