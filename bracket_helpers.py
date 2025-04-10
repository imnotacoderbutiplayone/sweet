# bracket_helpers.py (Cleaned and Modular)
import graphviz
from datetime import datetime
import streamlit as st
from app_helpers import render_match, get_winner_player, sanitize_key
from ui_helpers import sanitize_key, render_match, get_winner_player
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
    from app_helpers import sanitize_key, render_match  # make sure this works

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
