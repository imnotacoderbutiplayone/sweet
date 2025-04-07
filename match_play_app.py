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

# --- Save one match result to Supabase ---
def save_match_result(pod, player1, player2, winner, margin):
    data = {
        "pod": pod,
        "player1": player1,
        "player2": player2,
        "winner": winner,
        "margin": margin,
        "timestamp": datetime.utcnow().isoformat()
    }
    response = supabase.table("match_results").insert(data).execute()
    if response.status_code != 201:
        st.error("❌ Error saving match result.")
    return response

# --- Load all match results from Supabase ---
from collections import defaultdict

def load_match_results():
    response = supabase.table("match_results").select("*").order("created_at", desc=True).execute()

    # ✅ Check for errors using the correct method
    if response.error:
        st.error("❌ Supabase error loading match results")
        st.code(response.error)
        return {}

    # ✅ Convert flat list into legacy match_key structure
    match_dict = defaultdict(dict)
    for r in response.data:
        match_key = f"{r['pod']}|{r['player1']} vs {r['player2']}"
        match_dict[match_key] = {
            "winner": r["winner"],
            "margin": next((v for k, v in margin_lookup.items() if k == r["margin"]), 0)
        }

    return dict(match_dict)


# --- Streamlit App Config and File Paths ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

def load_bracket_data():
    response = supabase.table("bracket_data").select("json_data").order("timestamp", desc=True).limit(1).execute()
    if response.status_code == 200 and response.data:
        return pd.read_json(response.data[0]["json_data"], orient="split")
    else:
        return pd.DataFrame()

# Load shared bracket data
def load_bracket_data():
    response = supabase.table("bracket_data").select("json_data").order("timestamp", desc=True).limit(1).execute()

    if response.status_code == 200 and response.data and len(response.data) > 0:
        try:
            return pd.read_json(response.data[0]["json_data"], orient="split")
        except Exception as e:
            st.error(f"🧨 JSON parsing error: {e}")
            st.code(response.data[0]["json_data"])
            return pd.DataFrame()
    else:
        st.info("ℹ️ No bracket data found yet in Supabase.")
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

# --- Test Supabase Insert ---
st.sidebar.markdown("---")
st.sidebar.subheader("🧪 Supabase Test")

if st.sidebar.button("🚀 Test Save to Supabase"):
    test_response = save_match_result(
        pod="Pod Test",
        player1="Player A",
        player2="Player B",
        winner="Player A",
        margin="2 and 1"
    )
    st.sidebar.write("Status Code:", test_response.status_code)
    st.sidebar.write("Response:", test_response.data)
    st.sidebar.write("Error:", test_response.error)

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


# --- Simulation Function ---
def simulate_matches(players, pod_name):
    results = defaultdict(lambda: {"points": 0, "margin": 0})
    num_players = len(players)

    if "match_results" not in st.session_state:
        st.session_state.match_results = load_match_results()

    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1, p2 = players[i], players[j]
            match_key = f"{pod_name}|{p1['name']} vs {p2['name']}"
            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] is not None else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] is not None else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if st.session_state.authenticated:
                entry_key = match_key + "_entered"
                entered = st.checkbox("Enter result for this match", key=entry_key)

                if entered:
                    # Pre-fill previous result
                    prev_result = st.session_state.match_results.get(match_key, {})
                    prev_winner = prev_result.get("winner", "Tie")
                    margin_val = prev_result.get("margin", 0)
                    prev_margin = next((k for k, v in margin_lookup.items() if v == margin_val), "1 up")

                    # Winner radio button
                    winner = st.radio(
                        f"Who won?",
                        [p1['name'], p2['name'], "Tie"],
                        index=[p1['name'], p2['name'], "Tie"].index(prev_winner),
                        key=match_key
                    )

                    # Margin selectbox
                    margin = 0
                    if winner != "Tie":
                        result_str = st.selectbox(
                            "Select Match Result (Win Margin)",
                            options=list(margin_lookup.keys()),
                            index=list(margin_lookup.keys()).index(prev_margin),
                            key=match_key + "_result"
                        )
                        margin = margin_lookup[result_str]

                    # Save result
                    st.session_state.match_results[match_key] = {
                        "winner": winner,
                        "margin": margin
                    }
                    save_match_result(pod_name, p1['name'], p2['name'], winner, result_str)

                    # Score updating
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
        player.update(results[player['name']])
    return players


# --- Save bracket to Supabase ---
def save_bracket_data(df):
    data = {
        "json_data": df.to_json(orient="split"),
        "timestamp": datetime.utcnow().isoformat()
    }
    response = supabase.table("bracket_data").insert(data).execute()
    if response.status_code != 201:
        st.error("❌ Error saving bracket data.")
    return response


