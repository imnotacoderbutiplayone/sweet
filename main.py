# --- Shared Helpers ---
def sanitize_key(key: str) -> str:
    return key.replace(" ", "_").replace("|", "_").replace("&", "and").replace(":", "_").lower()

def render_match(p1, p2, default="Tie", readonly=False, key_prefix="", stage=""):
    key = f"{stage}_{key_prefix}_winner"
    options = [p1["name"], p2["name"], "Tie"]
    if readonly:
        st.write(f"**{p1['name']} vs {p2['name']}** — Winner: **{default}**")
        return default
    return st.radio(f"{p1['name']} vs {p2['name']}", options, index=options.index(default), key=key)

def get_winner_player(p1, p2, winner_name):
    if winner_name == p1["name"]:
        return p1
    elif winner_name == p2["name"]:
        return p2
    else:
        return {"name": "Tie"}
        # --- App + Bracket + Group Stage Functions ---

# bracket_helpers.py (Cleaned and Modular)
import graphviz
from datetime import datetime
import streamlit as st
from shared_helpers import render_match, get_winner_player, sanitize_key
from shared_helpers import sanitize_key, render_match, get_winner_player
from shared_helpers import sanitize_key, render_match




# --- Utility Functions ---
def get_player_by_name(name, df):
    return next((p for p in df.to_dict("records") if p["name"] == name), {"name": name, "handicap": "N/A"})
def get_winner_name(match):
    return match.get("winner") if match.get("winner") and match["winner"] != "Tie" else ""
        def get_winner_name(match):
    return match.get("winner") if match.get("winner") and match["winner"] != "Tie" else ""
    # --- Bracket Stage Rendering ---
