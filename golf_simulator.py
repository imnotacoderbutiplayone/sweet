import streamlit as st
import numpy as np
from collections import Counter
import matplotlib.pyplot as plt

st.set_page_config(page_title="Golf Duel Simulator", layout="centered")

# --- Style ---
st.markdown("""
    <style>
        .main { background-color: #f7f7f7; }
        .block-container { padding-top: 2rem; }
        h1, h2, h3, h4, h5, h6 { color: #004d00; }
        .stButton>button {
            background-color: #2e7d32;
            color: white;
            font-weight: bold;
        }
        .stRadio>div>label { font-weight: bold; }
        .stMetric label, .stMetric div { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# --- Functions ---
def analyze_scores(scores):
    avg = np.mean(scores)
    std_dev = np.std(scores, ddof=1)
    return avg, std_dev

def compute_course_handicap(handicap_index, slope, course_rating):
    return handicap_index * (slope / 113) + (course_rating - 72)

def assign_strokes(hcp1, hcp2):
    strokes = abs(round(hcp1 - hcp2))
    return np.array([1 if i < strokes else 0 for i in range(18)])

def simulate_matchplay(player1, player2, simulations=10000):
    results = {'P1 Wins': 0, 'P2 Wins': 0, 'Ties': 0}
    margins = Counter()
    for _ in range(simulations):
        p1_scores = np.random.normal(player1['avg'] / 18, player1['std'] / np.sqrt(18), 18)
        p2_scores = np.random.normal(player2['avg'] / 18, player2['std'] / np.sqrt(18), 18)
        p1_net = p1_scores - player1['strokes']
        p2_net = p2_scores - player2['strokes']
        match_score = 0
        holes_remaining = 18
        for h in range(18):
            holes_remaining -= 1
            if p1_net[h] < p2_net[h]:
                match_score += 1
            elif p2_net[h] < p1_net[h]:
                match_score -= 1
            if abs(match_score) > holes_remaining:
                break
        if match_score > 0:
            results['P1 Wins'] += 1
            margins[f"{abs(match_score)}&{holes_remaining + 1}"] += 1
        elif match_score < 0:
            results['P2 Wins'] += 1
            margins[f"{abs(match_score)}&{holes_remaining + 1}"] += 1
        else:
            results['Ties'] += 1
    results['Margins'] = margins
    return results

def simulate_strokeplay(player1, player2, simulations=10000):
    results = {'P1 Wins': 0, 'P2 Wins': 0, 'Ties': 0}
    for _ in range(simulations):
        p1_total = np.random.normal(player1['avg'], player1['std']) - np.sum(player1['strokes'])
        p2_total = np.random.normal(player2['avg'], player2['std']) - np.sum(player2['strokes'])
        if p1_total < p2_total:
            results['P1 Wins'] += 1
        elif p2_total < p1_total:
            results['P2 Wins'] += 1
        else:
            results['Ties'] += 1
    return results

def plot_win_chart(results, p1_name, p2_name):
    labels = [f"{p1_name} Wins", f"{p2_name} Wins", "Ties"]
    sizes = [results['P1 Wins'], results['P2 Wins'], results['Ties']]
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    st.pyplot(fig)

# --- Streamlit UI ---
st.title("🏌️ Golf Duel Simulator")
st.markdown("""
    <h4>🎯 Enter two players' data to simulate a net match play or stroke play duel.</h4>
""", unsafe_allow_html=True)

with st.form("player_input"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Player 1")
        p1_name = st.text_input("Name", "Player 1")
        p1_index_input = st.text_input("Player 1 Handicap Index (e.g., 12.5)")
        p1_index = float(p1_index_input) if p1_index_input else None
        p1_scores_input = st.text_input("Player 1 Last 10 Scores (comma-separated)")
        try:
            p1_scores = [float(s.strip()) for s in p1_scores_input.split(',') if s.strip()]
        except ValueError:
            p1_scores = []
            st.warning("Player 1 scores must be numbers separated by commas.")
    with col2:
        st.subheader("Player 2")
        p2_name = st.text_input("Name", "Player 2")
        p2_index_input = st.text_input("Player 2 Handicap Index (e.g., 10.0)")
        p2_index = float(p2_index_input) if p2_index_input else None
        p2_scores_input = st.text_input("Player 2 Last 10 Scores (comma-separated)")
        try:
            p2_scores = [float(s.strip()) for s in p2_scores_input.split(',') if s.strip()]
        except ValueError:
            p2_scores = []
            st.warning("Player 2 scores must be numbers separated by commas.")

    st.subheader("Course Setup")
    course_rating = st.number_input("Course Rating", value=72.0)
    slope_rating = st.number_input("Slope Rating", value=130)
    play_format = st.radio("Play Format", ["Match Play", "Stroke Play"], index=0)

    submitted = st.form_submit_button("🚀 Simulate Match")




if submitted:
    try:
        p1_scores = [float(x.strip()) for x in p1_scores.split(",") if x.strip()]
        p2_scores = [float(x.strip()) for x in p2_scores.split(",") if x.strip()]
        if len(p1_scores) < 2 or len(p2_scores) < 2:
            st.error("Please enter at least 2 scores per player.")
        else:
            p1_avg, p1_std = analyze_scores(p1_scores)
            p2_avg, p2_std = analyze_scores(p2_scores)
            p1_course_hcp = compute_course_handicap(p1_index, slope_rating, course_rating)
            p2_course_hcp = compute_course_handicap(p2_index, slope_rating, course_rating)
            if p1_course_hcp > p2_course_hcp:
                p1_strokes = assign_strokes(p1_course_hcp, p2_course_hcp)
                p2_strokes = np.zeros(18)
            else:
                p2_strokes = assign_strokes(p2_course_hcp, p1_course_hcp)
                p1_strokes = np.zeros(18)
            player1 = {'name': p1_name, 'avg': p1_avg, 'std': p1_std, 'strokes': p1_strokes}
            player2 = {'name': p2_name, 'avg': p2_avg, 'std': p2_std, 'strokes': p2_strokes}
            if play_format == "Match Play":
                results = simulate_matchplay(player1, player2)
            else:
                results = simulate_strokeplay(player1, player2)
            st.success("✅ Simulation complete!")
            col1, col2, col3 = st.columns(3)
            col1.metric(f"{p1_name} Wins", f"{results['P1 Wins'] / 100:.1f}%")
            col2.metric(f"{p2_name} Wins", f"{results['P2 Wins'] / 100:.1f}%")
            col3.metric("Tied Matches", f"{results['Ties'] / 100:.1f}%")
            st.subheader("📊 Win Probability Chart")
            plot_win_chart(results, p1_name, p2_name)
            if play_format == "Match Play" and 'Margins' in results:
                st.subheader("🏁 Match Play Margin of Victory")
                import pandas as pd
                margin_data = results['Margins'].items()
                sorted_margins = sorted(margin_data, key=lambda x: (int(x[0].split('&')[1]), int(x[0].split('&')[0])))
                df_margins = pd.DataFrame(sorted_margins, columns=["Margin", "Count"])
                df_margins["Frequency"] = df_margins["Count"] / 100
                st.dataframe(df_margins.style.format({"Frequency": "{:.1f}%"}))
                st.bar_chart(df_margins.set_index("Margin")["Count"])
    except Exception as e:
        st.error(f"Error processing input: {e}")