# --- Label Helper ---
def label(player):
    return f"{player['name']} ({player['handicap']})"


st.title("\U0001F3CC️ Golf Match Play Tournament Dashboard")
tabs = st.tabs(["📁 Pods Overview", "📊 Group Stage", "📋 Standings", "🏆 Bracket", "📤 Export", "🔮 Predict Bracket", "🗃️ Results Log"])


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
            updated_players = simulate_matches(players, pod_name)
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

        qf_left, qf_right = [], []
        sf_left, sf_right = [], []
        finalist_left = finalist_right = None
        champion = None

        # === LEFT SIDE ===
        with col1:
            st.markdown("### 🟦 Left Side")
            st.markdown("#### 🏁 Round of 16")

            for i in range(0, len(left), 2):
                try:
                    p1, p2 = left.iloc[i], left.iloc[i + 1]
                except IndexError:
                    continue  # Skip incomplete pair

                match_label = f"{label(p1)} vs {label(p2)}"

                if st.session_state.authenticated:
                    winner = st.radio(match_label, [label(p1), label(p2)], key=f"R16L_{i}", index=None)
                    if winner:
                        qf_left.append(p1 if winner == label(p1) else p2)
                else:
                    st.markdown(f"🔒 {match_label} _(Admin only)_")

            st.markdown("#### 🥈 Quarterfinals")
            for i in range(0, len(qf_left), 2):
                if i + 1 >= len(qf_left): continue
                p1, p2 = qf_left[i], qf_left[i + 1]
                match_label = f"QF: {label(p1)} vs {label(p2)}"

                if st.session_state.authenticated:
                    winner = st.radio(match_label, [label(p1), label(p2)], key=f"QFL_{i}", index=None)
                    if winner:
                        sf_left.append(p1 if winner == label(p1) else p2)
                else:
                    st.markdown(f"🔒 {match_label} _(Admin only)_")

            if len(sf_left) == 2:
                st.markdown("#### 🥇 Semifinal Winner")
                if st.session_state.authenticated:
                    finalist_label = st.radio(
                        "🏅 Left Finalist:", [label(sf_left[0]), label(sf_left[1])], key="LFinal", index=None
                    )
                    if finalist_label:
                        finalist_left = sf_left[0] if finalist_label == label(sf_left[0]) else sf_left[1]
                else:
                    st.markdown("🔒 Semifinal (Left) — _(Admin only)_")

        # === RIGHT SIDE ===
        with col2:
            st.markdown("### 🟥 Right Side")
            st.markdown("#### 🏁 Round of 16")

            for i in range(0, len(right), 2):
                try:
                    p1, p2 = right.iloc[i], right.iloc[i + 1]
                except IndexError:
                    continue

                match_label = f"{label(p1)} vs {label(p2)}"

                if st.session_state.authenticated:
                    winner = st.radio(match_label, [label(p1), label(p2)], key=f"R16R_{i}", index=None)
                    if winner:
                        qf_right.append(p1 if winner == label(p1) else p2)
                else:
                    st.markdown(f"🔒 {match_label} _(Admin only)_")

            st.markdown("#### 🥈 Quarterfinals")
            for i in range(0, len(qf_right), 2):
                if i + 1 >= len(qf_right): continue
                p1, p2 = qf_right[i], qf_right[i + 1]
                match_label = f"QF: {label(p1)} vs {label(p2)}"

                if st.session_state.authenticated:
                    winner = st.radio(match_label, [label(p1), label(p2)], key=f"QFR_{i}", index=None)
                    if winner:
                        sf_right.append(p1 if winner == label(p1) else p2)
                else:
                    st.markdown(f"🔒 {match_label} _(Admin only)_")

            if len(sf_right) == 2:
                st.markdown("#### 🥇 Semifinal Winner")
                if st.session_state.authenticated:
                    finalist_label = st.radio(
                        "🏅 Right Finalist:", [label(sf_right[0]), label(sf_right[1])], key="RFinal", index=None
                    )
                    if finalist_label:
                        finalist_right = sf_right[0] if finalist_label == label(sf_right[0]) else sf_right[1]
                else:
                    st.markdown("🔒 Semifinal (Right) — _(Admin only)_")

        # === FINAL MATCH ===
        st.markdown("### 🏁 Final Match")
        if st.session_state.authenticated and finalist_left and finalist_right:
            champ_label = st.radio(
                "🏆 Champion:", [label(finalist_left), label(finalist_right)], key="Champ", index=None
            )
            if champ_label:
                champion = finalist_left if champ_label == label(finalist_left) else finalist_right
                st.success(f"🎉 Champion: {champion['name']} ({champion['handicap']})")
        elif not st.session_state.authenticated:
            st.markdown("🔒 Final match — _(Admin only)_")



