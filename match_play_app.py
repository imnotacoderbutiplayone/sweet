import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import json
import os

# --- Utility functions for persistence ---
from supabase import create_client, Client
import streamlit as st
import pandas as pd
from datetime import datetime

# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- Save bracket data to Supabase ---
def save_bracket_data(df):
    try:
        json_data = df.to_json(orient="split")
        response = supabase.table("bracket_data").insert({"json_data": json_data}).execute()
        return response
    except Exception as e:
        st.error("❌ Failed to save bracket data to Supabase")
        st.code(str(e))
        return None

# --- Save one match result to Supabase ---
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
        response = supabase.table("match_results").insert(data).execute()
        return response
    except Exception as e:
        st.error("❌ Error saving match result to Supabase")
        st.code(str(e))
        return None

margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

# --- Load all match results from Supabase ---
from collections import defaultdict

def load_match_results():
    try:
        response = supabase.table("match_results").select("*").order("created_at", desc=True).execute()

        match_dict = defaultdict(dict)
        for r in response.data:
            match_key = f"{r['pod']}|{r['player1']} vs {r['player2']}"
            match_dict[match_key] = {
                "winner": r["winner"],
                "margin": next((v for k, v in margin_lookup.items() if k == r["margin"]), 0)
            }

        return dict(match_dict)

    except Exception as e:
        st.error("❌ Supabase error loading match results")
        st.code(str(e))
        return {}

# --- Load all predictions from Supabase ---
def load_predictions_from_supabase():
    try:
        response = supabase.table("predictions").select("*").order("timestamp", desc=True).execute()
        return response.data
    except Exception as e:
        st.error("❌ Failed to load predictions from Supabase")
        st.code(str(e))
        return []


# --- Send Prediction to Database ---
def save_prediction_to_supabase(name, finalist_left, finalist_right, champion):
    try:
        data = {
            "name": name,
            "finalist_left": finalist_left,
            "finalist_right": finalist_right,
            "champion": champion,
            "timestamp": datetime.utcnow().isoformat()
        }
        response = supabase.table("predictions").insert(data).execute()
        return response
    except Exception as e:
        st.error("❌ Failed to save prediction to Supabase")
        st.code(str(e))
        return None


# --- Streamlit App Config and File Paths ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

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


# Load shared bracket data
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


# Load match results (optional extension later)
if "match_results" not in st.session_state:
    st.session_state.match_results = load_match_results() or {}

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
            st.sidebar.success("✅ Logged in as admin.")
            st.rerun()
        else:
            st.sidebar.error("❌ Incorrect Admin Password.")
