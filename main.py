# tournament_app.py
import streamlit as st
import pandas as pd
import json
from supabase import create_client
from datetime import datetime
import graphviz
from collections import defaultdict

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
    return {"name": "Tie"}

def safe_name(name):
    return name if name and name != "" else "?"

def get_player_by_name(name, df):
    return next((p for p in df.to_dict("records") if p["name"] == name), {"name": name, "handicap": "N/A"})

def get_winner_name(match):
    return match.get("winner") if match.get("winner") and match["winner"] != "Tie" else ""

# --- Bracket Stage Functions ---
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
            "match_index": i // 2, "stage": next_stage,
            "winner": "", "margin": 0
        }
        supabase.table("tournament_matches").insert(update).execute()

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
    margin_lookup = {"1 up": 1, "2&1": 2, "3&2": 3, "4&3": 4, "5&4": 5}
    if len(players) < 2:
        st.warning(f"Not enough players in {pod_name} to generate matches.")
        return session_results
    st.markdown(f"<h3 style='color:#1f77b4'>📋 {pod_name}</h3>", unsafe_allow_html=True)
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
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
                    selected_winner = render_match(p1, p2, winner, readonly=False, key_prefix=base_key, stage="group_stage")
                    session_results[match_key] = {"winner": selected_winner, "margin": margin_lookup.get(margin_str, 0)}
            else:
                st.info(f"🔒 Admin login required to score matches in {pod_name}")
    return session_results

def compute_standings_from_results(pods, match_results):
    pod_scores = {}
    for pod_name, players in pods.items():
        records = []
        for player in players:
            name = player["name"]
            points = margin = 0
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
            records.append({"name": name, "handicap": player["handicap"], "points": points, "margin": margin})
        pod_scores[pod_name] = pd.DataFrame(records)
    return pod_scores

# --- App Helpers ---
def run_group_stage(pods, supabase):
    st.subheader("📊 Group Stage - Match Entry")
    if "group_stage_results" not in st.session_state:
        st.session_state.group_stage_results = load_match_results(supabase)
    for pod_name, players in pods.items():
        with st.expander(pod_name, expanded=True):
            st.session_state.group_stage_results = render_pod_matches(
                pod_name, players, st.session_state.authenticated, st.session_state.group_stage_results
            )

def render_pod_table(pods_df):
    grouped = pods_df.groupby("pod")
    sorted_pods = sorted(grouped, key=lambda x: int(x[0].split()[-1]))
    for pod_name, pod_group in sorted_pods:
        pod_group = pod_group.sort_values(by="handicap", ascending=True)
        pod_group["handicap"] = pod_group["handicap"].apply(lambda x: round(x, 1) if pd.notna(x) else "N/A")
        st.markdown(f"<h3 style='color:#1f77b4;'>\U0001F3CC️ {pod_name}</h3>", unsafe_allow_html=True)
        rows_html = "".join(f"<tr><td>{row.get('name', 'N/A')}</td><td>{row.get('handicap', 'N/A')}</td></tr>"
                           for _, row in pod_group.iterrows())
        table_html = f"""
        <style>
        .styled-table {{border-collapse: collapse; margin: 10px 0; font-size: 16px; width: 100%; box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);}}
        .styled-table th {{background-color: #1f77b4; color: white; text-align: left; padding: 8px;}}
        .styled-table td {{padding: 8px; border-bottom: 1px solid #ddd;}}
        .styled-table tr:nth-child(even) {{background-color: #f2f2f2;}}
        </style>
        <table class="styled-table"><thead><tr><th>Name</th><th>Handicap</th></tr></thead><tbody>{rows_html}</tbody></table>
        """
        st.markdown(table_html, unsafe_allow_html=True)

def load_match_results(supabase):
    try:
        response = supabase.table("tournament_matches").select("*").execute()
        if response.data:
            return {row.get("match_key") or f"{row['pod']}|{row['player1']} vs {row['player2']}": 
                    {"winner": row.get("winner", "Tie"), "margin": row.get("margin", 0)} 
                    for row in response.data}
        st.warning("No match results found.")
        return {}
    except Exception as e:
        st.error(f"Error loading match results: {e}")
        return {}

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
        st.graphviz livello_chart(visualize_bracket(r16, qf, sf, final))
        if st.button("Advance Bracket"):
            advance_round(r16, bracket_df, "qf", supabase)
            advance_round(qf, bracket_df, "sf", supabase)
            advance_round(sf, bracket_df, "final", supabase)

# --- Placeholder Functions (to be implemented) ---
def load_bracket_data_from_supabase(supabase):
    # Placeholder - Replace with actual Supabase query
    return pd.DataFrame()  # Return empty DataFrame for now

def load_matches_by_stage(supabase, stage):
    # Placeholder - Replace with actual Supabase query
    return []  # Return empty list for now

def predict_round(round_name, players, key_prefix):
    # Placeholder - Replace with actual prediction logic
    return players[:len(players)//2]  # Dummy return for now

def has_user_submitted_prediction(full_name, predictions):
    return any(pred["name"] == full_name for pred in predictions)

def save_user_prediction(supabase, full_name, finalist_left, finalist_right, champion, *args):
    # Placeholder - Replace with actual Supabase insert
    pass

def score_prediction(row, actual_results):
    # Placeholder - Replace with actual scoring logic
    return 0  # Dummy return for now

# --- Main App ---
st.set_page_config(page_title="Golf Match Play Tournament", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_supabase()
admin_password = st.secrets["admin_password"]["password"]
general_password = st.secrets["general_password"]["password"]

if 'app_authenticated' not in st.session_state:
    st.session_state.app_authenticated = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.app_authenticated:
    st.title("🔐 Golf Tournament Login")
    pwd = st.text_input("Enter Tournament Password:", type="password")
    if st.button("Enter"):
        if pwd == general_password:
            st.session_state.app_authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

st.sidebar.header("🔐 Admin Login")
if not st.session_state.authenticated:
    pwd_input = st.sidebar.text_input("Admin Password", type="password")
    if st.sidebar.button("Login"):
        if pwd_input == admin_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.sidebar.error("Wrong password.")
else:
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

tabs = st.tabs(["📁 Pods Overview", "📊 Group Stage", "📋 Standings", "🏆 Bracket", 
                "🔮 Predict Bracket", "🏅 Leaderboard", "📘 How It Works"])

players_response = supabase.table("players").select("*").execute()
players_df = pd.DataFrame(players_response.data)
pods = group_players_by_pod(players_df)

with tabs[0]:
    st.subheader("📁 Pods Overview")
    render_pod_table(players_df)

with tabs[1]:
    run_group_stage(pods, supabase)

with tabs[2]:
    show_standings(pods, supabase)

with tabs[3]:
    run_bracket_stage(players_df, supabase)

with tabs[4]:
    st.subheader("🔮 Predict the Bracket")
    # Add run_predictions_tab(supabase) when implemented

with tabs[5]:
    st.subheader("\U0001F3C5 Leaderboard")
    # Add show_leaderboard(supabase) when implemented

with tabs[6]:
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