def render_stage_matches(matches, bracket_df, stage):
    results = []
    for match in matches:
    p1 = get_player_by_name(match["player1"], bracket_df)
    p2 = get_player_by_name(match["player2"], bracket_df)
    default = match.get("winner") or "Tie"
    winner = render_match(p1, p2, default, readonly=False, key_prefix=f"{stage}_{match['match_index']}", stage=stage)
    results.append(get_winner_player(p1, p2, winner))
    return results
        def advance_round(current_matches, bracket_df, next_stage, supabase):
    for i in range(0, len(current_matches), 2):
    if i + 1 >= len(current_matches):
    continue
    w1 = get_winner_name(current_matches[i])
    w2 = get_winner_name(current_matches[i + 1])
    if not w1 or not w2:
    continue
    p1 = get_player_by_name(w1, bracket_df)
    p2 = get_player_by_name(w2, bracket_df)
    update = {
    "player1": p1["name"], "player2": p2["name"],
    "handicap1": p1.get("handicap"), "handicap2": p2.get("handicap")
    }
    supabase.table("tournament_bracket_matches") \
    .update(update) \
    .eq("stage", next_stage) \
    .eq("match_index", i // 2) \
    .execute()
    # --- Bracket Visualization ---
def visualize_bracket(r16, qf, sf, final):
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", size="8,5")
        for match in r16:
    label = f"{safe_name(match.get('player1'))} vs {safe_name(match.get('player2'))}"
    dot.node(f"r16_{match['match_index']}", label, shape="box")
    for match in qf:
    dot.node(f"qf_{match['match_index']}", safe_name(match.get("winner") or "?"))
    for match in sf:
    dot.node(f"sf_{match['match_index']}", safe_name(match.get("winner") or "?"))
    if final:
    dot.node("final_0", safe_name(final[0].get("winner") or "?"), shape="doublecircle")
        for i in range(0, len(r16), 2):
    dot.edge(f"r16_{i}", f"qf_{i//2}")
    dot.edge(f"r16_{i+1}", f"qf_{i//2}")
    for i in range(0, len(qf), 2):
    dot.edge(f"qf_{i}", f"sf_{i//2}")
    dot.edge(f"qf_{i+1}", f"sf_{i//2}")
    dot.edge("sf_0", "final_0")
    dot.edge("sf_1", "final_0")
        return dot
    # --- Group Stage Helpers ---
def render_pod_matches(pod_name, players, editable, session_results):
    import streamlit as st
    from collections import defaultdict
    from shared_helpers import sanitize_key, render_match  # make sure this works
        margin_lookup = {
    "1 up": 1,
    "2&1": 2,
    "3&2": 3,
    "4&3": 4,
    "5&4": 5,
    }
        results = defaultdict(lambda: {"points": 0, "margin": 0})
    num_players = len(players)
        if num_players < 2:
    st.warning(f"Not enough players in {pod_name} to generate matches.")
    return session_results
        st.markdown(f"<h3 style='color:#1f77b4'>📋 {pod_name}</h3>", unsafe_allow_html=True)
        for i in range(num_players):
    for j in range(i + 1, num_players):
    p1, p2 = players[i], players[j]
    player_names = sorted([p1['name'], p2['name']])
    match_key = f"{pod_name}|{player_names[0]} vs {player_names[1]}"
    base_key = sanitize_key(match_key)
        if editable:
    with st.expander(f"🆚 {p1['name']} vs {p2['name']}", expanded=True):
    prev = session_results.get(match_key, {})
    winner = prev.get("winner", "Tie")
    margin = prev.get("margin", 0)
    margin_str = next((k for k, v in margin_lookup.items() if v == margin), "1 up")
        # Render input
    selected_winner = render_match(
    p1, p2, winner,
    readonly=False,
    key_prefix=base_key,
    stage="group_stage"
    )
    session_results[match_key] = {
    "winner": selected_winner,
    "margin": margin_lookup.get(margin_str, 0)
    }
    else:
    st.info(f"🔒 Admin login required to score matches in {pod_name}")
        return session_results
                def compute_standings_from_results(pods, match_results):
    import pandas as pd
    pod_scores = {}
    for pod_name, players in pods.items():
    records = []
    for player in players:
    name = player["name"]
    points = 0
    margin = 0
    for key, result in match_results.items():
    if key.startswith(f"{pod_name}|") and name in key:
    winner = result.get("winner")
    margin_val = result.get("margin", 0)
    if winner == name:
    points += 1
    margin += margin_val
    elif winner == "Tie":
    points += 0.5
    else:
    margin -= margin_val
    records.append({
    "name": name,
    "handicap": player["handicap"],
    "points": points,
    "margin": margin
    })
    pod_scores[pod_name] = pd.DataFrame(records)
    return pod_scores
    # --- Moved from app_helpers.py ---

# app_helpers.py
import streamlit as st
import pandas as pd
import json
from shared_helpers import render_match, get_winner_player, sanitize_key

def run_group_stage(pods, supabase):
    st.subheader("📊 Group Stage - Match Entry")
        # Initialize results once per session
    if "group_stage_results" not in st.session_state:
    st.session_state.group_stage_results = load_match_results(supabase)
        # Show each pod's matches
    for pod_name, players in pods.items():
    with st.expander(pod_name, expanded=True):
    st.markdown("Match entry UI goes here.")  # placeholder
                    def render_pod_table(pods_df):
    grouped = pods_df.groupby("pod")
    sorted_pods = sorted(grouped, key=lambda x: int(x[0].split()[-1]))
        for pod_name, pod_group in sorted_pods:
    pod_group = pod_group.sort_values(by="handicap", ascending=True)
    pod_group["handicap"] = pod_group["handicap"].apply(lambda x: round(x, 1) if pd.notna(x) else "N/A")
        st.markdown(f"<h3 style='color:#1f77b4;'>\U0001F3CC️ {pod_name}</h3>", unsafe_allow_html=True)
        rows_html = ""
    for _, player in pod_group.iterrows():
    name = player.get("name", "N/A")
    handicap = player.get("handicap", "N/A")
    rows_html += f"<tr><td>{name}</td><td>{handicap}</td></tr>"
        table_html = f"""
    <style>
    .styled-table {{
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 16px;
    width: 100%;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);
    }}
    .styled-table th {{
    background-color: #1f77b4;
    color: white;
    text-align: left;
    padding: 8px;
    }}
    .styled-table td {{
    padding: 8px;
    border-bottom: 1px solid #ddd;
    }}
    .styled-table tr:nth-child(even) {{
    background-color: #f2f2f2;
    }}
    </style>
    <table class="styled-table">
    <thead>
    <tr><th>Name</th><th>Handicap</th></tr>
    </thead>
    <tbody>
    {rows_html}
    </tbody>
    </table>
    """
        st.markdown(table_html, unsafe_allow_html=True)
            def load_match_results(supabase):
    try:
    response = supabase.table("tournament_matches").select("*").execute()
    if response.data:
    result_dict = {}
    for row in response.data:
    match_key = row.get("match_key") or f"{row['pod']}|{row['player1']} vs {row['player2']}"
    result_dict[match_key] = {
    "winner": row.get("winner", "Tie"),
    "margin": row.get("margin", 0)
    }
    return result_dict
    else:
    st.warning("No match results found.")
    return {}
    except Exception as e:
    st.error(f"Error loading match results: {e}")
    return {}
                def show_pods_table(pods):
    for pod_name, players in pods.items():
    st.markdown(f"### \U0001F3CC️ Pod: {pod_name}")
    pod_df = pd.DataFrame(players)
        if "name" not in pod_df.columns or "handicap" not in pod_df.columns:
    st.error(f"Data for {pod_name} missing 'name' or 'handicap'.")
    continue
        render_pod_table(pod_df)
            def group_players_by_pod(players_df):
    return players_df.groupby("pod").apply(lambda x: x.to_dict(orient="records")).to_dict()
            def show_standings(pods, supabase):
    st.subheader("📋 Group Stage Standings")
    match_results = load_match_results(supabase)
    pod_scores = compute_standings_from_results(pods, match_results)
        for pod_name, df in pod_scores.items():
    with st.expander(pod_name):
    df = df.sort_values(by=["points", "margin"], ascending=False)
    st.dataframe(df, use_container_width=True)
            def run_bracket_stage(players_df, supabase):
    st.subheader("\U0001F3C6 Bracket Stage")
    bracket_df = load_bracket_data_from_supabase(supabase)
    if bracket_df.empty:
    st.warning("Field of 16 not finalized yet.")
    return
        r16 = load_matches_by_stage(supabase, "r16")
    qf = load_matches_by_stage(supabase, "qf")
    sf = load_matches_by_stage(supabase, "sf")
    final = load_matches_by_stage(supabase, "final")
        col1, col2 = st.columns(2)
    if st.session_state.authenticated:
    with col1:
    render_stage_matches(r16, bracket_df, "r16")
    render_stage_matches(qf, bracket_df, "qf")
    with col2:
    render_stage_matches(sf, bracket_df, "sf")
    render_stage_matches(final, bracket_df, "final")
        st.graphviz_chart(visualize_bracket(r16, qf, sf, final))
        if st.button("Advance Bracket"):
    advance_round(r16, bracket_df, "qf", supabase)
    advance_round(qf, bracket_df, "sf", supabase)
    advance_round(sf, bracket_df, "final", supabase)
            def run_predictions_tab(supabase):
        st.subheader("🔮 Predict the Bracket")
    bracket_df = load_bracket_data_from_supabase(supabase)
    if bracket_df.empty:
    st.warning("Predictions available once field is set.")
    return
        left = bracket_df.iloc[0:8].reset_index(drop=True)
    right = bracket_df.iloc[8:16].reset_index(drop=True)
        full_name = st.text_input("Enter your full name:")
    if not full_name:
    st.stop()
        predictions = supabase.table("predictions").select("name").execute().data
    if has_user_submitted_prediction(full_name, predictions):
    st.warning("You already submitted a prediction.")
    return
        pred_r16_left = predict_round("R16 Left", left.to_dict("records"), f"PL16_{full_name}")
    pred_r16_right = predict_round("R16 Right", right.to_dict("records"), f"PR16_{full_name}")
    pred_qf_left = predict_round("QF Left", pred_r16_left, f"PLQF_{full_name}")
    pred_qf_right = predict_round("QF Right", pred_r16_right, f"PRQF_{full_name}")
    pred_sf_left = predict_round("SF Left", pred_qf_left, f"PLSF_{full_name}")
    pred_sf_right = predict_round("SF Right", pred_qf_right, f"PRSF_{full_name}")
        finalist_left = pred_sf_left[0]
    finalist_right = pred_sf_right[0]
    champ_pick = st.radio("\U0001F3C6 Champion", [finalist_left["name"], finalist_right["name"]], key=f"champ_{full_name}")
    champion = finalist_left if champ_pick == finalist_left["name"] else finalist_right
        if st.button("Submit Prediction"):
    save_user_prediction(supabase, full_name, finalist_left, finalist_right, champion,
    pred_r16_left, pred_r16_right, pred_qf_left, pred_qf_right)
    st.success("✅ Prediction submitted!")
            def show_leaderboard(supabase):
    st.subheader("\U0001F3C5 Leaderboard")
        predictions = supabase.table("predictions").select("*").execute().data
    final_result = supabase.table("final_results").select("*").order("created_at", desc=True).limit(1).execute().data
        if not predictions or not final_result:
    st.info("Waiting for predictions or final results.")
    return
        actual = final_result[0]
    actual_results = {
    "r16_left": json.loads(actual.get("r16_left", "[]")),
    "r16_right": json.loads(actual.get("r16_right", "[]")),
    "qf_left": json.loads(actual.get("qf_left", "[]")),
    "qf_right": json.loads(actual.get("qf_right", "[]")),
    "sf_left": json.loads(actual.get("sf_left", "[]")),
    "sf_right": json.loads(actual.get("sf_right", "[]")),
    "champion": actual.get("champion", "")
    }
        leaderboard = [
    {
    "Name": row["name"],
    "Score": score_prediction(row, actual_results),
    "Submitted At": row["timestamp"].replace("T", " ")[:19] + " UTC"
    }
    for row in predictions
    ]
        df = pd.DataFrame(leaderboard).sort_values(by=["Score", "Submitted At"], ascending=[False, True])
    df.insert(0, "Rank", range(1, len(df) + 1))
    st.dataframe(df, use_container_width=True)
            def show_how_it_works():
    st.header("\U0001F4D8 How It Works")
    st.markdown("""
    ### 🏌️ Tournament Format
    - Round Robin (Group Stage) → Bracket of 16
    - Single Elimination: R16 → QF → SF → Final
        ### 🧠 Prediction Scoring
    | Round      | Points |
    |------------|--------|
    | R16 Pick   | 1 pt   |
    | QF Pick    | 3 pts  |
    | SF Pick    | 5 pts  |
    | Champion   | 10 pts |
        - Correct position matters — picking a name in the wrong spot won’t earn points.
    - Tie goes to earlier submission.
    - You can only submit once.
    """)
    import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

from app_helpers import (
run_group_stage,
render_pod_table,
show_standings,
run_predictions_tab,
show_leaderboard,
show_how_it_works,
group_players_by_pod
)

from bracket_helpers import (
run_bracket_stage,
render_pod_matches,
compute_standings_from_results,
resolve_tiebreakers,
build_bracket_df_from_pod_scores,
save_bracket_data
)

# --- Config ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# --- Supabase Init ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    supabase = init_supabase()

# --- Auth ---
admin_password = st.secrets["admin_password"]["password"]
general_password = st.secrets["general_password"]["password"]

# Initialize session state variables
if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
    if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Check if the user is authenticated
if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament Login")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == general_password:
            st.session_state.app_authenticated = True
            st.rerun()  # Refresh to show logged-in state
            else:
            st.error("Incorrect password.")
    st.stop()  # Stop further execution until the user is authenticated

# Sidebar Admin Login
st.sidebar.header("🔐 Admin Login")
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.rerun()  # Refresh to show logged-in state
            else:
            st.sidebar.error("Wrong password.")
            else:
                if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()  # Refresh to show logged-out state

# --- Tabs ---
tabs = st.tabs([
"📁 Pods Overview",
"📊 Group Stage",
"📋 Standings",
"🏆 Bracket",
"🔮 Predict Bracket",
"🏅 Leaderboard",
"📘 How It Works"
])

# --- Shared Data ---
players_response = supabase.table("players").select("*").execute()
players_df = pd.DataFrame(players_response.data)
pods = group_players_by_pod(players_df)

# --- Tab 0: Pods Overview ---
with tabs[0]:
    st.subheader("📁 Pods Overview")
    render_pod_table(players_df)
    st.subheader("📁 Pods Overview")
    render_pod_table(players_df)

# --- Tab 1: Group Stage ---
with tabs[1]:
    run_group_stage(pods, supabase)

# --- Tab 2: Standings ---
with tabs[2]:
    show_standings(pods, supabase)

# --- Tab 3: Bracket ---
with tabs[3]:
    run_bracket_stage(players_df, supabase)

# --- Tab 4: Predict Bracket ---
with tabs[4]:
    run_predictions_tab(supabase)

# --- Tab 5: Leaderboard ---
with tabs[5]:
    show_leaderboard(supabase)

# --- Tab 6: How It Works ---
with tabs[6]:
    show_how_it_works()        # --- App + Bracket + Group Stage Functions ---

# bracket_helpers.py (Cleaned and Modular)
import graphviz
from datetime import datetime
import streamlit as st
from shared_helpers import render_match, get_winner_player, sanitize_key
from shared_helpers import sanitize_key, render_match, get_winner_player
from shared_helpers import sanitize_key, render_match




# --- Utility Functions ---
def safe_name(name):
    return name if name and name != "" else "?"
        def get_player_by_name(name, df):
    return next((p for p in df.to_dict("records") if p["name"] == name), {"name": name, "handicap": "N/A"})
        def get_winner_name(match):
    return match.get("winner") if match.get("winner") and match["winner"] != "Tie" else ""
    # --- Bracket Stage Rendering ---
def render_stage_matches(matches, bracket_df, stage):
    results = []
    for match in matches:
    p1 = get_player_by_name(match["player1"], bracket_df)
    p2 = get_player_by_name(match["player2"], bracket_df)
    default = match.get("winner") or "Tie"
    winner = render_match(p1, p2, default, readonly=False, key_prefix=f"{stage}_{match['match_index']}", stage=stage)
    results.append(get_winner_player(p1, p2, winner))
    return results
        def advance_round(current_matches, bracket_df, next_stage, supabase):
    for i in range(0, len(current_matches), 2):
    if i + 1 >= len(current_matches):
    continue
    w1 = get_winner_name(current_matches[i])
    w2 = get_winner_name(current_matches[i + 1])
    if not w1 or not w2:
    continue
    p1 = get_player_by_name(w1, bracket_df)
    p2 = get_player_by_name(w2, bracket_df)
    update = {
    "player1": p1["name"], "player2": p2["name"],
    "handicap1": p1.get("handicap"), "handicap2": p2.get("handicap")
    }
    supabase.table("tournament_bracket_matches") \
    .update(update) \
    .eq("stage", next_stage) \
    .eq("match_index", i // 2) \
    .execute()
    # --- Bracket Visualization ---
def visualize_bracket(r16, qf, sf, final):
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", size="8,5")
        for match in r16:
    label = f"{safe_name(match.get('player1'))} vs {safe_name(match.get('player2'))}"
    dot.node(f"r16_{match['match_index']}", label, shape="box")
    for match in qf:
    dot.node(f"qf_{match['match_index']}", safe_name(match.get("winner") or "?"))
    for match in sf:
    dot.node(f"sf_{match['match_index']}", safe_name(match.get("winner") or "?"))
    if final:
    dot.node("final_0", safe_name(final[0].get("winner") or "?"), shape="doublecircle")
        for i in range(0, len(r16), 2):
    dot.edge(f"r16_{i}", f"qf_{i//2}")
    dot.edge(f"r16_{i+1}", f"qf_{i//2}")
    for i in range(0, len(qf), 2):
    dot.edge(f"qf_{i}", f"sf_{i//2}")
    dot.edge(f"qf_{i+1}", f"sf_{i//2}")
    dot.edge("sf_0", "final_0")
    dot.edge("sf_1", "final_0")
        return dot
    # --- Group Stage Helpers ---
def render_pod_matches(pod_name, players, editable, session_results):
    import streamlit as st
    from collections import defaultdict
    from shared_helpers import sanitize_key, render_match  # make sure this works
        margin_lookup = {
    "1 up": 1,
    "2&1": 2,
    "3&2": 3,
    "4&3": 4,
    "5&4": 5,
    }
        results = defaultdict(lambda: {"points": 0, "margin": 0})
    num_players = len(players)
        if num_players < 2:
    st.warning(f"Not enough players in {pod_name} to generate matches.")
    return session_results
        st.markdown(f"<h3 style='color:#1f77b4'>📋 {pod_name}</h3>", unsafe_allow_html=True)
        for i in range(num_players):
    for j in range(i + 1, num_players):
    p1, p2 = players[i], players[j]
    player_names = sorted([p1['name'], p2['name']])
    match_key = f"{pod_name}|{player_names[0]} vs {player_names[1]}"
    base_key = sanitize_key(match_key)
        if editable:
    with st.expander(f"🆚 {p1['name']} vs {p2['name']}", expanded=True):
    prev = session_results.get(match_key, {})
    winner = prev.get("winner", "Tie")
    margin = prev.get("margin", 0)
    margin_str = next((k for k, v in margin_lookup.items() if v == margin), "1 up")
        # Render input
    selected_winner = render_match(
    p1, p2, winner,
    readonly=False,
    key_prefix=base_key,
    stage="group_stage"
    )
    session_results[match_key] = {
    "winner": selected_winner,
    "margin": margin_lookup.get(margin_str, 0)
    }
    else:
    st.info(f"🔒 Admin login required to score matches in {pod_name}")
        return session_results
                def compute_standings_from_results(pods, match_results):
    import pandas as pd
    pod_scores = {}
    for pod_name, players in pods.items():
    records = []
    for player in players:
    name = player["name"]
    points = 0
    margin = 0
    for key, result in match_results.items():
    if key.startswith(f"{pod_name}|") and name in key:
    winner = result.get("winner")
    margin_val = result.get("margin", 0)
    if winner == name:
    points += 1
    margin += margin_val
    elif winner == "Tie":
    points += 0.5
    else:
    margin -= margin_val
    records.append({
    "name": name,
    "handicap": player["handicap"],
    "points": points,
    "margin": margin
    })
    pod_scores[pod_name] = pd.DataFrame(records)
    return pod_scores
    # --- Moved from app_helpers.py ---

# app_helpers.py
import streamlit as st
import pandas as pd
import json
from shared_helpers import render_match, get_winner_player, sanitize_key

def run_group_stage(pods, supabase):
    st.subheader("📊 Group Stage - Match Entry")
        # Initialize results once per session
    if "group_stage_results" not in st.session_state:
    st.session_state.group_stage_results = load_match_results(supabase)
        # Show each pod's matches
    for pod_name, players in pods.items():
    with st.expander(pod_name, expanded=True):
    st.markdown("Match entry UI goes here.")  # placeholder
                    def render_pod_table(pods_df):
    grouped = pods_df.groupby("pod")
    sorted_pods = sorted(grouped, key=lambda x: int(x[0].split()[-1]))
        for pod_name, pod_group in sorted_pods:
    pod_group = pod_group.sort_values(by="handicap", ascending=True)
    pod_group["handicap"] = pod_group["handicap"].apply(lambda x: round(x, 1) if pd.notna(x) else "N/A")
        st.markdown(f"<h3 style='color:#1f77b4;'>\U0001F3CC️ {pod_name}</h3>", unsafe_allow_html=True)
        rows_html = ""
    for _, player in pod_group.iterrows():
    name = player.get("name", "N/A")
    handicap = player.get("handicap", "N/A")
    rows_html += f"<tr><td>{name}</td><td>{handicap}</td></tr>"
        table_html = f"""
    <style>
    .styled-table {{
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 16px;
    width: 100%;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);
    }}
    .styled-table th {{
    background-color: #1f77b4;
    color: white;
    text-align: left;
    padding: 8px;
    }}
    .styled-table td {{
    padding: 8px;
    border-bottom: 1px solid #ddd;
    }}
    .styled-table tr:nth-child(even) {{
    background-color: #f2f2f2;
    }}
    </style>
    <table class="styled-table">
    <thead>
    <tr><th>Name</th><th>Handicap</th></tr>
    </thead>
    <tbody>
    {rows_html}
    </tbody>
    </table>
    """
        st.markdown(table_html, unsafe_allow_html=True)
            def load_match_results(supabase):
    try:
    response = supabase.table("tournament_matches").select("*").execute()
    if response.data:
    result_dict = {}
    for row in response.data:
    match_key = row.get("match_key") or f"{row['pod']}|{row['player1']} vs {row['player2']}"
    result_dict[match_key] = {
    "winner": row.get("winner", "Tie"),
    "margin": row.get("margin", 0)
    }
    return result_dict
    else:
    st.warning("No match results found.")
    return {}
    except Exception as e:
    st.error(f"Error loading match results: {e}")
    return {}
                def show_pods_table(pods):
    for pod_name, players in pods.items():
    st.markdown(f"### \U0001F3CC️ Pod: {pod_name}")
    pod_df = pd.DataFrame(players)
        if "name" not in pod_df.columns or "handicap" not in pod_df.columns:
    st.error(f"Data for {pod_name} missing 'name' or 'handicap'.")
    continue
        render_pod_table(pod_df)
            def group_players_by_pod(players_df):
    return players_df.groupby("pod").apply(lambda x: x.to_dict(orient="records")).to_dict()
            def show_standings(pods, supabase):
    st.subheader("📋 Group Stage Standings")
    match_results = load_match_results(supabase)
    pod_scores = compute_standings_from_results(pods, match_results)
        for pod_name, df in pod_scores.items():
    with st.expander(pod_name):
    df = df.sort_values(by=["points", "margin"], ascending=False)
    st.dataframe(df, use_container_width=True)
            def run_bracket_stage(players_df, supabase):
    st.subheader("\U0001F3C6 Bracket Stage")
    bracket_df = load_bracket_data_from_supabase(supabase)
    if bracket_df.empty:
    st.warning("Field of 16 not finalized yet.")
    return
        r16 = load_matches_by_stage(supabase, "r16")
    qf = load_matches_by_stage(supabase, "qf")
    sf = load_matches_by_stage(supabase, "sf")
    final = load_matches_by_stage(supabase, "final")
        col1, col2 = st.columns(2)
    if st.session_state.authenticated:
    with col1:
    render_stage_matches(r16, bracket_df, "r16")
    render_stage_matches(qf, bracket_df, "qf")
    with col2:
    render_stage_matches(sf, bracket_df, "sf")
    render_stage_matches(final, bracket_df, "final")
        st.graphviz_chart(visualize_bracket(r16, qf, sf, final))
        if st.button("Advance Bracket"):
    advance_round(r16, bracket_df, "qf", supabase)
    advance_round(qf, bracket_df, "sf", supabase)
    advance_round(sf, bracket_df, "final", supabase)
            def run_predictions_tab(supabase):
        st.subheader("🔮 Predict the Bracket")
    bracket_df = load_bracket_data_from_supabase(supabase)
    if bracket_df.empty:
    st.warning("Predictions available once field is set.")
    return
        left = bracket_df.iloc[0:8].reset_index(drop=True)
    right = bracket_df.iloc[8:16].reset_index(drop=True)
        full_name = st.text_input("Enter your full name:")
    if not full_name:
    st.stop()
        predictions = supabase.table("predictions").select("name").execute().data
    if has_user_submitted_prediction(full_name, predictions):
    st.warning("You already submitted a prediction.")
    return
        pred_r16_left = predict_round("R16 Left", left.to_dict("records"), f"PL16_{full_name}")
    pred_r16_right = predict_round("R16 Right", right.to_dict("records"), f"PR16_{full_name}")
    pred_qf_left = predict_round("QF Left", pred_r16_left, f"PLQF_{full_name}")
    pred_qf_right = predict_round("QF Right", pred_r16_right, f"PRQF_{full_name}")
    pred_sf_left = predict_round("SF Left", pred_qf_left, f"PLSF_{full_name}")
    pred_sf_right = predict_round("SF Right", pred_qf_right, f"PRSF_{full_name}")
        finalist_left = pred_sf_left[0]
    finalist_right = pred_sf_right[0]
    champ_pick = st.radio("\U0001F3C6 Champion", [finalist_left["name"], finalist_right["name"]], key=f"champ_{full_name}")
    champion = finalist_left if champ_pick == finalist_left["name"] else finalist_right
        if st.button("Submit Prediction"):
    save_user_prediction(supabase, full_name, finalist_left, finalist_right, champion,
    pred_r16_left, pred_r16_right, pred_qf_left, pred_qf_right)
    st.success("✅ Prediction submitted!")
            def show_leaderboard(supabase):
    st.subheader("\U0001F3C5 Leaderboard")
        predictions = supabase.table("predictions").select("*").execute().data
    final_result = supabase.table("final_results").select("*").order("created_at", desc=True).limit(1).execute().data
        if not predictions or not final_result:
    st.info("Waiting for predictions or final results.")
    return
        actual = final_result[0]
    actual_results = {
    "r16_left": json.loads(actual.get("r16_left", "[]")),
    "r16_right": json.loads(actual.get("r16_right", "[]")),
    "qf_left": json.loads(actual.get("qf_left", "[]")),
    "qf_right": json.loads(actual.get("qf_right", "[]")),
    "sf_left": json.loads(actual.get("sf_left", "[]")),
    "sf_right": json.loads(actual.get("sf_right", "[]")),
    "champion": actual.get("champion", "")
    }
        leaderboard = [
    {
    "Name": row["name"],
    "Score": score_prediction(row, actual_results),
    "Submitted At": row["timestamp"].replace("T", " ")[:19] + " UTC"
    }
    for row in predictions
    ]
        df = pd.DataFrame(leaderboard).sort_values(by=["Score", "Submitted At"], ascending=[False, True])
    df.insert(0, "Rank", range(1, len(df) + 1))
    st.dataframe(df, use_container_width=True)
            def show_how_it_works():
    st.header("\U0001F4D8 How It Works")
    st.markdown("""
    ### 🏌️ Tournament Format
    - Round Robin (Group Stage) → Bracket of 16
    - Single Elimination: R16 → QF → SF → Final
        ### 🧠 Prediction Scoring
    | Round      | Points |
    |------------|--------|
    | R16 Pick   | 1 pt   |
    | QF Pick    | 3 pts  |
    | SF Pick    | 5 pts  |
    | Champion   | 10 pts |
        - Correct position matters — picking a name in the wrong spot won’t earn points.
    - Tie goes to earlier submission.
    - You can only submit once.
    """)
    import streamlit as st
from supabase import create_client
import pandas as pd
import json
from datetime import datetime

from app_helpers import (
run_group_stage,
render_pod_table,
show_standings,
run_predictions_tab,
show_leaderboard,
show_how_it_works,
group_players_by_pod
)

from bracket_helpers import (
run_bracket_stage,
render_pod_matches,
compute_standings_from_results,
resolve_tiebreakers,
build_bracket_df_from_pod_scores,
save_bracket_data
)

# --- Config ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

# --- Supabase Init ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    supabase = init_supabase()

# --- Auth ---
admin_password = st.secrets["admin_password"]["password"]
general_password = st.secrets["general_password"]["password"]

# Initialize session state variables
if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
    if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Check if the user is authenticated
if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament Login")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == general_password:
            st.session_state.app_authenticated = True
            st.rerun()  # Refresh to show logged-in state
            else:
            st.error("Incorrect password.")
    st.stop()  # Stop further execution until the user is authenticated

# Sidebar Admin Login
st.sidebar.header("🔐 Admin Login")
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.rerun()  # Refresh to show logged-in state
            else:
            st.sidebar.error("Wrong password.")
            else:
                if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()  # Refresh to show logged-out state

# --- Tabs ---
tabs = st.tabs([
"📁 Pods Overview",
"📊 Group Stage",
"📋 Standings",
"🏆 Bracket",
"🔮 Predict Bracket",
"🏅 Leaderboard",
"📘 How It Works"
])

# --- Shared Data ---
players_response = supabase.table("players").select("*").execute()
players_df = pd.DataFrame(players_response.data)
pods = group_players_by_pod(players_df)

# --- Tab 0: Pods Overview ---
with tabs[0]:
    st.subheader("📁 Pods Overview")
    render_pod_table(players_df)
    st.subheader("📁 Pods Overview")
    render_pod_table(players_df)

# --- Tab 1: Group Stage ---
with tabs[1]:
    run_group_stage(pods, supabase)

# --- Tab 2: Standings ---
with tabs[2]:
    show_standings(pods, supabase)

# --- Tab 3: Bracket ---
with tabs[3]:
    run_bracket_stage(players_df, supabase)

# --- Tab 4: Predict Bracket ---
with tabs[4]:
    run_predictions_tab(supabase)

# --- Tab 5: Leaderboard ---
with tabs[5]:
    show_leaderboard(supabase)

# --- Tab 6: How It Works ---
with tabs[6]:
    show_how_it_works()