else:
    st.sidebar.success("✅ Admin logged in.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

    # --- ⚙️ Admin Tools ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Admin Tools")

    st.sidebar.warning("This will permanently delete ALL match results and bracket data.")

    confirm_reset = st.sidebar.text_input("Type RESET to confirm", key="confirm_reset")

    if st.sidebar.button("🧨 Reset Tournament Data"):
        if confirm_reset.strip().upper() == "RESET":
            for file in [RESULTS_FILE, BRACKET_FILE]:
                if os.path.exists(file):
                    os.remove(file)

            st.session_state.match_results = {}
            st.session_state.bracket_data = pd.DataFrame()
            st.session_state.tiebreak_selections = {}
            st.session_state.tiebreaks_resolved = False
            st.session_state.user_predictions = {}

            st.success("✅ Tournament data has been reset. Refreshing...")
            st.rerun()
        else:
            st.sidebar.error("❌ You must type RESET to confirm.")

# ---- Link to Golf Score Probability Calculator ----
st.sidebar.markdown(
    """
    <a href="https://ndddxgvdvvxzbtif33qmkr.streamlit.app" target="_blank">
        🔮 Golf Score Probability Calculator
    </a>
    """, unsafe_allow_html=True
)


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


import re
import hashlib
from collections import defaultdict

def sanitize_key(text):
    """Sanitize and hash widget keys to avoid Streamlit duplication."""
    cleaned = re.sub(r'\W+', '_', text)  # Replace non-alphanumerics with underscores
    hashed = hashlib.md5(text.encode()).hexdigest()[:8]  # Short hash for uniqueness
    return f"{cleaned}_{hashed}"

def simulate_matches(players, pod_name, source=""):
    results = defaultdict(lambda: {"points": 0, "margin": 0})
    num_players = len(players)

    if "match_results" not in st.session_state:
        st.session_state.match_results = load_match_results()

    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1, p2 = players[i], players[j]

            # Create consistent, unique match key
            player_names = sorted([p1['name'], p2['name']])
            raw_key = f"{source}_{pod_name}|{player_names[0]} vs {player_names[1]}"
            base_key = sanitize_key(raw_key)

            entry_key = f"{base_key}_checkbox"
            winner_key = f"{base_key}_winner"
            margin_key = f"{base_key}_margin"

            match_key = f"{pod_name}|{p1['name']} vs {p2['name']}"
            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] is not None else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] is not None else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if st.session_state.authenticated:
                entered = st.checkbox("Enter result for this match", key=entry_key)
            else:
                entered = False

            if entered:
                prev_result = st.session_state.match_results.get(match_key, {})
                prev_winner = prev_result.get("winner", "Tie")
                margin_val = prev_result.get("margin", 0)
                prev_margin = next((k for k, v in margin_lookup.items() if v == margin_val), "1 up")

                winner = st.radio(
                    "Who won?",
                    [p1['name'], p2['name'], "Tie"],
                    index=[p1['name'], p2['name'], "Tie"].index(prev_winner),
                    key=winner_key
                )

                margin = 0
                if winner != "Tie":
                    result_str = st.selectbox(
                        "Select Match Result (Win Margin)",
                        options=list(margin_lookup.keys()),
                        index=list(margin_lookup.keys()).index(prev_margin),
                        key=margin_key
                    )
                    margin = margin_lookup[result_str]
                else:
                    result_str = "Tie"

                st.session_state.match_results[match_key] = {
                    "winner": winner,
                    "margin": margin
                }

                save_match_result(pod_name, p1['name'], p2['name'], winner, result_str)

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
            else:
                st.info("🔒 Only admin can enter match results.")

    for player in players:
        player.update(results[player['name']])
    return players



# --- Label Helper ---
def label(player):
    return f"{player['name']} ({player['handicap']})"


st.title("\U0001F3CC️ Golf Match Play Tournament Dashboard")
tabs = st.tabs([
    "📁 Pods Overview", 
    "📊 Group Stage", 
    "📋 Standings", 
    "🏆 Bracket", 
    "📤 Export", 
    "🔮 Predict Bracket", 
    "🗃️ Results Log",
    "🏅 Leaderboard"  # 👈 NEW TAB
])


