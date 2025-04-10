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
from datetime import datetime, timezone

PREDICTION_DEADLINE = datetime.fromisoformat(
    st.secrets["predictions"]["deadline"].replace("Z", "+00:00")
)



# --- Connect to Supabase ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

#--- new save bracket function to shared table --
def save_bracket_result(match_id, round_name, player1, player2, winner, margin, status="completed"):
    try:
        data = {
            "match_id": match_id,
            "round": round_name,
            "player1": player1,
            "player2": player2,
            "winner": winner,
            "margin": margin,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        response = supabase.table("tournament_matches") \
            .upsert(data, on_conflict="match_id") \
            .execute()

        if response and response.data:
            st.success(f"✅ Match {match_id} saved: {winner} wins")
        else:
            st.warning(f"⚠️ No response data returned for match {match_id}")

    except Exception as e:
        st.error(f"❌ Exception saving match result: {e}")


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

# --- load bracket match results ---
def load_bracket_match_result(match_id):
    try:
        response = supabase.table("tournament_matches") \
            .select("winner, margin") \
            .eq("match_id", match_id) \
            .limit(1) \
            .execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return {}
    except Exception as e:
        st.warning(f"⚠️ Could not load match {match_id}: {e}")
        return {}


# --- Helper: Parse JSON field ---
def parse_json_field(field):
    try:
        st.write("👀 Field type:", type(field), "→", field)
        if isinstance(field, str):
            return json.loads(field)
        elif isinstance(field, list):
            return field
        elif isinstance(field, dict):  # Supabase jsonb might come as dict
            return list(field.values())  # flatten if needed
        return []
    except Exception as e:
        st.warning(f"⚠️ Failed to parse field: {e}")
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
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        #st.write("📦 Raw Supabase response:", response.data)  # <--- DEBUG LINE

        if response.data and len(response.data) > 0:
            bracket_df = pd.read_json(response.data[0]["json_data"], orient="split")
            #st.write("✅ Parsed Bracket DataFrame:", bracket_df)  # <--- DEBUG LINE
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
    st.session_state.finalized_bracket = bracket_df


#-- winner data ---
def get_winner_player(player1, player2, winner_name):
    """Return the full player dict matching the winner_name, or fallback."""
    for p in [player1, player2]:
        if p["name"] == winner_name:
            return p
    return {"name": winner_name, "handicap": "N/A"}  # fallback if no match

def render_match(player1, player2, winner, readonly=False, key_prefix="", stage="group_stage"):
    if not player1 or not player2:
        st.error(f"❌ Invalid player data for one or both players: {player1}, {player2}")
        return "Tie"

    st.write(f"### Match: {player1['name']} vs {player2['name']}")
    st.write(f"**Handicaps**: {player1['handicap']} vs {player2['handicap']}")
    st.write(f"**Current Winner**: {winner if winner != 'Tie' else 'No winner yet'}")

    if readonly:
        st.write(f"Match result: {winner}")
        return winner

    winner_key = f"{key_prefix}_winner"
    margin_key = f"{key_prefix}_margin"

    options = [player1['name'], player2['name'], "Tie"]
    default_index = options.index(winner) if winner in options else 2

    selected_winner = st.radio(
        "Select winner",
        options=options,
        index=default_index,
        key=winner_key
    )

    if selected_winner != "Tie":
        margin = st.selectbox(
            "Select win margin",
            options=["1 up", "2 and 1", "3 and 2", "4 and 3", "5 and 4"],
            key=margin_key
        )
    else:
        margin = "Tie"

    # Optional: Save the result when button is clicked (good for logs)
    if st.button(f"Save result for {player1['name']} vs {player2['name']}", key=f"submit_{key_prefix}"):
        save_match_result(stage, player1['name'], player2['name'], selected_winner, margin)
        st.success(f"Result saved: {selected_winner} wins {margin}")

    return selected_winner  # Always return winner, even if not "saved"

#--- new render match ui ---
def render_bracket_match_ui(match_id, round_name, player1, player2):
    saved_result = load_bracket_match_result(match_id)
    saved_winner = saved_result.get("winner", "")
    saved_margin_value = saved_result.get("margin", None)
    saved_margin_label = next((k for k, v in margin_lookup.items() if v == saved_margin_value), "1 up")

    st.markdown(f"### {round_name} – Match {match_id}")
    st.write(f"**{player1} vs {player2}**")

    if st.session_state.authenticated:
        winner = st.selectbox(
            "Select winner",
            options=["", player1, player2],
            index=["", player1, player2].index(saved_winner) if saved_winner in [player1, player2] else 0,
            key=f"winner_select_{match_id}"
        )

        if winner:
            margin = st.selectbox(
                "Select win margin",
                options=list(margin_lookup.keys()),
                index=list(margin_lookup.keys()).index(saved_margin_label) if saved_margin_label in margin_lookup else 0,
                key=f"margin_select_{match_id}"
            )

            if st.button("Submit Result", key=f"submit_btn_{match_id}"):
                save_bracket_result(
                    match_id=match_id,
                    round_name=round_name,
                    player1=player1,
                    player2=player2,
                    winner=winner,
                    margin=margin_lookup.get(margin, 1)
                )
    else:
        if saved_winner:
            margin_label = saved_margin_label or "1 up"
            st.success(f"🏆 **Winner: {saved_winner}** ({margin_label})")
        else:
            st.info("⏳ Match not yet decided.")


# ---- Get winner from bracket ---
import time

def get_bracket_winner(match_id, retries=3, delay=1):
    for attempt in range(retries):
        try:
            response = supabase.table("tournament_matches") \
                .select("winner") \
                .eq("match_id", match_id) \
                .limit(1) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]["winner"]
            return None

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                st.warning(f"⚠️ Could not fetch winner for match {match_id}: {e}")
                return None


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
        res = supabase.table("bracket_progression") \
                      .select("*") \
                      .order("created_at", desc=True) \
                      .limit(1).execute()

        if not res.data:
            st.warning("📭 No bracket progression data found.")
            return {}

        record = res.data[0]

        # Debug dump
        #st.write("📦 Full Raw Bracket Progression Record:", record)

        return record
    except Exception as e:
        st.error(f"❌ Failed to load bracket progression: {e}")
        return {}

