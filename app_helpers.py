# app_helpers.py

import streamlit as st
from bracket_helpers import *
import pandas as pd


def run_group_stage(pods, supabase):
    """
    Run the group stage, simulate matches, show match entry UI, and save results.
    
    Args:
    - pods (dict): Dictionary of players grouped by pods.
    - supabase (object): The Supabase client.
    """
    st.subheader("📊 Group Stage - Match Entry")

    # Load match results from Supabase
    match_results = load_match_results(supabase)

    # Compute standings for each pod based on match results
    pod_scores = compute_pod_standings_from_results(pods, match_results)

    # Loop over each pod and simulate matches
    for pod_name, players in pods.items():
        with st.expander(pod_name):
            updated_players = simulate_matches(players, pod_name, source="group_stage", editable=st.session_state.authenticated)
            st.dataframe(pd.DataFrame(updated_players))

    # If the user is authenticated (admin), allow finalizing the bracket
    if st.session_state.authenticated:
        unresolved = resolve_tiebreakers(pod_scores)

        if not unresolved and st.button("Finalize Bracket Field"):
            # Build bracket from pod scores and tiebreaker selections
            bracket_df = build_bracket_df_from_pod_scores(pod_scores, st.session_state.tiebreak_selections)

            # Save the bracket data to Supabase
            save_bracket_data(bracket_df, supabase)
            
            # Success message after saving
            st.success("✅ Field of 16 saved!")


def load_match_results(supabase):
    """
    Load match results from Supabase.
    
    Args:
    - supabase (object): The initialized Supabase client.
    
    Returns:
    - pd.DataFrame: DataFrame containing match results.
    """
    try:
        # Fetch match results from the "tournament_matches" table in Supabase
        response = supabase.table("tournament_matches").select("*").execute()
        if response.data:
            match_results = pd.DataFrame(response.data)
            return match_results
        else:
            st.warning("No match results found.")
            return pd.DataFrame()  # Return an empty DataFrame if no data is found
    except Exception as e:
        st.error(f"Error loading match results: {e}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error

def show_pods_table(pods):
    for pod_name, players in pods.items():
        # Create a DataFrame for players in the pod
        pod_df = pd.DataFrame(players)
        
        # Ensure correct data structure: if players is a list of dicts
        if 'Name' not in pod_df.columns or 'Handicap' not in pod_df.columns:
            st.error("Data is missing 'Name' or 'Handicap' columns. Please check your data structure.")
            return

        # Format the "Handicap" column to 1 decimal place
        pod_df['Handicap'] = pod_df['Handicap'].apply(lambda x: f"{x:.1f}" if isinstance(x, (int, float)) else "N/A")

        # Styling for the table
        st.markdown(f"### 🏌️ Pod: {pod_name}")
        
        # Apply color styling to the table for visual appeal
        styled_table = pod_df.style.applymap(
            lambda val: 'background-color: lightblue;' if isinstance(val, str) else '',
            subset=['Name']
        ).applymap(
            lambda val: 'background-color: #f9f9f9;' if isinstance(val, str) else '',
            subset=['Handicap']
        ).set_table_styles([
            {'selector': 'thead th', 'props': [('background-color', '#1f77b4'), ('color', 'white'), ('text-align', 'center')]},
            {'selector': 'tbody td', 'props': [('text-align', 'center')]},
        ])

        # Display the styled dataframe
        st.dataframe(styled_table)


def group_players_by_pod(players_df):
    """
    Groups players by the 'pod' field in the players DataFrame.
    
    Args:
    - players_df (DataFrame): DataFrame of players with at least a 'pod' column.
    
    Returns:
    - dict: A dictionary where keys are pod names and values are lists of player records.
    """
    pods = players_df.groupby("pod").apply(lambda x: x.to_dict(orient="records")).to_dict()
    return pods


def show_standings(pods, supabase):
    st.subheader("📋 Group Stage Standings")
    match_results = load_match_results(supabase)
    pod_scores = compute_pod_standings_from_results(pods, match_results)

    for pod_name, df in pod_scores.items():
        with st.expander(pod_name):
            df = df.sort_values(by=["points", "margin"], ascending=False)
            st.dataframe(df, use_container_width=True)

def run_bracket_stage(players_df, supabase):
    st.subheader("🏆 Bracket Stage")
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
    from bracket_helpers import predict_round, save_user_prediction
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

    # Check for existing submission
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
    champ_pick = st.radio("🏆 Champion", [finalist_left["name"], finalist_right["name"]], key=f"champ_{full_name}")
    champion = finalist_left if champ_pick == finalist_left["name"] else finalist_right

    if st.button("Submit Prediction"):
        save_user_prediction(supabase, full_name, finalist_left, finalist_right, champion,
                             pred_r16_left, pred_r16_right, pred_qf_left, pred_qf_right)
        st.success("✅ Prediction submitted!")

def show_leaderboard(supabase):
    from bracket_helpers import score_prediction

    st.subheader("🏅 Leaderboard")
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

    leaderboard = []
    for row in predictions:
        leaderboard.append({
            "Name": row["name"],
            "Score": score_prediction(row, actual_results),
            "Submitted At": row["timestamp"].replace("T", " ")[:19] + " UTC"
        })

    df = pd.DataFrame(leaderboard).sort_values(by=["Score", "Submitted At"], ascending=[False, True])
    df.insert(0, "Rank", range(1, len(df) + 1))
    st.dataframe(df, use_container_width=True)

def show_how_it_works():
    st.header("📘 How It Works")

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
