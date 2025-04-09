import streamlit as st
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")
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
        json_data = df.to_json(orient="split")  # Convert DataFrame to JSON string
        response = supabase.table("bracket_data").insert({"json_data": json_data}).execute()

        if response.status_code == 200 and response.data:
            st.success("✅ Bracket data saved successfully to Supabase.")
            return response.data  # Return the inserted data or a success indicator
        else:
            st.error(f"❌ Failed to save bracket data to Supabase: {response.status_code} - {response.error_message if hasattr(response, 'error_message') else ''}")
            return None
    except Exception as e:
        st.error(f"❌ Error saving bracket data to Supabase: {e}")
        return None


# --- Helper: Parse JSON field ---
def parse_json_field(json_data):
    """Parse the JSON string into a Python object."""
    try:
        return json.loads(json_data) if json_data else []
    except Exception as e:
        st.error(f"❌ Error parsing JSON field: {e}")
        return []

def get_player_by_name(name, source_df):
    return next((p for p in source_df.to_dict("records") if p["name"] == name), {"name": name})

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

# --- Compute standings dynamically from match results ---
def compute_pod_standings_from_results(pods, match_results):
    pod_scores = {}

    # Define the margin lookup as a dictionary (you've provided this)
    margin_lookup = {
        "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
        "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
    }

    for pod_name, players in pods.items():
        results = []
        for player in players:
            name = player["name"]
            points, margin = 0, 0

            # Iterate through all match results and calculate points and margins
            for key, result in match_results.items():
                if key.startswith(f"{pod_name}|") and name in key:
                    winner = result.get("winner")
                    # Get the margin string (e.g., "1 up", "2 and 1")
                    margin_str = result.get("margin", "Tie")  # Default to "Tie" if no margin

                    # Convert margin string to a numeric value
                    if margin_str != "Tie":
                        margin_value = margin_lookup.get(margin_str, 0)  # Get corresponding numeric value, default to 0 if not found
                    else:
                        margin_value = 0

                    if winner == name:
                        points += 1
                        margin += margin_value  # Safely add margin
                    elif winner == "Tie":
                        points += 0.5
                    else:
                        margin -= margin_value  # Safely subtract margin

            results.append({
                "name": name,
                "handicap": player["handicap"],
                "points": points,
                "margin": margin
            })

        pod_scores[pod_name] = pd.DataFrame(results)

    return pod_scores

# --- Fetch the most recent match results from Supabase ---
def load_most_recent_match_results():
    try:
        # Fetch the latest match results directly from Supabase
        response = supabase.table("tournament_matches") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if response.data:
            return response.data[0]  # Return the most recent match result
        else:
            st.warning("No match results found.")
            return None

    except Exception as e:
        st.error(f"❌ Error loading match results: {e}")
        return None


# --- Fetch the entire match result log ---
def load_match_result_log():
    try:
        # Fetch all match results, ordered by created_at
        response = supabase.table("tournament_matches").select("*") \
            .order("created_at", desc=True).execute()

        if response.data:
            match_results = {f"{r['pod']}|{r['player1']} vs {r['player2']}": {
                "winner": r["winner"],
                "margin": r["margin"]
            } for r in response.data}

            st.write("📋 Match Results Log")

            # Adjust the iteration to handle the structure correctly
            data = []
            for key, result in match_results.items():
                pod_name, match_str = key.split("|", 1)
                player1, player2 = match_str.split(" vs ")
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

            # Create a DataFrame and display the match results
            df = pd.DataFrame(data)
            df = df.sort_values(by=["Pod", "Player 1"])
            st.dataframe(df, use_container_width=True)

        else:
            st.warning("No match results found.")

    except Exception as e:
        st.error(f"❌ Error loading match results: {e}")
        st.code(str(e))  # Display the error if any


# --- Display the most recent match result ---
def display_most_recent_result():
    most_recent_result = load_most_recent_match_results()

    if most_recent_result:
        st.subheader("📌 Most Recent Match Result")
        match_info = most_recent_result
        winner = match_info["winner"]
        margin_value = match_info["margin"]
        # Convert margin back to string if needed
        margin_str = next((k for k, v in margin_lookup.items() if v == margin_value), "Unknown margin")
        st.write(f"Player 1: {match_info['player1']}")
        st.write(f"Player 2: {match_info['player2']}")
        st.write(f"Winner: {winner}")
        st.write(f"Margin: {margin_str}")
    else:
        st.write("No results available.")