def save_final_results_to_supabase(final_data):
    try:
        response = supabase.table("final_results").insert(final_data).execute()
        if response.data:
            st.success("✅ Final results saved to Supabase.")
        else:
            st.error("❌ Failed to save final results.")
    except Exception as e:
        st.error(f"❌ Error saving final results: {e}")


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
with tabs[5]:
    st.warning("🚨 ENTERED Leaderboard tab")
    st.write("👋 Hello, world!")

# Load shared bracket data
if "bracket_data" not in st.session_state:
    bracket_df = load_bracket_data_from_supabase()
    st.session_state.finalized_bracket = bracket_df
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
        match_results = st.session_state.get("match_results") or load_match_results()
    st.session_state.match_results = match_results

    pod_results = {}
    display_match_result_log()

    for pod_name, players in pods.items():
        with st.expander(pod_name):
            updated_players = simulate_matches(players, pod_name, source="group_stage", editable=st.session_state.authenticated)
            pod_results[pod_name] = pd.DataFrame(updated_players)

    # --- Admin-only Tiebreaker and Finalize Logic ---
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

            # Resolve 1st place
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

            # Resolve 2nd place
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

        # --- Finalize Bracket ---
if st.session_state.get("tiebreaks_resolved", False):
    if st.button("🏁 Finalize Bracket and Seed Field"):
        bracket_df = build_bracket_df_from_pod_scores(pod_scores, st.session_state.tiebreak_selections)
        st.session_state.finalized_bracket = bracket_df

        # Save bracket to Supabase (for prediction tab, etc.)
        save_bracket_data(bracket_df)

        # --- Build Round of 16 matchups ---
        r16_left = [
            [bracket_df.iloc[0]["name"], bracket_df.iloc[15]["name"]],
            [bracket_df.iloc[7]["name"], bracket_df.iloc[8]["name"]],
            [bracket_df.iloc[4]["name"], bracket_df.iloc[11]["name"]],
            [bracket_df.iloc[3]["name"], bracket_df.iloc[12]["name"]],
        ]
        r16_right = [
            [bracket_df.iloc[1]["name"], bracket_df.iloc[14]["name"]],
            [bracket_df.iloc[6]["name"], bracket_df.iloc[9]["name"]],
            [bracket_df.iloc[5]["name"], bracket_df.iloc[10]["name"]],
            [bracket_df.iloc[2]["name"], bracket_df.iloc[13]["name"]],
        ]

        # Save R16 matchups to bracket_progression
        try:
            record = {
                "r16_left": json.dumps(r16_left),
                "r16_right": json.dumps(r16_right),
                "qf_left": json.dumps([]),
                "qf_right": json.dumps([]),
                "sf_left": json.dumps([]),
                "sf_right": json.dumps([]),
                "finalist_left": None,
                "finalist_right": None,
                "champion": None,
                "field_locked": True,
                "created_at": datetime.utcnow().isoformat()
            }

            result = supabase.table("bracket_progression").insert(record).execute()

            if result.data and len(result.data) > 0:
                bracket_id = result.data[0]["id"]
                st.session_state.bracket_data = {**record, "id": bracket_id}
                st.success("✅ Bracket finalized and seeded. Ready for knockout rounds!")
                st.dataframe(bracket_df)
            else:
                st.error("❌ Bracket was inserted, but no ID was returned.")

        except Exception as e:
            st.error(f"❌ Failed to save bracket progression: {e}")