if "bracket_data" not in st.session_state:
    bracket_df = load_bracket_data()
    st.session_state.bracket_data = bracket_df
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
            updated_players = simulate_matches(players, pod_name, source="group_stage")
            pod_results[pod_name] = pd.DataFrame(updated_players)

    # --- Helper: Check if any match results exist for this pod ---
    def pod_has_results(pod_name):
        return any(key.startswith(f"{pod_name}|") for key in st.session_state.match_results)

    # --- Tiebreak Selection + Bracket Finalization ---
    if st.session_state.authenticated:
        st.header("\U0001F9EE Step 1: Review & Resolve Tiebreakers")

        if "tiebreak_selections" not in st.session_state:
            st.session_state.tiebreak_selections = {}
        if "tiebreaks_resolved" not in st.session_state:
            st.session_state.tiebreaks_resolved = False

        pod_winners_temp, pod_second_temp = [], []
        unresolved = False

        for pod_name, df in pod_results.items():
            # Skip pods with no match results
            if "points" not in df.columns:
                st.info(f"📭 No match results entered yet for {pod_name}.")
                continue

            df["points"] = df.get("points", 0)
            df["margin"] = df.get("margin", 0)

            if not df["points"].any() and not df["margin"].any():
                st.info(f"📭 No match results entered yet for {pod_name}.")
                continue

            sorted_players = df.sort_values(by=["points", "margin"], ascending=False).reset_index(drop=True)

            # --- First Place ---
            top_score = sorted_players.iloc[0]["points"]
            top_margin = sorted_players.iloc[0]["margin"]
            tied_first = sorted_players[
                (sorted_players["points"] == top_score) &
                (sorted_players["margin"] == top_margin)
            ]

            if len(tied_first) > 1:
                st.warning(f"🔁 Tie for 1st in {pod_name}")
                options = tied_first["name"].tolist()
                selected = st.radio(
                    f"Select 1st place in {pod_name}:",
                    options,
                    key=f"{pod_name}_1st"
                )
                if selected:
                    st.session_state.tiebreak_selections[f"{pod_name}_1st"] = selected
                else:
                    unresolved = True
            else:
                st.session_state.tiebreak_selections[f"{pod_name}_1st"] = tied_first.iloc[0]["name"]

            # --- Second Place ---
            winner_name = st.session_state.tiebreak_selections.get(f"{pod_name}_1st")
            remaining = sorted_players[sorted_players["name"] != winner_name].reset_index(drop=True)

            if remaining.empty:
                st.warning(f"⚠️ Not enough players to determine second place in {pod_name}")
                continue

            second_score = remaining.iloc[0]["points"]
            second_margin = remaining.iloc[0]["margin"]
            tied_second = remaining[
                (remaining["points"] == second_score) &
                (remaining["margin"] == second_margin)
            ]

            if len(tied_second) > 1:
                st.warning(f"🔁 Tie for 2nd in {pod_name}")
                options = tied_second["name"].tolist()
                selected = st.radio(
                    f"Select 2nd place in {pod_name}:",
                    options,
                    key=f"{pod_name}_2nd"
                )
                if selected:
                    st.session_state.tiebreak_selections[f"{pod_name}_2nd"] = selected
                else:
                    unresolved = True
            else:
                st.session_state.tiebreak_selections[f"{pod_name}_2nd"] = tied_second.iloc[0]["name"]

        # --- Completion Check ---
        if unresolved:
            st.error("⛔ Please resolve all tiebreakers before finalizing.")
            st.session_state.tiebreaks_resolved = False
        else:
            st.success("✅ All tiebreakers selected.")
            st.session_state.tiebreaks_resolved = True

        # --- Finalize Bracket Button ---
        if st.session_state.get("tiebreaks_resolved", False):
            if st.button("🏁 Finalize Bracket and Seed Field"):
                winners, second_place = [], []

                for pod_name, df in pod_results.items():
                    if not pod_has_results(pod_name):
                        continue

                    first_name = st.session_state.tiebreak_selections.get(f"{pod_name}_1st")
                    second_name = st.session_state.tiebreak_selections.get(f"{pod_name}_2nd")

                    if not first_name or not second_name:
                        continue

                    first_row = df[df["name"] == first_name].iloc[0].to_dict()
                    second_row = df[df["name"] == second_name].iloc[0].to_dict()

                    winners.append({"pod": pod_name, **first_row})
                    second_place.append(second_row)

                top_3 = sorted(second_place, key=lambda x: (x["points"], x["margin"]), reverse=True)[:3]
                final_players = winners + top_3

                bracket_df = pd.DataFrame(final_players)
                bracket_df.index = [f"Seed {i+1}" for i in range(len(bracket_df))]

                st.session_state.bracket_data = bracket_df
                save_bracket_data(bracket_df)

                st.success("✅ Bracket finalized and seeded.")
                st.write("📊 Final Bracket", st.session_state.bracket_data)