# --- Display the entire match result log ---
def display_match_result_log():
    match_results = load_match_result_log()

    if match_results:
        st.subheader("📋 Match Results Log")
        log_data = []

        # Iterate through the match results and prepare a displayable list
        for result in match_results:
            winner = result["winner"]
            margin_value = result["margin"]
            margin_str = next((k for k, v in margin_lookup.items() if v == margin_value), "Unknown margin")
            log_data.append({
                "Player 1": result["player1"],
                "Player 2": result["player2"],
                "Winner": winner,
                "Margin": margin_str,
                "Timestamp": result["created_at"]
            })

        # Display the match log in a DataFrame format
        log_df = pd.DataFrame(log_data)
        log_df = log_df.sort_values(by="Timestamp", ascending=False)  # Sort by timestamp (newest first)
        st.dataframe(log_df, use_container_width=True)
    else:
        st.write("No match result log available.")


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

# Define the margin lookup dictionary to map string descriptions to numeric values
margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

def save_bracket_progression_to_supabase(data: dict):
    try:
        response = supabase.table("bracket_progression").insert(data).execute()
        st.write("✅ Supabase insert response:", response.data)  # optional debug
    except Exception as e:
        st.error(f"Supabase save failed: {e}")
        raise



def save_match_result(pod, player1, player2, winner, margin_str):
    # Convert margin string to numeric
    if margin_str != "Tie":
        margin_value = margin_lookup.get(margin_str, 0)
    else:
        margin_value = 0

    # Prepare the data to save
    data = {
        "pod": pod,
        "player1": player1,
        "player2": player2,
        "winner": winner,
        "margin": margin_value,  
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        # Check if a match result already exists based on pod, player1, and player2
        response = supabase.table("tournament_matches").select("*") \
            .eq("pod", pod) \
            .eq("player1", player1) \
            .eq("player2", player2) \
            .execute()

        if response.data and len(response.data) > 0:
            # Match exists, so update it
            update_response = supabase.table("tournament_matches") \
                .update(data) \
                .eq("pod", pod) \
                .eq("player1", player1) \
                .eq("player2", player2) \
                .execute()

            if update_response.data:
                st.success(f"Result updated: {winner} wins {margin_str}")
            else:
                st.error("❌ Error updating match result.")
        else:
            # Match does not exist, so insert it
            insert_response = supabase.table("tournament_matches").insert(data).execute()

            if insert_response.data:
                st.success(f"Result saved: {winner} wins {margin_str}")
            else:
                st.error("❌ Error saving match result.")

        # Refresh the match result log after saving/updating the result
        load_match_result_log()  # Reload the log with the updated result

    except Exception as e:
        st.error(f"❌ Error saving match result: {str(e)}")

# Define the function to load bracket data from Supabase
def load_bracket_data_from_supabase():
    try:
        response = (
            supabase.table("bracket_data")
            .select("json_data")
            .order("timestamp", desc=True)  # ✅ Use 'timestamp' instead of 'created_at'
            .limit(1)
            .execute()
        )

        if response.data and len(response.data) > 0:
            bracket_df = pd.read_json(response.data[0]["json_data"], orient="split")
            return bracket_df
        else:
            st.warning("No bracket data found.")
            return pd.DataFrame()
    except Exception as e:
        st.error("❌ Error loading bracket data from Supabase.")
        st.code(str(e))
        return pd.DataFrame()


# --- Initialize Bracket Data in Session State ---
if "bracket_data" not in st.session_state:
    bracket_df = load_bracket_data_from_supabase()  # Load from Supabase if not in session state
    st.session_state.bracket_data = bracket_df


#-- winner data ---
def get_winner_player(player1, player2, winner_name):
    """Return the full player dict matching the winner_name, or fallback."""
    for p in [player1, player2]:
        if p["name"] == winner_name:
            return p
    return {"name": winner_name, "handicap": "N/A"}  # fallback if no match

# --- Render Match ----
def render_match(player1, player2, winner, readonly=False, key_prefix=""):
    """
    Renders the match between two players.
    - player1, player2: dictionaries containing player info (e.g., name, handicap)
    - winner: the current winner (or "Tie")
    - readonly: if True, makes the match readonly (admin-only input)
    - key_prefix: ensures that each checkbox/radio button has a unique key
    """
    # Check if both players have valid data
    if not player1 or not player2:
        st.error(f"❌ Invalid player data for one or both players: {player1}, {player2}")
        return None
    if "name" not in player1 or "handicap" not in player1:
        st.error(f"❌ Invalid player data for {player1}")
        return None
    if "name" not in player2 or "handicap" not in player2:
        st.error(f"❌ Invalid player data for {player2}")
        return None

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
        if selected_winner != "Tie":
            margin = st.selectbox(
                "Select win margin",
                options=["1 up", "2 and 1", "3 and 2", "4 and 3", "5 and 4"],
                key=margin_key
            )
        else:
            margin = "Tie"  # Ensure margin is "Tie" when winner is "Tie"
        
        # Display result button
        if st.button(f"Save result for {player1['name']} vs {player2['name']}", key=f"submit_{key_prefix}"):
            # Save the result to Supabase
            save_match_result("group_stage", player1['name'], player2['name'], selected_winner, margin)
            st.success(f"Result saved: {selected_winner} wins {margin}")
            return selected_winner
    else:
        # If readonly is True, just display the result
        st.write(f"Match result: {winner}")
        return winner

#--- resolve tiebreakers --
def resolve_tiebreakers(pod_scores):
    unresolved = False
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

        # Resolve second place if there's still a tie
        remaining = sorted_players[sorted_players["name"] != selected].reset_index(drop=True)
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

    return unresolved

# Define the margin lookup dictionary to map string descriptions to numeric values
margin_lookup = {
    "1 up": 1, "2 and 1": 3, "3 and 2": 5, "4 and 3": 7,
    "5 and 4": 9, "6 and 5": 11, "7 and 6": 13, "8 and 7": 15, "9 and 8": 17
}

def compute_pod_standings_from_results(pods, match_results):
    pod_scores = {}

    for pod_name, players in pods.items():
        results = []
        for player in players:
            name = player["name"]
            points, margin = 0, 0

            # Iterate through all match results and calculate points and margins
            for key, result in match_results.items():
                if key.startswith(f"{pod_name}|") and name in key:
                    winner = result.get("winner")
                    margin_str = result.get("margin", "Tie")  # Default to "Tie" if no margin

                    # Ensure margin is numeric
                    if isinstance(margin_str, str):
                        # If margin_str is a string like "1 up", "2 and 1", etc., look it up
                        margin_value = margin_lookup.get(margin_str, 0)  # Default to 0 if not found in lookup
                    else:
                        margin_value = margin_str  # If it's already numeric, use it directly

                    # Update points and margin based on the winner
                    if winner == name:
                        points += 1
                        margin += margin_value  # Add margin for the winner
                    elif winner == "Tie":
                        points += 0.5  # Tie gives half a point
                    else:
                        margin -= margin_value  # Subtract margin for the loser

            results.append({
                "name": name,
                "handicap": player["handicap"],
                "points": points,
                "margin": margin
            })

        pod_scores[pod_name] = pd.DataFrame(results)

    return pod_scores



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
        # Fetch match results directly from Supabase, ordered by created_at (most recent first)
        response = supabase.table("tournament_matches").select("*").order("created_at", desc=True).execute()

        # Check if the response contains data
        if not response.data:
            st.warning("📭 No match results found in the Supabase response.")
            return {}

        # Dictionary to group match results by match pair
        match_dict = defaultdict(list)

        # Group the match results by match pair
        for result in response.data:
            match_key = f"{result['pod']}|{result['player1']} vs {result['player2']}"
            match_dict[match_key].append(result)

        # Dictionary to store the most recent result for each match pair
        latest_match_results = {}

        # Iterate through each match pair and select the most recent result
        for match_key, match_results in match_dict.items():
            # Sort the match results by created_at (timestamp), most recent first
            match_results.sort(key=lambda x: x['created_at'], reverse=True)

            # Pick the latest result (first entry after sorting by timestamp)
            latest_result = match_results[0]
            latest_match_results[match_key] = {
                "winner": latest_result["winner"],
                "margin": latest_result["margin"]
            }

        # Return the dictionary with the most recent match results
        return latest_match_results

    except Exception as e:
        # Handle any errors that occur during the process
        st.error(f"❌ Error loading match results from Supabase: {e}")
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
BRACKET_FILE = "bracket_data.json"
RESULTS_FILE = "match_results.json"

# --- Helper: Label players ---
def label(player):
    return f"{player['name']} ({player['handicap']})"

# --- Update the bracket progression ---
def update_bracket_progression(round_key, winners):
    try:
        # Update the bracket progression in Supabase
        response = supabase.table("bracket_progression").update({round_key: json.dumps([w["name"] for w in winners])}).execute()
        if response.status_code == 200:
            st.success("✅ Bracket progression updated successfully.")
        else:
            st.error(f"❌ Error updating bracket progression: {response.status_code} - {response.error_message}")
    except Exception as e:
        st.error(f"❌ Error updating bracket progression: {str(e)}")

# --- Load updated bracket progression ---
def load_bracket_progression_from_supabase():
    try:
        # Load the current bracket progression from Supabase
        response = supabase.table("bracket_progression").select("*").order("created_at", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]
        else:
            return None
    except Exception as e:
        st.error(f"❌ Error loading bracket progression from Supabase: {str(e)}")
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
    "🔮 Predict Bracket", 
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

    # Show loading spinner while loading match results
    with st.spinner('Loading match results...'):
        match_results = load_match_results()

    st.session_state.match_results = match_results

    pod_results = {}

    # Display match results for all users (both admins and non-admins)
    display_match_result_log()

    for pod_name, players in pods.items():
        with st.expander(pod_name):
            updated_players = simulate_matches(players, pod_name, source="group_stage", editable=st.session_state.authenticated)
            pod_results[pod_name] = pd.DataFrame(updated_players)

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

    # Fetch the most recent match results from Supabase
    match_results = load_match_results()

    # Initialize an empty dictionary to store the standings for each pod
    pod_results = {}

    # Process each pod and calculate points and margin for each player
    for pod_name, players in pods.items():
        updated_players = []
        for player in players:
            name = player['name']
            total_points = 0
            total_margin = 0

            # Iterate through all match results and calculate points and margins
            for key, result in match_results.items():
                if key.startswith(f"{pod_name}|"):
                    if name in key:
                        # Debugging: Print the result to check its structure
                        print(f"Result for {key}: {result}")
                        
                        if isinstance(result, dict):  # Ensure result is a dictionary
                            if result.get("winner") == name:
                                total_points += 1
                                total_margin += result.get("margin", 0)  # Safely access margin
                            elif result.get("winner") == "Tie":
                                total_points += 0.5
                            else:
                                total_margin -= result.get("margin", 0)  # Safely access margin
                        else:
                            print(f"Unexpected data type for result: {type(result)}")
                            total_margin -= 0  # Default to subtracting 0 if result is not a dictionary

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

# --- Bracket Visualization ---
with tabs[3]:
    if "finalized_bracket" not in st.session_state:
        bracket_df = load_bracket_data_from_supabase()
        if bracket_df.empty:
            st.warning("Bracket progression not set yet. Please finalize the bracket in Group Stage.")
            st.stop()
        else:
            st.session_state.finalized_bracket = bracket_df

    bracket_df = st.session_state.finalized_bracket
    icon = "🏌️‍♂️"

    # Load last bracket state from Supabase
    records = supabase.table("bracket_progression").select("*").order("created_at", desc=True).limit(1).execute()
    bracket_data = records.data[0] if records.data else {}
    field_locked = bracket_data.get("field_locked", False)

    def get_player_by_name(name, source_df):
        return next((p for p in source_df.to_dict("records") if p["name"] == name), {"name": name})

    if st.session_state.authenticated:
        st.info("🔐 Admin mode")

        if field_locked:
            st.error("⚠️ The Round of 16 field is locked and cannot be edited.")

        left = bracket_df.iloc[0:8].to_dict("records")
        right = bracket_df.iloc[8:16].to_dict("records")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🟦 Left Side")
            st.markdown("#### 🔒 Round of 16 (Locked)")
            r16_left = []
            for i, (p1_name, p2_name) in enumerate(bracket_data.get("r16_left", [])):
                p1 = get_player_by_name(p1_name, bracket_df)
                p2 = get_player_by_name(p2_name, bracket_df)
                default_winner = bracket_data.get("qf_left", [None] * 4)[i // 2]
                winner_name = render_match(p1, p2, default_winner, readonly=False, key_prefix=f"r16_left_{i}")
                r16_left.append(get_winner_player(p1, p2, winner_name))

            st.markdown("#### 🥉 Quarterfinals")
            qf_left = []
            for i in range(0, len(r16_left), 2):
                if i + 1 < len(r16_left):
                    p1 = r16_left[i]
                    p2 = r16_left[i + 1]
                    default_winner = bracket_data.get("sf_left", [None] * 2)[i // 2] if bracket_data.get("sf_left") else None
                    winner_name = render_match(p1, p2, default_winner, readonly=False, key_prefix=f"qf_left_{i}")
                    qf_left.append(get_winner_player(p1, p2, winner_name))

        with col2:
            st.markdown("### 🟥 Right Side")
            st.markdown("#### 🔒 Round of 16 (Locked)")
            r16_right = []
            for i, (p1_name, p2_name) in enumerate(bracket_data.get("r16_right", [])):
                p1 = get_player_by_name(p1_name, bracket_df)
                p2 = get_player_by_name(p2_name, bracket_df)
                default_winner = bracket_data.get("qf_right", [None] * 4)[i // 2]
                winner_name = render_match(p1, p2, default_winner, readonly=False, key_prefix=f"r16_right_{i}")
                r16_right.append(get_winner_player(p1, p2, winner_name))

            st.markdown("#### 🥉 Quarterfinals")
            qf_right = []
            for i in range(0, len(r16_right), 2):
                if i + 1 < len(r16_right):
                    p1 = r16_right[i]
                    p2 = r16_right[i + 1]
                    default_winner = bracket_data.get("sf_right", [None] * 2)[i // 2] if bracket_data.get("sf_right") else None
                    winner_name = render_match(p1, p2, default_winner, readonly=False, key_prefix=f"qf_right_{i}")
                    qf_right.append(get_winner_player(p1, p2, winner_name))

        st.markdown("### 🏁 Semifinals & Final")
        sf_left = qf_left
        sf_right = qf_right

        if sf_left and sf_right:
            default_finalist_left = bracket_data.get("finalist_left")
            default_finalist_right = bracket_data.get("finalist_right")
            finalist_left = render_match(sf_left[0], sf_left[1], default_finalist_left, readonly=False, key_prefix="sf_left")
            finalist_right = render_match(sf_right[0], sf_right[1], default_finalist_right, readonly=False, key_prefix="sf_right")
            finalist_left_player = get_winner_player(sf_left[0], sf_left[1], finalist_left)
            finalist_right_player = get_winner_player(sf_right[0], sf_right[1], finalist_right)

            champ_default = bracket_data.get("champion")
            champ_choice = st.radio("🏆 Select the Champion",
                                    [label(finalist_left_player), label(finalist_right_player)],
                                    index=0 if champ_default == finalist_left_player["name"] else 1,
                                    key="final_match_radio")
            champion = finalist_left_player if champ_choice == label(finalist_left_player) else finalist_right_player
        else:
            finalist_left_player = None
            finalist_right_player = None
            champion = None

        if st.button("📋 Save Bracket Progress"):
            try:
                updates = {}
                if qf_left: updates["qf_left"] = [p["name"] for p in qf_left]
                if qf_right: updates["qf_right"] = [p["name"] for p in qf_right]
                if sf_left: updates["sf_left"] = [p["name"] for p in sf_left]
                if sf_right: updates["sf_right"] = [p["name"] for p in sf_right]
                if finalist_left_player: updates["finalist_left"] = finalist_left_player["name"]
                if finalist_right_player: updates["finalist_right"] = finalist_right_player["name"]
                if champion: updates["champion"] = champion["name"]

                if updates:
                    supabase.table("bracket_progression").update(updates).eq("id", bracket_data["id"]).execute()
                    st.success("✅ Bracket progress saved.")
                    st.rerun()
                else:
                    st.info("⚠️ Nothing new to save.")
            except Exception as e:
                st.error(f"❌ Failed to save: {e}")

        if field_locked:
            if st.button("🔓 Unlock R16 (Admin Only)", type="primary"):
                try:
                    supabase.table("bracket_progression").update({"field_locked": False}).eq("id", bracket_data["id"]).execute()
                    st.success("✅ Field has been unlocked.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to unlock field: {e}")

    else:
        st.markdown("### 🏆 Finalized Bracket (Read-Only)")
        if not bracket_data:
            st.warning("No bracket progression has been saved yet.")
            st.stop()

        def render_matchups(title, matchups):
            if matchups:
                st.markdown(title)
                for m in matchups:
                    if isinstance(m, list) and len(m) == 2:
                        st.write(f"{m[0]} {icon} vs {m[1]} {icon}")
                    elif isinstance(m, str):
                        st.write(f"{m} {icon}")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🟦 Left Side")
            render_matchups("#### 🔹 Round of 16", bracket_data.get("r16_left", []))
            render_matchups("#### 🥉 Quarterfinals", bracket_data.get("qf_left", []))
            render_matchups("#### 🥈 Semifinalist", bracket_data.get("sf_left", []))

        with col2:
            st.markdown("### 🟥 Right Side")
            render_matchups("#### 🔹 Round of 16", bracket_data.get("r16_right", []))
            render_matchups("#### 🥉 Quarterfinals", bracket_data.get("qf_right", []))
            render_matchups("#### 🥈 Semifinalist", bracket_data.get("sf_right", []))

        if bracket_data.get("finalist_left") and bracket_data.get("finalist_right"):
            st.markdown("### 🏁 Final Match")
            st.write(f"{bracket_data['finalist_left']} {icon} vs {bracket_data['finalist_right']} {icon}")

        if bracket_data.get("champion"):
            st.success(f"🏆 Champion: **{bracket_data['champion']}**")



# --- Predict Bracket ---
with tabs[4]:
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


# --- Leaderboard ---
with tabs[5]:
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