# --- Standings ---
# --- Standings ---
with tabs[2]:
    st.subheader("📋 Standings")

    match_results = load_match_results()
    if not match_results:
        st.info("📭 No match results have been entered yet.")
        st.stop()

    pod_results = {}

    for pod_name, players in pods.items():
        updated_players = []
        for player in players:
            name = player['name']
            total_points = 0
            total_margin = 0

            for match_key, result in match_results.items():
                if match_key.startswith(f"{pod_name}|") and name in match_key:
                    winner = result.get("winner", "")
                    margin_val = result.get("margin", 0)

                    if winner == name:
                        total_points += 1
                        total_margin += margin_val
                    elif winner == "Tie":
                        total_points += 0.5
                    else:
                        total_margin -= margin_val

            updated_players.append({
                "Player": name,
                "Handicap": player["handicap"] if player["handicap"] is not None else "N/A",
                "Points": total_points,
                "Margin": total_margin
            })

        df = pd.DataFrame(updated_players)
        if not df.empty:
            df = df.sort_values(by=["Points", "Margin"], ascending=False)
            pod_results[pod_name] = df

    # Display
    if pod_results:
        for pod_name, df in pod_results.items():
            with st.expander(f"📦 {pod_name} Standings", expanded=False):
                st.dataframe(df, use_container_width=True)
    else:
        st.warning("No standings available yet.")