# Tab 3: Standings
with tabs[2]:
    st.subheader("📋 Standings")

    if not st.session_state.bracket_data.empty and st.session_state.get("tiebreaks_resolved", False):
        st.dataframe(st.session_state.bracket_data)
    elif st.session_state.authenticated and not st.session_state.bracket_data.empty:
        st.info("🔧 Bracket data loaded, but finalization is not complete. Finalize bracket to publish standings.")
    else:
        st.info("📭 Standings will appear here once the bracket has been finalized by an admin.")

# Tab 4: Export
with tabs[4]:
    st.subheader("\U0001F4E4 Export")
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv")

# Predict Bracket (Updated for Full Name and Public Ledger)
with tabs[5]:
    st.subheader("🔮 Predict Bracket")

    if st.session_state.bracket_data.empty or len(st.session_state.bracket_data) < 16:
        st.warning("Bracket prediction will be available once the field of 16 is set.")
    else:
        if "prediction_log" not in st.session_state:
            st.session_state.prediction_log = load_json("predictions.json") or []

        full_name = st.text_input("Enter your full name to submit a prediction:")

        if full_name:
            name_exists = any(entry["name"].lower() == full_name.lower() for entry in st.session_state.prediction_log)

            if name_exists:
                st.warning("You've already submitted a bracket. Only one entry per name is allowed.")
            else:
                bracket_df = st.session_state.bracket_data
                left = bracket_df.iloc[0:8].reset_index(drop=True)
                right = bracket_df.iloc[8:16].reset_index(drop=True)

                st.markdown("### \U0001F7E6 Left Side Predictions")
                pred_qf_left = []
                for i in range(0, 8, 2):
                    p1, p2 = left.iloc[i], left.iloc[i+1]
                    pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PL16_{i}_{full_name}")
                    pred_qf_left.append(p1 if pick == label(p1) else p2)

                pred_sf_left = []
                for i in range(0, len(pred_qf_left), 2):
                    p1, p2 = pred_qf_left[i], pred_qf_left[i+1]
                    pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PLQF_{i}_{full_name}")
                    pred_sf_left.append(p1 if pick == label(p1) else p2)

                finalist_left = st.radio(f"Left Finalist:", [label(pred_sf_left[0]), label(pred_sf_left[1])], key=f"PLSF_{full_name}")
                finalist_left = pred_sf_left[0] if finalist_left == label(pred_sf_left[0]) else pred_sf_left[1]

                st.markdown("### \U0001F7E5 Right Side Predictions")
                pred_qf_right = []
                for i in range(0, 8, 2):
                    p1, p2 = right.iloc[i], right.iloc[i+1]
                    pick = st.radio(f"Round of 16: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PR16_{i}_{full_name}")
                    pred_qf_right.append(p1 if pick == label(p1) else p2)

                pred_sf_right = []
                for i in range(0, len(pred_qf_right), 2):
                    p1, p2 = pred_qf_right[i], pred_qf_right[i+1]
                    pick = st.radio(f"Quarterfinal: {label(p1)} vs {label(p2)}", [label(p1), label(p2)], key=f"PRQF_{i}_{full_name}")
                    pred_sf_right.append(p1 if pick == label(p1) else p2)

                finalist_right = st.radio(f"Right Finalist:", [label(pred_sf_right[0]), label(pred_sf_right[1])], key=f"PRSF_{full_name}")
                finalist_right = pred_sf_right[0] if finalist_right == label(pred_sf_right[0]) else pred_sf_right[1]

                champion = st.radio(f"�෼F Predict the Champion:", [label(finalist_left), label(finalist_right)], key=f"PickChamp_{full_name}")
                champion_final = finalist_left if champion == label(finalist_left) else finalist_right

                if st.button("Submit My Bracket"):
                    prediction_entry = {
                        "name": full_name,
                        "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "finalist_left": finalist_left["name"],
                        "finalist_right": finalist_right["name"],
                        "champion": champion_final["name"]
                    }
                    st.session_state.prediction_log.append(prediction_entry)
                    save_json("predictions.json", st.session_state.prediction_log)
                    st.success("✅ Your bracket prediction has been submitted!")

        # --- Public Ledger ---
        if st.session_state.prediction_log:
            st.subheader("\U0001F4C8 Public Bracket Prediction Ledger")
            df = pd.DataFrame(st.session_state.prediction_log)
            df = df.sort_values(by="timestamp", ascending=False)
            st.dataframe(df, use_container_width=True)



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