# --- Tab 3: Bracket (Admin – Confirm Winners) ---
with tabs[3]:
    st.subheader("🏆 Bracket")
    
    if st.session_state.bracket_data.empty:
        st.warning("Please calculate bracket seeding from the Group Stage tab first.")
    else:
        bracket_df = st.session_state.bracket_data
        left = bracket_df.iloc[0:8].reset_index(drop=True)
        right = bracket_df.iloc[8:16].reset_index(drop=True)
        
        col1, col2 = st.columns(2)
        
        # =============================
        # LEFT SIDE – Admin Confirmation
        # =============================
        with col1:
            st.markdown("### 🟦 Left Side")
            
            # ---- Round of 16 (Left) ----
            st.markdown("#### 🏁 Round of 16")
            if "r16_left" not in st.session_state:
                r16_left_choices = {}
                for i in range(0, len(left), 2):
                    p1, p2 = left.iloc[i], left.iloc[i + 1]
                    match_label = f"{label(p1)} vs {label(p2)}"
                    if st.session_state.authenticated:
                        choice = st.radio(match_label, [label(p1), label(p2)], key=f"R16L_{i}")
                        r16_left_choices[i] = p1 if choice == label(p1) else p2
                    else:
                        st.markdown(f"🔒 {match_label} _(Admin only)_")
                if st.button("Confirm Round of 16 (Left Side)"):
                    st.session_state.r16_left = [r16_left_choices[i] for i in sorted(r16_left_choices)]
                    st.success("Round of 16 winners (Left) confirmed!")
            else:
                st.info("Round of 16 winners (Left) have been confirmed:")
                for p in st.session_state.r16_left:
                    st.write(label(p))
            
            # ---- Quarterfinals (Left) ----
            st.markdown("#### 🥈 Quarterfinals")
            if "qf_left" not in st.session_state:
                if "r16_left" in st.session_state:
                    r16_left = st.session_state.r16_left
                    qf_left_choices = {}
                    for i in range(0, len(r16_left), 2):
                        if i + 1 < len(r16_left):
                            p1 = r16_left[i]
                            p2 = r16_left[i + 1]
                            match_label = f"QF: {label(p1)} vs {label(p2)}"
                            choice = st.radio(match_label, [label(p1), label(p2)], key=f"QFL_{i}")
                            qf_left_choices[i] = p1 if choice == label(p1) else p2
                    if st.button("Confirm Quarterfinals (Left Side)"):
                        st.session_state.qf_left = [qf_left_choices[i] for i in sorted(qf_left_choices)]
                        st.success("Quarterfinal winners (Left) confirmed!")
                else:
                    st.warning("Please confirm Round of 16 first.")
            else:
                st.info("Quarterfinal winners (Left) have been confirmed:")
                for p in st.session_state.qf_left:
                    st.write(label(p))
            
            # ---- Semifinals (Left) ----
            st.markdown("#### 🥇 Semifinals")
            if "sf_left" not in st.session_state:
                if "qf_left" in st.session_state:
                    qf_left = st.session_state.qf_left
                    sf_left_choices = {}
                    for i in range(0, len(qf_left), 2):
                        if i + 1 < len(qf_left):
                            p1 = qf_left[i]
                            p2 = qf_left[i + 1]
                            match_label = f"SF: {label(p1)} vs {label(p2)}"
                            choice = st.radio(match_label, [label(p1), label(p2)], key=f"SFL_{i}")
                            sf_left_choices[i] = p1 if choice == label(p1) else p2
                    if st.button("Confirm Semifinals (Left Side)"):
                        st.session_state.sf_left = [sf_left_choices[i] for i in sorted(sf_left_choices)]
                        st.success("Semifinal winner (Left) confirmed!")
                else:
                    st.warning("Please confirm Quarterfinals first.")
            else:
                st.info("Semifinal winner (Left) has been confirmed:")
                for p in st.session_state.sf_left:
                    st.write(label(p))
        
        # ==============================
        # RIGHT SIDE – Admin Confirmation
        # ==============================
        with col2:
            st.markdown("### 🟥 Right Side")
            
            # ---- Round of 16 (Right) ----
            st.markdown("#### 🏁 Round of 16")
            if "r16_right" not in st.session_state:
                r16_right_choices = {}
                for i in range(0, len(right), 2):
                    p1, p2 = right.iloc[i], right.iloc[i + 1]
                    match_label = f"{label(p1)} vs {label(p2)}"
                    if st.session_state.authenticated:
                        choice = st.radio(match_label, [label(p1), label(p2)], key=f"R16R_{i}")
                        r16_right_choices[i] = p1 if choice == label(p1) else p2
                    else:
                        st.markdown(f"🔒 {match_label} _(Admin only)_")
                if st.button("Confirm Round of 16 (Right Side)"):
                    st.session_state.r16_right = [r16_right_choices[i] for i in sorted(r16_right_choices)]
                    st.success("Round of 16 winners (Right) confirmed!")
            else:
                st.info("Round of 16 winners (Right) have been confirmed:")
                for p in st.session_state.r16_right:
                    st.write(label(p))
            
            # ---- Quarterfinals (Right) ----
            st.markdown("#### 🥈 Quarterfinals")
            if "qf_right" not in st.session_state:
                if "r16_right" in st.session_state:
                    r16_right = st.session_state.r16_right
                    qf_right_choices = {}
                    for i in range(0, len(r16_right), 2):
                        if i + 1 < len(r16_right):
                            p1 = r16_right[i]
                            p2 = r16_right[i + 1]
                            match_label = f"QF: {label(p1)} vs {label(p2)}"
                            choice = st.radio(match_label, [label(p1), label(p2)], key=f"QFR_{i}")
                            qf_right_choices[i] = p1 if choice == label(p1) else p2
                    if st.button("Confirm Quarterfinals (Right Side)"):
                        st.session_state.qf_right = [qf_right_choices[i] for i in sorted(qf_right_choices)]
                        st.success("Quarterfinal winners (Right) confirmed!")
                else:
                    st.warning("Please confirm Round of 16 first.")
            else:
                st.info("Quarterfinal winners (Right) have been confirmed:")
                for p in st.session_state.qf_right:
                    st.write(label(p))
            
            # ---- Semifinals (Right) ----
            st.markdown("#### 🥇 Semifinals")
            if "sf_right" not in st.session_state:
                if "qf_right" in st.session_state:
                    qf_right = st.session_state.qf_right
                    sf_right_choices = {}
                    for i in range(0, len(qf_right), 2):
                        if i + 1 < len(qf_right):
                            p1 = qf_right[i]
                            p2 = qf_right[i + 1]
                            match_label = f"SF: {label(p1)} vs {label(p2)}"
                            choice = st.radio(match_label, [label(p1), label(p2)], key=f"SFR_{i}")
                            sf_right_choices[i] = p1 if choice == label(p1) else p2
                    if st.button("Confirm Semifinals (Right Side)"):
                        st.session_state.sf_right = [sf_right_choices[i] for i in sorted(sf_right_choices)]
                        st.success("Semifinal winner (Right) confirmed!")
                else:
                    st.warning("Please confirm Quarterfinals first.")
            else:
                st.info("Semifinal winner (Right) has been confirmed:")
                for p in st.session_state.sf_right:
                    st.write(label(p))
        
        # ============================
        # FINAL MATCH – Champion Confirmation
        # ============================
        st.markdown("### 🏁 Final Match")
        if st.session_state.authenticated and "sf_left" in st.session_state and "sf_right" in st.session_state:
            finalist_left = st.session_state.sf_left[0] if st.session_state.sf_left else None
            finalist_right = st.session_state.sf_right[0] if st.session_state.sf_right else None
            if finalist_left is not None and finalist_right is not None:
                final_choice = st.radio("Select the Final Champion:",
                                        [label(finalist_left), label(finalist_right)],
                                        key="FinalMatch")
                if st.button("Confirm Final Match"):
                    champion = finalist_left if final_choice == label(finalist_left) else finalist_right
                    st.session_state.champion_name = champion["name"]
                    st.session_state.finalist_left_name = finalist_left["name"]
                    st.session_state.finalist_right_name = finalist_right["name"]
                    st.success(f"Final Champion Confirmed: {champion['name']} ({champion['handicap']})")
                    
                    # Persist final results to Supabase for all users to see:
                    final_results = {
                        "r16_left": json.dumps([p["name"] for p in st.session_state.get("r16_left", [])]),
                        "r16_right": json.dumps([p["name"] for p in st.session_state.get("r16_right", [])]),
                        "qf_left": json.dumps([p["name"] for p in st.session_state.get("qf_left", [])]),
                        "qf_right": json.dumps([p["name"] for p in st.session_state.get("qf_right", [])]),
                        "sf_left": json.dumps([p["name"] for p in st.session_state.get("sf_left", [])]),
                        "sf_right": json.dumps([p["name"] for p in st.session_state.get("sf_right", [])]),
                        "champion": champion["name"],
                        "finalist_left": finalist_left["name"],
                        "finalist_right": finalist_right["name"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    supabase.table("final_results").insert(final_results).execute()
        else:
            st.markdown("🔒 Final match — _(Admin only)_")



# Tab 3: Standings
# Tab 2: Standings
with tabs[2]:
    st.subheader("📋 Standings")

    if "match_results" not in st.session_state:
        st.session_state.match_results = load_match_results()

    pod_results = {}

    for pod_name, players in pods.items():
        updated_players = []
        for player in players:
            name = player['name']
            total_points = 0
            total_margin = 0

            for key, result in st.session_state.match_results.items():
                if key.startswith(f"{pod_name}|"):
                    if name in key:
                        if result["winner"] == name:
                            total_points += 1
                            total_margin += result["margin"]
                        elif result["winner"] == "Tie":
                            total_points += 0.5
                        else:
                            total_margin -= result["margin"]

            updated_players.append({
                "name": name,
                "handicap": player["handicap"],
                "Points": total_points,
                "Margin": total_margin
            })

        df = pd.DataFrame(updated_players)
        if not df.empty:
            df = df.sort_values(by=["Points", "Margin"], ascending=False)
            df.rename(columns={"name": "Player", "handicap": "Handicap"}, inplace=True)
            pod_results[pod_name] = df

    if pod_results:
        for pod_name, df in pod_results.items():
            with st.expander(f"📦 {pod_name} Standings", expanded=True):
                st.dataframe(df, use_container_width=True)
    else:
        st.info("📭 No match results have been entered yet.")



# Tab 4: Export
with tabs[4]:
    st.subheader("\U0001F4E4 Export")
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# Tab 5: Predict Bracket
with tabs[5]:
    st.subheader("🔮 Predict Bracket")

    # --- Clear the full_name input if a prediction was just submitted ---
    if st.session_state.get("prediction_submitted", False):
        if "full_name" in st.session_state:
            del st.session_state["full_name"]
        st.session_state.prediction_submitted = False

    if st.session_state.bracket_data.empty or len(st.session_state.bracket_data) < 16:
        st.warning("Bracket prediction will be available once the field of 16 is set.")
    else:
        bracket_df = st.session_state.bracket_data
        left = bracket_df.iloc[0:8].reset_index(drop=True)
        right = bracket_df.iloc[8:16].reset_index(drop=True)

        full_name = st.text_input("Enter your full name to submit a prediction:", key="full_name")

        if full_name.strip():
            user_name = full_name.strip().lower()

            # Load all predictions and normalize names
            try:
                existing = supabase.table("predictions").select("name").execute()
                submitted_names = [row["name"].strip().lower() for row in existing.data]
            except Exception as e:
                st.error("❌ Failed to check existing predictions")
                st.code(str(e))
                st.stop()

            if user_name in submitted_names:
                st.warning("You've already submitted a bracket. Only one entry per name is allowed.")
            else:
                st.markdown("### 🟦 Left Side Predictions")
                pred_r16_left, pred_qf_left, pred_sf_left = [], [], []

                for i in range(0, 8, 2):
                    p1, p2 = left.iloc[i], left.iloc[i + 1]
                    pick = st.radio(
                        f"Round of 16: {label(p1)} vs {label(p2)}",
                        [label(p1), label(p2)],
                        key=f"PL16_{i}_{full_name}"
                    )
                    pred_r16_left.append(p1 if pick == label(p1) else p2)

                for i in range(0, len(pred_r16_left), 2):
                    if i + 1 < len(pred_r16_left):
                        p1, p2 = pred_r16_left[i], pred_r16_left[i + 1]
                        pick = st.radio(
                            f"Quarterfinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PLQF_{i}_{full_name}"
                        )
                        pred_qf_left.append(p1 if pick == label(p1) else p2)

                for i in range(0, len(pred_qf_left), 2):
                    if i + 1 < len(pred_qf_left):
                        p1, p2 = pred_qf_left[i], pred_qf_left[i + 1]
                        pick = st.radio(
                            f"Semifinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PLSF_{i}_{full_name}"
                        )
                        pred_sf_left.append(p1 if pick == label(p1) else p2)

                finalist_left = pred_sf_left[0] if len(pred_sf_left) == 1 else None

                st.markdown("### 🟥 Right Side Predictions")
                pred_r16_right, pred_qf_right, pred_sf_right = [], [], []

                for i in range(0, 8, 2):
                    p1, p2 = right.iloc[i], right.iloc[i + 1]
                    pick = st.radio(
                        f"Round of 16: {label(p1)} vs {label(p2)}",
                        [label(p1), label(p2)],
                        key=f"PR16_{i}_{full_name}"
                    )
                    pred_r16_right.append(p1 if pick == label(p1) else p2)

                for i in range(0, len(pred_r16_right), 2):
                    if i + 1 < len(pred_r16_right):
                        p1, p2 = pred_r16_right[i], pred_r16_right[i + 1]
                        pick = st.radio(
                            f"Quarterfinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PRQF_{i}_{full_name}"
                        )
                        pred_qf_right.append(p1 if pick == label(p1) else p2)

                for i in range(0, len(pred_qf_right), 2):
                    if i + 1 < len(pred_qf_right):
                        p1, p2 = pred_qf_right[i], pred_qf_right[i + 1]
                        pick = st.radio(
                            f"Semifinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PRSF_{i}_{full_name}"
                        )
                        pred_sf_right.append(p1 if pick == label(p1) else p2)

                finalist_right = pred_sf_right[0] if len(pred_sf_right) == 1 else None

                champion_final = None
                if finalist_left is not None and finalist_right is not None:
                    st.markdown("### 🏁 Final Match")
                    champ_label = st.radio(
                        "🏆 Predict the Champion:",
                        [label(finalist_left), label(finalist_right)],
                        key=f"PickChamp_{full_name}"
                    )
                    if champ_label:
                        champion_final = finalist_left if champ_label == label(finalist_left) else finalist_right

                # Only show the submit button if all selections are made
                if finalist_left is not None and finalist_right is not None and champion_final is not None:
                    if st.button("🚀 Submit My Bracket Prediction"):
                        try:
                            prediction_entry = {
                                "name": full_name.strip(),
                                "timestamp": datetime.utcnow().isoformat(),
                                "champion": champion_final["name"],
                                "finalist_left": finalist_left["name"],
                                "finalist_right": finalist_right["name"],
                                "r16_left": json.dumps([p["name"] for p in pred_r16_left]),
                                "r16_right": json.dumps([p["name"] for p in pred_r16_right]),
                                "qf_left": json.dumps([p["name"] for p in pred_qf_left]),
                                "qf_right": json.dumps([p["name"] for p in pred_qf_right]),
                            }
                            supabase.table("predictions").insert(prediction_entry).execute()
                            st.success("✅ Your bracket prediction has been submitted!")
                            # Set a flag to clear the full_name input on next run
                            st.session_state.prediction_submitted = True
                            st.rerun()
                        except Exception as e:
                            st.error("❌ Error saving your prediction.")
                            st.code(str(e))
                else:
                    st.info("📋 Fill out all predictions and pick a champion to unlock the Submit button.")




# Tab 6: Results Log
with tabs[6]:
    st.subheader("🗃️ Match Results Log")

    match_results = st.session_state.get("match_results", {})

    if not match_results:
        st.info("No match results have been entered yet.")
    else:
        # Convert dict into a DataFrame
        data = []
        for key, result in match_results.items():
            if "|" not in key:
                continue  # Skip malformed or legacy keys

            pod_name, match_str = key.split("|", 1)
            try:
                player1, player2 = match_str.split(" vs ")
            except ValueError:
                continue  # Skip malformed match strings

            winner = result.get("winner", "Tie")
            margin = result.get("margin", 0)
            margin_text = next(
                (k for k, v in margin_lookup.items() if v == margin),
                "Tie" if winner == "Tie" else "1 up"
            )

            data.append({
                "Pod": pod_name,
                "Player 1": player1.strip(),
                "Player 2": player2.strip(),
                "Winner": winner,
                "Margin": margin_text
            })

        df = pd.DataFrame(data)
        df = df.sort_values(by=["Pod", "Player 1"])

        st.dataframe(df, use_container_width=True)

        # Optional: Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Match Results CSV", csv, "match_results.csv", "text/csv")

# Tab 7: Leaderboard
with tabs[7]:
    st.subheader("🏅 Prediction Leaderboard")

    try:
        predictions = supabase.table("predictions").select("*").execute().data
        if not predictions:
            st.info("No predictions submitted yet.")
        else:
            # Query the latest final results from the Supabase table
            final_results_data = supabase.table("final_results") \
                                       .select("*") \
                                       .order("timestamp", desc=True) \
                                       .limit(1) \
                                       .execute().data
            if not final_results_data or len(final_results_data) == 0:
                st.warning("Final results have not been confirmed yet. Leaderboard will update once a winner is finalized.")
            else:
                final_result = final_results_data[0]
                # Rebuild the actual results dictionary from the stored JSON data:
                actual_results = {
                    "r16_left": json.loads(final_result.get("r16_left", "[]")),
                    "r16_right": json.loads(final_result.get("r16_right", "[]")),
                    "qf_left": json.loads(final_result.get("qf_left", "[]")),
                    "qf_right": json.loads(final_result.get("qf_right", "[]")),
                    "sf_left": json.loads(final_result.get("sf_left", "[]")),
                    "sf_right": json.loads(final_result.get("sf_right", "[]")),
                    "champion": final_result.get("champion", "")
                }
    
                leaderboard = []
    
                for row in predictions:
                    name = row.get("name", "Unknown")
                    score = 0
                    
                    # --- Round-of-16 scoring (1 point per correct prediction) ---
                    try:
                        pred_r16_left = json.loads(row.get("r16_left", "[]"))
                    except Exception as e:
                        pred_r16_left = []
                    try:
                        pred_r16_right = json.loads(row.get("r16_right", "[]"))
                    except Exception as e:
                        pred_r16_right = []
                    
                    for actual, predicted in zip(actual_results["r16_left"], pred_r16_left):
                        if actual == predicted:
                            score += 1
                    for actual, predicted in zip(actual_results["r16_right"], pred_r16_right):
                        if actual == predicted:
                            score += 1
    
                    # --- Quarterfinals scoring (3 points per correct prediction) ---
                    try:
                        pred_qf_left = json.loads(row.get("qf_left", "[]"))
                    except Exception as e:
                        pred_qf_left = []
                    try:
                        pred_qf_right = json.loads(row.get("qf_right", "[]"))
                    except Exception as e:
                        pred_qf_right = []
                    
                    for actual, predicted in zip(actual_results["qf_left"], pred_qf_left):
                        if actual == predicted:
                            score += 3
                    for actual, predicted in zip(actual_results["qf_right"], pred_qf_right):
                        if actual == predicted:
                            score += 3
    
                    # --- Semifinals scoring (5 points per correct prediction) ---
                    try:
                        pred_sf_left = json.loads(row.get("sf_left", "[]"))
                    except Exception as e:
                        pred_sf_left = []
                    try:
                        pred_sf_right = json.loads(row.get("sf_right", "[]"))
                    except Exception as e:
                        pred_sf_right = []
                    
                    for actual, predicted in zip(actual_results["sf_left"], pred_sf_left):
                        if actual == predicted:
                            score += 5
                    for actual, predicted in zip(actual_results["sf_right"], pred_sf_right):
                        if actual == predicted:
                            score += 5
    
                    # --- Final match scoring (10 points for picking the champion) ---
                    if row.get("champion", "").strip() == actual_results["champion"]:
                        score += 10
    
                    leaderboard.append({
                        "Name": name,
                        "Score": score
                    })
    
                leaderboard_df = pd.DataFrame(leaderboard)
                leaderboard_df = leaderboard_df.sort_values(by="Score", ascending=False).reset_index(drop=True)
                st.dataframe(leaderboard_df, use_container_width=True)
                
    except Exception as e:
        st.error("❌ Error loading leaderboard.")
        st.code(str(e))