# --- Bracket Tab ---
# --- Bracket Tab ---
with tabs[3]:
    st.subheader("🏆 Bracket Stage")

    def decode_if_json(raw):
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return raw
        return raw

    def load_or_refresh_bracket_data():
        bracket_data = st.session_state.get("bracket_data", {})
        bracket_id = bracket_data.get("id")

        if not bracket_id:
            bracket_data = load_bracket_progression_from_supabase()
            if bracket_data and "id" in bracket_data:
                st.session_state.bracket_data = bracket_data
            else:
                st.warning("❌ No valid bracket record found. Please finalize the bracket in the Group Stage.")
                st.stop()

        return st.session_state.bracket_data

    def get_bracket_winner(match_id):
        try:
            response = supabase.table("tournament_matches") \
                .select("winner") \
                .eq("match_id", match_id) \
                .limit(1) \
                .execute()
            if response.data and len(response.data) > 0:
                return response.data[0]["winner"]
            return None
        except Exception as e:
            st.warning(f"⚠️ Could not fetch winner for match {match_id}: {e}")
            return None

    def save_final_results_to_supabase(final_data):
        try:
            response = supabase.table("final_results").insert(final_data).execute()
            if response.data:
                st.success("✅ Final results saved to Supabase.")
            else:
                st.error("❌ Failed to save final results.")
        except Exception as e:
            st.error(f"❌ Error saving final results: {e}")

    bracket_data = load_or_refresh_bracket_data()
    bracket_id = bracket_data.get("id")

    if "finalized_bracket" not in st.session_state or st.session_state.finalized_bracket is None:
        st.session_state.finalized_bracket = load_bracket_data_from_supabase()

    bracket_df = st.session_state.finalized_bracket
    if bracket_df is None or bracket_df.empty:
        st.warning("❌ Bracket data not available. Finalize in Group Stage.")
        st.stop()

    r16_left = decode_if_json(bracket_data.get("r16_left"))
    r16_right = decode_if_json(bracket_data.get("r16_right"))

    icon = "🏌️"

    if st.session_state.authenticated:
        st.success("🔐 Admin Mode Enabled")

    col1, col2 = st.columns(2)

    qf_left = []
    qf_right = []
    sf_left = []
    sf_right = []
    finalists = []
    champion = None

    with col1:
        st.markdown("### 🟦 Left Side")

        for i, (p1_name, p2_name) in enumerate(r16_left):
            render_bracket_match_ui(100 + i, "Round of 16", p1_name, p2_name)

        for i in range(0, len(r16_left), 2):
            if i + 1 < len(r16_left):
                w1 = get_bracket_winner(100 + i)
                w2 = get_bracket_winner(100 + i + 1)
                if w1 and w2:
                    render_bracket_match_ui(200 + i, "Quarterfinals", w1, w2)
                    qf_left.append((w1, w2))

        if len(qf_left) >= 2:
            w1 = get_bracket_winner(200)
            w2 = get_bracket_winner(202)
            if w1 and w2:
                render_bracket_match_ui(300, "Semifinal", w1, w2)
                sf_left.append((w1, w2))

    with col2:
        st.markdown("### 🟥 Right Side")

        for i, (p1_name, p2_name) in enumerate(r16_right):
            render_bracket_match_ui(110 + i, "Round of 16", p1_name, p2_name)

        for i in range(0, len(r16_right), 2):
            if i + 1 < len(r16_right):
                w1 = get_bracket_winner(110 + i)
                w2 = get_bracket_winner(110 + i + 1)
                if w1 and w2:
                    render_bracket_match_ui(210 + i, "Quarterfinals", w1, w2)
                    qf_right.append((w1, w2))

        if len(qf_right) >= 2:
            w1 = get_bracket_winner(210)
            w2 = get_bracket_winner(212)
            if w1 and w2:
                render_bracket_match_ui(310, "Semifinal", w1, w2)
                sf_right.append((w1, w2))

    if len(sf_left) == 1 and len(sf_right) == 1:
        left_finalist = get_bracket_winner(300)
        right_finalist = get_bracket_winner(310)
        if left_finalist and right_finalist:
            render_bracket_match_ui(400, "Final", left_finalist, right_finalist)
            champion = get_bracket_winner(400)
            if champion:
                st.success(f"🏆 Champion: **{champion}**")

                if st.session_state.authenticated:
                    if st.button("💾 Save Final Results to Leaderboard"):
                        final_data = {
                            "r16_left": json.dumps([p1 for p1, p2 in r16_left]),
                            "r16_right": json.dumps([p1 for p1, p2 in r16_right]),
                            "qf_left": json.dumps([p1 for p1, p2 in qf_left]),
                            "qf_right": json.dumps([p1 for p1, p2 in qf_right]),
                            "sf_left": json.dumps([p1 for p1, p2 in sf_left]),
                            "sf_right": json.dumps([p1 for p1, p2 in sf_right]),
                            "finalist_left": left_finalist,
                            "finalist_right": right_finalist,
                            "champion": champion,
                            "created_at": datetime.utcnow().isoformat()
                        }
                        save_final_results_to_supabase(final_data)


