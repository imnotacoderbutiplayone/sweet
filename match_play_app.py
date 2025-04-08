import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import json
import os
from datetime import datetime
from supabase import create_client
import hashlib
import re

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

# --- Helper: Parse JSON field ---
def parse_json_field(json_data):
    """Parse the JSON string into a Python object."""
    try:
        return json.loads(json_data) if json_data else []
    except Exception as e:
        st.error(f"❌ Error parsing JSON field: {e}")
        return []

#-- player by name helper ---
def get_players_by_names(source_players, names):
    """
    Given a list of names and a source player list (or pods), return full player dicts.
    Will default to {"name": name, "handicap": "N/A"} if player is not found.
    """
    name_lookup = {}

    # If passed pods dictionary, flatten all players
    if isinstance(source_players, dict):
        for pod in source_players.values():
            for player in pod:
                name_lookup[player["name"]] = player
    else:
        # Assume it's already a flat list of players
        for player in source_players:
            name_lookup[player["name"]] = player

    # Return the full player records in the same order
    return [name_lookup.get(name, {"name": name, "handicap": "N/A"}) for name in names]

#-- load round players ---
def load_round_players(round_key, progression_data, source_players=None):
    """
    Load player records for a specific bracket round using Supabase progression data.
    
    Parameters:
    - round_key (str): The bracket round key, e.g., 'r16_left', 'qf_right'
    - progression_data (dict): The loaded Supabase progression object
    - source_players (list or dict): Optional. If not provided, defaults to global `pods`

    Returns:
    - list of dicts: Player records with name and handicap
    """
    if source_players is None:
        source_players = pods  # fallback to global pods

    try:
        # Get player names from progression data
        names = parse_json_field(progression_data.get(round_key, "[]"))
        
        # Ensure players are full dictionaries
        players = get_players_by_names(source_players, names)
        return players
    except Exception as e:
        st.warning(f"⚠️ Failed to load round '{round_key}': {e}")
        return []



# --- Helper: Sanitize Key function for Streamlit ---
def sanitize_key(text):
    """Sanitize and hash widget keys to avoid Streamlit duplication."""
    cleaned = re.sub(r'\W+', '_', text)  # Replace non-alphanumerics with underscores
    hashed = hashlib.md5(text.encode()).hexdigest()[:8]  # Short hash for uniqueness
    return f"{cleaned}_{hashed}"