# --- Predict Bracket ---
with tabs[4]:
    st.subheader("🔮 Predict the Bracket")

    now = datetime.now(timezone.utc)
    predictions_locked = now > PREDICTION_DEADLINE

    bracket_data = load_bracket_progression_from_supabase()
    r16_left = decode_if_json(bracket_data.get("r16_left"))
    r16_right = decode_if_json(bracket_data.get("r16_right"))

    if not r16_left or not r16_right or len(r16_left) < 4 or len(r16_right) < 4:
        st.warning("Bracket is not finalized. Prediction will open once the field of 16 is set.")
        st.stop()

    full_name = st.text_input("Enter your full name to submit your bracket:", key="predictor_name").strip()
    if not full_name:
        st.info("Enter your name to proceed.")
        st.stop()

    user_predictions = load_predictions_from_supabase()
    existing_names = [p["name"].strip().lower() for p in user_predictions]
    user_name = full_name.lower()

    if predictions_locked or user_name in existing_names:
        st.warning("⛔ Predictions are locked or already submitted.")
        st.stop()

    def pick_winners_with_dropdown(matchups, round_label, key_prefix):
        winners = []
        for i, match in enumerate(matchups):
            if isinstance(match, list) and len(match) == 2:
                p1, p2 = match
                winner = st.selectbox(
                    f"{round_label} Match {i + 1}: {p1} vs {p2}",
                    options=["-- Select Winner --", p1, p2],
                    key=f"{key_prefix}_{i}"
                )
                if winner == "-- Select Winner --":
                    st.warning(f"Please pick a winner for Match {i + 1} of {round_label}")
                    st.stop()
                winners.append(winner)
        return winners

    # --- R16 ---
    st.markdown("### 🏁 Round of 16")
    pred_r16_left = pick_winners_with_dropdown(r16_left, "R16 Left", "r16L")
    pred_r16_right = pick_winners_with_dropdown(r16_right, "R16 Right", "r16R")

    # --- QF ---
    st.markdown("### 🎯 Quarterfinals")
    qf_left = [[pred_r16_left[i], pred_r16_left[i+1]] for i in range(0, 4, 2)]
    qf_right = [[pred_r16_right[i], pred_r16_right[i+1]] for i in range(0, 4, 2)]
    pred_qf_left = pick_winners_with_dropdown(qf_left, "QF Left", "qfL")
    pred_qf_right = pick_winners_with_dropdown(qf_right, "QF Right", "qfR")

    # --- SF ---
    st.markdown("### 🥊 Semifinals")
    sf_left = [[pred_qf_left[0], pred_qf_left[1]]]
    sf_right = [[pred_qf_right[0], pred_qf_right[1]]]
    pred_sf_left = pick_winners_with_dropdown(sf_left, "SF Left", "sfL")
    pred_sf_right = pick_winners_with_dropdown(sf_right, "SF Right", "sfR")

    # --- Final ---
    st.markdown("### 🏆 Final Match")
    finalist_left = pred_sf_left[0]
    finalist_right = pred_sf_right[0]
    champion = st.selectbox(
        f"Final: {finalist_left} vs {finalist_right}",
        options=["-- Select Winner --", finalist_left, finalist_right],
        key="champion"
    )
    if champion == "-- Select Winner --":
        st.warning("Please select a Champion before submitting.")
        st.stop()

    # --- Submit ---
    if st.button("🚀 Submit My Bracket Prediction"):
        try:
            data = {
                "name": full_name,
                "timestamp": datetime.utcnow().isoformat(),
                "r16_left": json.dumps(pred_r16_left),
                "r16_right": json.dumps(pred_r16_right),
                "qf_left": json.dumps(pred_qf_left),
                "qf_right": json.dumps(pred_qf_right),
                "sf_left": json.dumps(pred_sf_left),
                "sf_right": json.dumps(pred_sf_right),
                "finalist_left": finalist_left,
                "finalist_right": finalist_right,
                "champion": champion
            }
            supabase.table("predictions").insert(data).execute()
            st.success("✅ Your bracket has been submitted!")
            st.rerun()
        except Exception as e:
            st.error("❌ Failed to submit your prediction.")
            st.code(str(e))




# --- Leaderboard Tab ---
with tabs[5]:
    st.warning("🚨 ENTERED tab[5]")
    st.write("👋 Hello, world!")