# --- Save match result to Supabase ---
def save_match_result(pod, player1, player2, winner, margin_text):
    """
    Save match result to Supabase
    """
    data = {
        "pod": pod,
        "player1": player1,
        "player2": player2,
        "winner": winner,
        "margin": margin_text,  # Ensure the margin is saved
        "status": "pending",  # Assuming the match is still pending until the result is finalized
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    try:
        response = supabase.table("tournament_matches").insert(data).execute()  # Save to the database
        st.write("Match Result Saved:", response)  # Debugging line to check the response
        
        # Reload match results into session state
        st.session_state.match_results = load_match_results()  # Re-load match results from Supabase

        return response
    except Exception as e:
        st.error("❌ Error saving match result to Supabase")
        st.code(str(e))
        return None



#-- winner data ---
def get_winner_player(player1, player2, winner_name):
    """Return the full player dict matching the winner_name, or fallback."""
    for p in [player1, player2]:
        if p["name"] == winner_name:
            return p
    return {"name": winner_name, "handicap": "N/A"}  # fallback if no match

def render_match(player1, player2, winner, margin, readonly=False, key_prefix=""):
    """
    Renders the match between two players.
    - player1, player2: dictionaries containing player info (e.g., name, handicap)
    - winner: the current winner (or "Tie")
    - margin: the margin of victory (or "Tie")
    - readonly: if True, makes the match readonly (admin-only input)
    - key_prefix: ensures that each checkbox/radio button has a unique key

    Returns the winner of the match and the margin.
    """
    # Check if both players have valid data
    if not player1 or not player2:
        st.error(f"❌ Invalid player data for one or both players: {player1}, {player2}")
        return None, None
    if "name" not in player1 or "handicap" not in player1:
        st.error(f"❌ Invalid player data for {player1}")
        return None, None
    if "name" not in player2 or "handicap" not in player2:
        st.error(f"❌ Invalid player data for {player2}")
        return None, None

    # Display match information
    st.write(f"### Match: {player1['name']} vs {player2['name']}")
    st.write(f"**Handicaps**: {player1['handicap']} vs {player2['handicap']}")
    
    # Show the winner (if known)
    st.write(f"**Current Winner**: {winner if winner != 'Tie' else 'No winner yet'}")

    # If readonly is False, allow the admin to select the winner
    if not readonly:
        winner_key = f"{key_prefix}_winner"
        margin_key = f"{key_prefix}_margin"

        # Radio button to choose the winner (or tie)
        options = [player1['name'], player2['name'], "Tie"]
        default_index = options.index(winner) if winner in options else 2  # Default to "Tie" if winner is invalid

        selected_winner = st.radio(
            "Select winner",
            options=options,
            index=default_index,
            key=winner_key
        )

        # Select margin if there is a winner
        margin = "Tie"  # Default if it's a tie
        if selected_winner != "Tie":
            margin = st.selectbox(
                "Select win margin",
                options=["1 up", "2 and 1", "3 and 2", "4 and 3", "5 and 4"],
                key=margin_key
            )
        
        # Display result button
        if st.button(f"Save result for {player1['name']} vs {player2['name']}", key=f"submit_{key_prefix}"):
            # Save the result to Supabase
            save_match_result("group_stage", player1['name'], player2['name'], selected_winner, margin)

            # Reload match results to update session state
            st.session_state.match_results = load_match_results()  # Re-load match results from Supabase
            
            st.success(f"Result saved: {selected_winner} wins {margin}")
            return selected_winner, margin
    else:
        # If readonly is True, just display the result and margin
        st.write(f"Match result: {winner}")
        st.write(f"Margin: {margin}")
        return winner, margin


# --- Build bracket from scores and tiebreaks ---
def build_bracket_df_from_pod_scores(pod_scores, tiebreak_selections):
    winners, second_place = [], []

    for pod_name, df in pod_scores.items():
        if df.empty or "points" not in df.columns:
            continue

        df_sorted = df.sort_values(by=["points", "margin"], ascending=False).reset_index(drop=True)

        # Resolve 1st
        tied_first = df_sorted[
            (df_sorted["points"] == df_sorted.iloc[0]["points"]) &
            (df_sorted["margin"] == df_sorted.iloc[0]["margin"])
        ]
        first_name = (tiebreak_selections.get(f"{pod_name}_1st")
                      if len(tied_first) > 1 else tied_first.iloc[0]["name"])
        winner_row = df_sorted[df_sorted["name"] == first_name].iloc[0].to_dict()
        winners.append({"pod": pod_name, **winner_row})

        # Resolve 2nd
        remaining = df_sorted[df_sorted["name"] != first_name].reset_index(drop=True)
        if remaining.empty:
            continue
        tied_second = remaining[
            (remaining["points"] == remaining.iloc[0]["points"]) &
            (remaining["margin"] == remaining.iloc[0]["margin"])
        ]
        second_name = (tiebreak_selections.get(f"{pod_name}_2nd")
                       if len(tied_second) > 1 else tied_second.iloc[0]["name"])
        second_row = remaining[remaining["name"] == second_name].iloc[0].to_dict()
        second_place.append(second_row)

    # Add 3 best 2nd place finishers
    top_3 = sorted(second_place, key=lambda x: (x["points"], x["margin"]), reverse=True)[:3]
    final_players = winners + top_3
    bracket_df = pd.DataFrame(final_players)
    bracket_df.index = [f"Seed {i+1}" for i in range(len(bracket_df))]

    return bracket_df

#--- Simulate Matches ----

def simulate_matches(players, pod_name, source="", editable=False):
    results = defaultdict(lambda: {"points": 0, "margin": 0})

    if not players:
        st.error(f"❌ No players found in pod {pod_name}.")
        return []

    num_players = len(players)

    if not all(isinstance(player, dict) and 'name' in player and 'handicap' in player for player in players):
        st.error(f"❌ Invalid player data in pod {pod_name}.")
        return []

    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1, p2 = players[i], players[j]
            player_names = sorted([p1['name'], p2['name']])
            raw_key = f"{source}_{pod_name}|{player_names[0]} vs {player_names[1]}"
            base_key = sanitize_key(raw_key)

            entry_key = f"{base_key}_checkbox"
            winner_key = f"{base_key}_winner"
            margin_key = f"{base_key}_margin"
            match_key = f"{pod_name}|{p1['name']} vs {p2['name']}"

            h1 = f"{p1['handicap']:.1f}" if p1['handicap'] else "N/A"
            h2 = f"{p2['handicap']:.1f}" if p2['handicap'] else "N/A"
            st.write(f"Match: {p1['name']} ({h1}) vs {p2['name']} ({h2})")

            if editable:
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



# --- Load all match results from Supabase ---
def load_match_results():
    try:
        response = supabase.table("tournament_matches").select("*").order("created_at", desc=True).execute()

        match_dict = defaultdict(dict)
        for r in response.data:
            match_key = f"{r['pod']}|{r['player1']} vs {r['player2']}"

            # Handle None values gracefully and check the status
            match_dict[match_key] = {
                "winner": r.get("winner", "N/A"),  # Default to 'N/A' if winner is missing
                "margin": r.get("margin", "N/A"),  # Default to 'N/A' if margin is missing
                "status": r.get("status", "N/A"),  # Handle status if it's missing or null
                "round": r.get("round", "N/A"),  # Handle round if it's None
            }

        st.write("Loaded Match Results:", match_dict)  # Debugging line to check what is loaded
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

# --- Helper: Label players ---
def label(player):
    return f"{player['name']} ({player['handicap']})"

# --- Load bracket data ---
def load_bracket_data():
    try:
        # Fetch bracket data from Supabase
        response = supabase.table("bracket_data").select("json_data").order("created_at", desc=True).limit(1).execute()

        if response.data and len(response.data) > 0:
            bracket_df = pd.read_json(response.data[0]["json_data"], orient="split")
            if bracket_df.empty:
                st.warning("Bracket data is empty.")
            return bracket_df
        else:
            st.info("ℹ️ No bracket data found in Supabase.")
            return pd.DataFrame()

    except Exception as e:
        st.error("❌ Supabase error loading bracket data")
        st.code(str(e))
        return pd.DataFrame()


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

# --- Bracket Margin Lookup ---
margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

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

# --- Streamlit App Auth ---
if "match_results" not in st.session_state:
    st.session_state.match_results = load_match_results() or {}

# --- Admin Authentication (Simple Password-Based) ---
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

# --- Sidebar Admin Login ---
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

# --- Streamlit App Configuration ---
tabs = st.tabs([
    "📁 Pods Overview", 
    "📊 Group Stage", 
    "📋 Standings", 
    "🏆 Bracket", 
    "📤 Export", 
    "🔮 Predict Bracket", 
    "🗃️ Results Log",
    "🏅 Leaderboard"
])

# Load shared bracket data
if "bracket_data" not in st.session_state:
    bracket_df = load_bracket_data()
    st.session_state.bracket_data = bracket_df
if "user_predictions" not in st.session_state:
    st.session_state.user_predictions = {}

# --- Main Tournament Tabs ---
with tabs[0]:
    st.subheader("📁 All Pods and Player Handicaps")

    # Displaying pod data...
    pod_names = list(pods.keys())
    num_cols = 3  # You can adjust this to control the number of columns
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


# --- Group Stage ---
with tabs[1]:
    st.subheader("📊 Group Stage - Match Results")

    # Load match results from Supabase (or session state if loaded earlier)
    match_results = load_match_results()
    st.session_state.match_results = match_results

    pod_results = {}

    # Render matches for each pod
    for pod_name, players in pods.items():
        with st.expander(pod_name):
            # Render each match and allow the admin to pick winners and margins
            for i in range(0, len(players), 2):  # Pair players for each match
                if i + 1 < len(players):  # Ensure there are two players to compare
                    player1 = players[i]
                    player2 = players[i + 1]

                    # Get current winner and margin if it exists
                    match_key = f"{pod_name}|{player1['name']} vs {player2['name']}"
                    current_result = match_results.get(match_key, {"winner": "Tie", "margin": "Tie"})

                    # Fallback in case 'winner' or 'margin' are missing
                    winner = current_result.get("winner", "Tie")
                    margin = current_result.get("margin", "Tie")

                    # Render the match, allowing for winner and margin selection
                    winner, margin = render_match(player1, player2, winner, margin, readonly=False, key_prefix=match_key)

                    # Store the results after selecting
                    if winner != "Tie":
                        match_results[match_key] = {"winner": winner, "margin": margin}
                    else:
                        match_results[match_key] = {"winner": "Tie", "margin": margin}

            # Update pod standings after each match
            pod_results[pod_name] = pd.DataFrame(players)

    # If authenticated, allow to review and resolve tiebreakers
    if st.session_state.authenticated:
        st.header("🧠 Step 1: Review & Resolve Tiebreakers")

        if "tiebreak_selections" not in st.session_state:
            st.session_state.tiebreak_selections = {}
        if "tiebreaks_resolved" not in st.session_state:
            st.session_state.tiebreaks_resolved = False

        unresolved = False
        pod_scores = compute_pod_standings_from_results(pods, match_results)

        for pod_name, df in pod_scores.items():
            if df.empty or "points" not in df.columns:
                st.info(f"📭 No match results entered yet for {pod_name}.")
                continue

            sorted_players = df.sort_values(by=["points", "margin"], ascending=False).reset_index(drop=True)

            # Resolve tiebreakers for first place
            top_score = sorted_players.iloc[0]["points"]
            top_margin = sorted_players.iloc[0]["margin"]
            tied_first = sorted_players[(sorted_players["points"] == top_score) & (sorted_players["margin"] == top_margin)]

            if len(tied_first) > 1:
                st.warning(f"🔁 Tie for 1st in {pod_name}")
                options = tied_first["name"].tolist()
                selected = st.radio(f"Select 1st place in {pod_name}:", options, key=f"{pod_name}_1st")
                if selected:
                    st.session_state.tiebreak_selections[f"{pod_name}_1st"] = selected
                else:
                    unresolved = True
            else:
                st.session_state.tiebreak_selections[f"{pod_name}_1st"] = tied_first.iloc[0]["name"]

            winner_name = st.session_state.tiebreak_selections.get(f"{pod_name}_1st")
            remaining = sorted_players[sorted_players["name"] != winner_name].reset_index(drop=True)

            if remaining.empty:
                st.warning(f"⚠️ Not enough players to determine second place in {pod_name}")
                continue

            second_score = remaining.iloc[0]["points"]
            second_margin = remaining.iloc[0]["margin"]
            tied_second = remaining[(remaining["points"] == second_score) & (remaining["margin"] == second_margin)]

            if len(tied_second) > 1:
                st.warning(f"🔁 Tie for 2nd in {pod_name}")
                options = tied_second["name"].tolist()
                selected = st.radio(f"Select 2nd place in {pod_name}:", options, key=f"{pod_name}_2nd")
                if selected:
                    st.session_state.tiebreak_selections[f"{pod_name}_2nd"] = selected
                else:
                    unresolved = True
            else:
                st.session_state.tiebreak_selections[f"{pod_name}_2nd"] = tied_second.iloc[0]["name"]

        if unresolved:
            st.error("⛔ Please resolve all tiebreakers before finalizing.")
            st.session_state.tiebreaks_resolved = False
        else:
            st.success("✅ All tiebreakers selected.")
            st.session_state.tiebreaks_resolved = True

        if st.session_state.get("tiebreaks_resolved", False):
            if st.button("🏁 Finalize Bracket and Seed Field"):
                bracket_df = build_bracket_df_from_pod_scores(pod_scores, st.session_state.tiebreak_selections)
                st.session_state.finalized_bracket = bracket_df

                # Optionally, save to Supabase if you want persistence
                save_bracket_data(bracket_df)

                st.success("✅ Bracket finalized and seeded.")
                st.write("📊 Final Bracket", bracket_df)
    else:
        st.warning("Bracket cannot be finalized until all tiebreakers are resolved.")



# --- Standings ---
with tabs[2]:
    st.subheader("📋 Standings")

    # Load match results from session state
    if "match_results" not in st.session_state:
        st.session_state.match_results = load_match_results()

    pod_results = {}

    # Process each pod and calculate the points and margins for each player
    for pod_name, players in pods.items():
        updated_players = []
        for player in players:
            name = player['name']
            total_points = 0
            total_margin = 0

            # Iterate through all match results and calculate points and margins
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

            # Store the player's updated stats
            updated_players.append({
                "name": name,
                "handicap": player["handicap"],
                "Points": total_points,
                "Margin": total_margin
            })

        # Sort players within the pod by points and margin
        df = pd.DataFrame(updated_players)
        if not df.empty:
            df = df.sort_values(by=["Points", "Margin"], ascending=False)
            df.rename(columns={"name": "Player", "handicap": "Handicap"}, inplace=True)
            pod_results[pod_name] = df

    # Display standings for each pod
    if pod_results:
        for pod_name, df in pod_results.items():
            with st.expander(f"📦 {pod_name} Standings", expanded=True):
                st.dataframe(df, use_container_width=True)
    else:
        st.info("📭 No match results have been entered yet.")


# --- Admin View Rendering Bracket ---
with tabs[3]:
    st.subheader("🏆 Bracket")

    # Check if the bracket is finalized
    if "finalized_bracket" not in st.session_state:
        st.warning("Bracket progression not set yet. Please finalize the bracket in Group Stage.")
        st.stop()

    bracket_df = st.session_state.finalized_bracket  # Load finalized bracket data from session state

    # Split bracket into left and right sides
    left = bracket_df.iloc[0:8].to_dict("records")
    right = bracket_df.iloc[8:16].to_dict("records")

    col1, col2 = st.columns(2)

    def get_winner_safe(round_list, index):
        try:
            return round_list[index]["name"]
        except (IndexError, TypeError, KeyError):
            return ""

    if st.session_state.authenticated:
        st.info("🔐 Admin mode: Enter results and save")

        with col1:
            st.markdown("### 🟦 Left Side")

            st.markdown("#### 🔹 Round of 16")
            r16_left = []
            for i in range(0, len(left), 2):
                winner_name = render_match(left[i], left[i + 1], "", readonly=False, key_prefix=f"r16_left_{i}")
                r16_left.append(get_winner_player(left[i], left[i + 1], winner_name))

            st.markdown("#### 🥉 Quarterfinals")
            qf_left = []
            for i in range(0, len(r16_left), 2):
                if i + 1 < len(r16_left):
                    winner_name = render_match(r16_left[i], r16_left[i + 1], "", readonly=False, key_prefix=f"qf_left_{i}")
                    qf_left.append(get_winner_player(r16_left[i], r16_left[i + 1], winner_name))

            st.markdown("#### 🥈 Semifinal")
            sf_left = []
            for i in range(0, len(qf_left), 2):
                if i + 1 < len(qf_left):
                    winner_name = render_match(qf_left[i], qf_left[i + 1], "", readonly=False, key_prefix=f"sf_left_{i}")
                    sf_left.append(get_winner_player(qf_left[i], qf_left[i + 1], winner_name))

        with col2:
            st.markdown("### 🟥 Right Side")

            st.markdown("#### 🔹 Round of 16")
            r16_right = []
            for i in range(0, len(right), 2):
                winner_name = render_match(right[i], right[i + 1], "", readonly=False, key_prefix=f"r16_right_{i}")
                r16_right.append(get_winner_player(right[i], right[i + 1], winner_name))

            st.markdown("#### 🥉 Quarterfinals")
            qf_right = []
            for i in range(0, len(r16_right), 2):
                if i + 1 < len(r16_right):
                    winner_name = render_match(r16_right[i], r16_right[i + 1], "", readonly=False, key_prefix=f"qf_right_{i}")
                    qf_right.append(get_winner_player(r16_right[i], r16_right[i + 1], winner_name))

            st.markdown("#### 🥈 Semifinal")
            sf_right = []
            for i in range(0, len(qf_right), 2):
                if i + 1 < len(qf_right):
                    winner_name = render_match(qf_right[i], qf_right[i + 1], "", readonly=False, key_prefix=f"sf_right_{i}")
                    sf_right.append(get_winner_player(qf_right[i], qf_right[i + 1], winner_name))

        if sf_left and sf_right:
            st.markdown("### 🏁 Final Match")
            champ_choice = st.radio("🏆 Select the Champion",
                                    [label(sf_left[0]), label(sf_right[0])],
                                    key="final_match_radio")
            champion = sf_left[0] if champ_choice == label(sf_left[0]) else sf_right[0]
        else:
            champion = None

        # Save the bracket progression once the admin finalizes
        if st.button("🏁 Finalize Bracket and Seed Field", key="finalize_bracket_button"):
            save_bracket_progression_to_supabase({
                "r16_left": json.dumps([p["name"] for p in r16_left]),
                "r16_right": json.dumps([p["name"] for p in r16_right]),
                "qf_left": json.dumps([p["name"] for p in qf_left]),
                "qf_right": json.dumps([p["name"] for p in qf_right]),
                "sf_left": json.dumps([p["name"] for p in sf_left]),
                "sf_right": json.dumps([p["name"] for p in sf_right]),
                "finalist_left": sf_left[0]["name"] if sf_left else "",
                "finalist_right": sf_right[0]["name"] if sf_right else "",
                "champion": champion["name"] if champion else ""
            })
            st.success("✅ Bracket progression saved!")
    else:
        st.warning("Bracket progression not set yet.")
        
# --- Non-Admin View Rendering Bracket ---
with tabs[3]:
    st.subheader("🏆 Bracket")

    # Check if the bracket is finalized
    if "finalized_bracket" not in st.session_state:
        st.warning("Bracket progression not set yet. Please finalize the bracket in Group Stage.")
        st.stop()

    bracket_df = st.session_state.finalized_bracket  # Load finalized bracket data from session state

    # Split bracket into left and right sides
    left = bracket_df.iloc[0:8].to_dict("records")
    right = bracket_df.iloc[8:16].to_dict("records")

    col1, col2 = st.columns(2)

    def get_winner_safe(round_list, index):
        try:
            return round_list[index]["name"]
        except (IndexError, TypeError, KeyError):
            return ""

    # Render the bracket for non-admin users
    with col1:
        st.markdown("### 🟦 Left Side")

        st.markdown("#### 🔹 Round of 16")
        r16_left = []
        for i in range(0, len(left), 2):
            winner_name = get_winner_safe(left, i)
            r16_left.append(winner_name)

        st.markdown("#### 🥉 Quarterfinals")
        qf_left = []
        for i in range(0, len(r16_left), 2):
            if i + 1 < len(r16_left):
                winner_name = get_winner_safe(r16_left, i)
                qf_left.append(winner_name)

        st.markdown("#### 🥈 Semifinal")
        sf_left = []
        for i in range(0, len(qf_left), 2):
            if i + 1 < len(qf_left):
                winner_name = get_winner_safe(qf_left, i)
                sf_left.append(winner_name)

    with col2:
        st.markdown("### 🟥 Right Side")

        st.markdown("#### 🔹 Round of 16")
        r16_right = []
        for i in range(0, len(right), 2):
            winner_name = get_winner_safe(right, i)
            r16_right.append(winner_name)

        st.markdown("#### 🥉 Quarterfinals")
        qf_right = []
        for i in range(0, len(r16_right), 2):
            if i + 1 < len(r16_right):
                winner_name = get_winner_safe(r16_right, i)
                qf_right.append(winner_name)

        st.markdown("#### 🥈 Semifinal")
        sf_right = []
        for i in range(0, len(qf_right), 2):
            if i + 1 < len(qf_right):
                winner_name = get_winner_safe(qf_right, i)
                sf_right.append(winner_name)

    if sf_left and sf_right:
        st.markdown("### 🏁 Final Match")
        champ_choice = st.radio("🏆 Select the Champion",
                                [label(sf_left[0]), label(sf_right[0])],
                                key="final_match_radio")
        champion = sf_left[0] if champ_choice == label(sf_left[0]) else sf_right[0]
    else:
        champion = None



# --- Export ---
with tabs[4]:
    st.subheader("📤 Export")

    # Export Bracket Data
    if not st.session_state.bracket_data.empty:
        csv = st.session_state.bracket_data.to_csv().encode("utf-8")
        st.download_button("Download Bracket CSV", csv, "bracket.csv", "text/csv", key="bracket_download_button")
    else:
        st.warning("No bracket data available for export.")


# Export Match Results
if "match_results" in st.session_state and st.session_state.match_results:
    match_results_data = []
    for key, result in st.session_state.match_results.items():
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

        match_results_data.append({
            "Pod": pod_name,
            "Player 1": player1.strip(),
            "Player 2": player2.strip(),
            "Winner": winner,
            "Margin": margin_text
        })

    df_match_results = pd.DataFrame(match_results_data)
    df_match_results = df_match_results.sort_values(by=["Pod", "Player 1"])

    # Display match results CSV download button (Ensure unique key for button)
    csv_match_results = df_match_results.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Match Results CSV", csv_match_results, "match_results.csv", "text/csv", key="unique_match_results_download_button")
else:
    st.warning("No match results available for export.")


# --- Predict Bracket ---
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

                # Round of 16 predictions
                for i in range(0, 8, 2):
                    p1, p2 = left.iloc[i], left.iloc[i + 1]
                    pick = st.radio(
                        f"Round of 16: {label(p1)} vs {label(p2)}",
                        [label(p1), label(p2)],
                        key=f"PL16_{i}_{full_name}"
                    )
                    pred_r16_left.append(p1 if pick == label(p1) else p2)

                # Quarterfinal predictions
                for i in range(0, len(pred_r16_left), 2):
                    if i + 1 < len(pred_r16_left):
                        p1, p2 = pred_r16_left[i], pred_r16_left[i + 1]
                        pick = st.radio(
                            f"Quarterfinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PLQF_{i}_{full_name}"
                        )
                        pred_qf_left.append(p1 if pick == label(p1) else p2)

                # Semifinal predictions
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

                # Round of 16 predictions for right side
                for i in range(0, 8, 2):
                    p1, p2 = right.iloc[i], right.iloc[i + 1]
                    pick = st.radio(
                        f"Round of 16: {label(p1)} vs {label(p2)}",
                        [label(p1), label(p2)],
                        key=f"PR16_{i}_{full_name}"
                    )
                    pred_r16_right.append(p1 if pick == label(p1) else p2)

                # Quarterfinal predictions for right side
                for i in range(0, len(pred_r16_right), 2):
                    if i + 1 < len(pred_r16_right):
                        p1, p2 = pred_r16_right[i], pred_r16_right[i + 1]
                        pick = st.radio(
                            f"Quarterfinal: {label(p1)} vs {label(p2)}",
                            [label(p1), label(p2)],
                            key=f"PRQF_{i}_{full_name}"
                        )
                        pred_qf_right.append(p1 if pick == label(p1) else p2)

                # Semifinal predictions for right side
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

                # Final match predictions
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
                            # Save the prediction to the database
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


# --- Results Log ---
with tabs[6]:  # Results Log tab
    st.subheader("🗃️ Match Results Log")

    try:
        # Reload match results into session state (after saving match result)
        match_results = st.session_state.get("match_results", {})

        if not match_results:
            st.info("No match results have been entered yet.")
        else:
            # Convert the match results into a DataFrame
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
                margin = result.get("margin", "Tie")  # Ensure we handle 'Tie' margin
                status = result.get("status", "N/A")  # Include status here
                
                # Fallback for unknown margin
                margin_text = margin if margin != "Tie" else "Tie"

                data.append({
                    "Pod": pod_name,
                    "Player 1": player1.strip(),
                    "Player 2": player2.strip(),
                    "Winner": winner,
                    "Margin": margin_text,
                    "Status": status  # Display status in the log
                })

            # Create DataFrame to display the match results
            df = pd.DataFrame(data)
            df = df.sort_values(by=["Pod", "Player 1"])

            # Display match results
            st.dataframe(df, use_container_width=True)

            # Optional: Allow the user to download the match results as CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Match Results CSV", csv, "match_results.csv", "text/csv")
    
    except Exception as e:
        st.error("❌ Error loading match results.")
        st.code(str(e))



# --- Leaderboard ---
with tabs[7]:
    st.subheader("🏅 Prediction Leaderboard")

    try:
        # Load predictions from Supabase
        predictions_response = supabase.table("predictions").select("*").execute()
        predictions = predictions_response.data

        if not predictions:
            st.info("No predictions submitted yet.")
        else:
            # Load the latest final results
            final_results_response = supabase.table("final_results") \
                                             .select("*") \
                                             .order("created_at", desc=True) \
                                             .limit(1) \
                                             .execute()
            final_results_data = final_results_response.data

            if not final_results_data:
                st.warning("Final results not confirmed yet. Leaderboard will update once finalized.")
            else:
                final_result = final_results_data[0]

                # Parse the actual results
                actual_results = {
                    "r16_left": parse_json_field(final_result.get("r16_left", "[]")),
                    "r16_right": parse_json_field(final_result.get("r16_right", "[]")),
                    "qf_left": parse_json_field(final_result.get("qf_left", "[]")),
                    "qf_right": parse_json_field(final_result.get("qf_right", "[]")),
                    "sf_left": parse_json_field(final_result.get("sf_left", "[]")),
                    "sf_right": parse_json_field(final_result.get("sf_right", "[]")),
                    "champion": final_result.get("champion", "").strip()
                }

                leaderboard = []

                # Calculate scores for each prediction
                for row in predictions:
                    name = row.get("name", "Unknown")
                    score = 0
                    ts = row.get("timestamp", "")[:19].replace("T", " ") + " UTC"

                    # Compare round of 16 predictions
                    pred_r16_left = parse_json_field(row.get("r16_left", "[]"))
                    pred_r16_right = parse_json_field(row.get("r16_right", "[]"))

                    for actual, predicted in zip(actual_results["r16_left"], pred_r16_left):
                        if actual == predicted:
                            score += 1
                    for actual, predicted in zip(actual_results["r16_right"], pred_r16_right):
                        if actual == predicted:
                            score += 1

                    # Compare quarterfinal predictions
                    pred_qf_left = parse_json_field(row.get("qf_left", "[]"))
                    pred_qf_right = parse_json_field(row.get("qf_right", "[]"))

                    for actual, predicted in zip(actual_results["qf_left"], pred_qf_left):
                        if actual == predicted:
                            score += 3
                    for actual, predicted in zip(actual_results["qf_right"], pred_qf_right):
                        if actual == predicted:
                            score += 3

                    # Compare semifinal predictions
                    pred_sf_left = parse_json_field(row.get("sf_left", "[]"))
                    pred_sf_right = parse_json_field(row.get("sf_right", "[]"))

                    for actual, predicted in zip(actual_results["sf_left"], pred_sf_left):
                        if actual == predicted:
                            score += 5
                    for actual, predicted in zip(actual_results["sf_right"], pred_sf_right):
                        if actual == predicted:
                            score += 5

                    # Compare champion prediction
                    if row.get("champion", "").strip() == actual_results["champion"]:
                        score += 10

                    leaderboard.append({
                        "Name": name,
                        "Score": score,
                        "Submitted At": ts
                    })

                # Create a dataframe for leaderboard
                leaderboard_df = pd.DataFrame(leaderboard)
                leaderboard_df = leaderboard_df.sort_values(
                    by=["Score", "Submitted At"],
                    ascending=[False, True]
                ).reset_index(drop=True)

                # Add rank column
                leaderboard_df.insert(0, "Rank", leaderboard_df.index + 1)

                # Highlight podium places
                def highlight_podium(row):
                    color = ""
                    if row["Rank"] == 1:
                        color = "background-color: gold; font-weight: bold"
                    elif row["Rank"] == 2:
                        color = "background-color: silver; font-weight: bold"
                    elif row["Rank"] == 3:
                        color = "background-color: #cd7f32; font-weight: bold"  # bronze
                    return [color] * len(row)

                # Apply styles to the leaderboard
                styled_df = leaderboard_df.style.apply(highlight_podium, axis=1)

                # Display leaderboard
                st.dataframe(styled_df, use_container_width=True)
    except Exception as e:
        st.error("❌ Error loading leaderboard.")
        st.code(str(e))
