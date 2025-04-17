
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import truncnorm

st.set_page_config(page_title="Golf Probability Forecaster", layout="centered")  # Mobile-optimized
st.title("\U0001F3CC️ Golf Probability Forecaster")
st.markdown("Enter your golf stats to calculate the probability of your score.")

# Course data
courses = {
    "Cypress": {
        "yardages": [367, 355, 504, 164, 366, 539, 125, 387, 346, 338, 525, 398, 353, 128, 418, 163, 397, 426],
        "handicaps": [7, 13, 11, 15, 1, 5, 17, 3, 9, 10, 12, 4, 14, 18, 2, 16, 8, 6],
        "pars": [4, 4, 5, 3, 4, 5, 3, 4, 4, 4, 5, 4, 4, 3, 4, 3, 4, 5],
        "slope": 130,
        "rating": 71.3
    },
    "Pecan": {
        "yardages": [349, 488, 328, 179, 420, 539, 167, 396, 437, 375, 542, 358, 137, 353, 480, 189, 424, 388],
        "handicaps": [7, 17, 11, 15, 5, 1, 13, 9, 3, 8, 6, 14, 16, 10, 18, 12, 4, 2],
        "pars": [4, 5, 4, 3, 4, 5, 3, 4, 4, 4, 5, 4, 3, 4, 5, 3, 4, 4],
        "slope": 132,
        "rating": 72.0
    }
}

mode = st.radio("Choose Format", ["Stroke Play", "Match Play"], horizontal=True)
course_choice = st.selectbox("Select Course", list(courses.keys()))
hole_handicaps = courses[course_choice]["handicaps"]
hole_pars = courses[course_choice]["pars"]
slope_rating = courses[course_choice]["slope"]
course_rating = courses[course_choice]["rating"]

st.markdown(f"**Slope Rating:** {slope_rating} &nbsp;&nbsp; **Course Rating:** {course_rating}")

if mode == "Match Play":
    player_a_name = st.text_input("Player A Name", "Player A")
    player_b_name = st.text_input("Player B Name", "Player B")
else:
    player_a_name = "You"
    player_b_name = "Opponent"

col1, col2 = st.columns(2)
with col1:
    handicap_index_1 = st.number_input(f"{player_a_name} Handicap Index", min_value=-10.0, max_value=40.0, value=0.0, step=0.1)
with col2:
    if mode == "Stroke Play":
        actual_score = st.number_input("Actual Score", min_value=40.0, max_value=150.0, step=0.1, value=72.0)
    else:
        handicap_index_2 = st.number_input(f"{player_b_name} Handicap Index", min_value=-10.0, max_value=40.0, value=10.0, step=0.1)

def get_std_dev(handicap_index):
    return [2.5, 3.5, 4.5, 5.5, 6.5][min(int(handicap_index // 5), 4)]

def get_hole_std_dev(handicap_index):
    return [0.6, 0.8, 1.0, 1.2, 1.4][min(int(handicap_index // 5), 4)]

def simulate_hole_score(par, handicap_index):
    mean_score = par + (handicap_index / 18.0)
    std_dev = get_hole_std_dev(handicap_index)
    lower, upper = par - 1, par + 4
    a = (lower - mean_score) / std_dev
    b = (upper - mean_score) / std_dev
    dist = truncnorm(a, b, loc=mean_score, scale=std_dev)
    return round(dist.rvs())

def allocate_strokes(h1, h2, hole_handicaps):
    diff = int(round(h1 - h2))
    strokes = [0] * 18
    if diff > 0:
        sorted_holes = sorted(range(18), key=lambda x: hole_handicaps[x])
        for i in range(diff):
            strokes[sorted_holes[i % 18]] += 1
    return strokes

def simulate_match_play(pars, hole_handicaps, hcp1, hcp2):
    strokes_p1 = allocate_strokes(hcp1, hcp2, hole_handicaps)
    strokes_p2 = allocate_strokes(hcp2, hcp1, hole_handicaps)
    holes, p1_wins, p2_wins = [], 0, 0
    match_result = "All Square"

    for i in range(18):
        p1_score = simulate_hole_score(pars[i], hcp1) - strokes_p1[i]
        p2_score = simulate_hole_score(pars[i], hcp2) - strokes_p2[i]

        if p1_score < p2_score:
            result = f"{player_a_name} wins"
            p1_wins += 1
        elif p2_score < p1_score:
            result = f"{player_b_name} wins"
            p2_wins += 1
        else:
            result = "Halved"

        holes.append({
            "Hole": i+1,
            "Par": pars[i],
            "HCP": hole_handicaps[i],
            f"{player_a_name} Gross": p1_score + strokes_p1[i],
            f"{player_b_name} Gross": p2_score + strokes_p2[i],
            f"{player_a_name} Net": p1_score,
            f"{player_b_name} Net": p2_score,
            f"{player_a_name} Strokes": strokes_p1[i],
            f"{player_b_name} Strokes": strokes_p2[i],
            "Result": result
        })

        lead = p1_wins - p2_wins
        holes_remaining = 17 - i
        if abs(lead) > holes_remaining:
            match_result = f"{player_a_name if lead > 0 else player_b_name} wins {abs(lead)}&{holes_remaining}"

            for j in range(i + 1, 18):
                holes.append({
                    "Hole": j + 1,
                    "Par": pars[j],
                    "HCP": hole_handicaps[j],
                    f"{player_a_name} Gross": "X",
                    f"{player_b_name} Gross": "X",
                    f"{player_a_name} Net": "X",
                    f"{player_b_name} Net": "X",
                    f"{player_a_name} Strokes": "X",
                    f"{player_b_name} Strokes": "X",
                    "Result": "Match Over"
                })
            break

    if abs(p1_wins - p2_wins) <= 0:
        match_result = "All Square"

    return holes, match_result

def highlight_match_over(val):
    if val == "X" or val == "Match Over":
        return "color: gray; font-style: italic;"
    return ""

if st.button("Calculate Probability", key="calc_prob_1"):
    if mode == "Match Play":
        holes, result = simulate_match_play(hole_pars, hole_handicaps, handicap_index_1, handicap_index_2)
        # Show cumulative win probabilities before scorecard
        total = len(sim_results)
        win_counts = {
            player_a_name: sum(1 for r in sim_results if r.startswith(player_a_name)),
            player_b_name: sum(1 for r in sim_results if r.startswith(player_b_name)),
            "All Square": sum(1 for r in sim_results if r == "All Square")
        }

        st.markdown("### 🧮 Cumulative Win Probabilities")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label=f"{player_a_name} Wins", value=f"{win_counts[player_a_name] / total * 100:.1f}%")
        with col2:
            st.metric(label=f"{player_b_name} Wins", value=f"{win_counts[player_b_name] / total * 100:.1f}%")
        with col3:
            st.metric(label="All Square", value=f"{win_counts['All Square'] / total * 100:.1f}%")
        st.success(f"Match Result: {result}")
        df = pd.DataFrame(holes).set_index("Hole").T
        styled_df = df.style.applymap(highlight_match_over)
        st.dataframe(styled_df, use_container_width=True)
        st.caption("‘X’ indicates holes not played due to early match conclusion.")
# Additional: Run multiple simulations to estimate outcome probabilities
        sim_results = []
        for _ in range(1000):
            _, sim_result = simulate_match_play(hole_pars, hole_handicaps, handicap_index_1, handicap_index_2)
            sim_results.append(sim_result)

        result_counts = pd.Series(sim_results).value_counts().reset_index()
        result_counts.columns = ["Match Result", "Frequency"]
        result_counts["Probability"] = (result_counts["Frequency"] / len(sim_results) * 100).round(2)

        
# Cumulative win probabilities
        total = len(sim_results)
        win_counts = {
            player_a_name: sum(1 for r in sim_results if r.startswith(player_a_name)),
            player_b_name: sum(1 for r in sim_results if r.startswith(player_b_name)),
            "All Square": sum(1 for r in sim_results if r == "All Square")
        }

        st.markdown("### 🧮 Cumulative Win Probabilities")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label=f"{player_a_name} Wins", value=f"{win_counts[player_a_name] / total * 100:.1f}%")
        with col2:
            st.metric(label=f"{player_b_name} Wins", value=f"{win_counts[player_b_name] / total * 100:.1f}%")
        with col3:
            st.metric(label="All Square", value=f"{win_counts['All Square'] / total * 100:.1f}%")

        # Hole-by-hole win heatmap: count wins per hole
        win_holes_p1 = np.zeros(18)
        win_holes_p2 = np.zeros(18)

        for _ in range(1000):
            holes, result = simulate_match_play(hole_pars, hole_handicaps, handicap_index_1, handicap_index_2)
            for hole in holes:
                if hole["Result"] == f"{player_a_name} wins":
                    if isinstance(hole["Hole"], int):
                        win_holes_p1[hole["Hole"] - 1] += 1
                elif hole["Result"] == f"{player_b_name} wins":
                    if isinstance(hole["Hole"], int):
                        win_holes_p2[hole["Hole"] - 1] += 1

        win_df = pd.DataFrame({
            "Hole": np.arange(1, 19),
            f"{player_a_name} Wins": win_holes_p1,
            f"{player_b_name} Wins": win_holes_p2
        })

        with st.expander("🔁 Match Result Probabilities Table & Heatmap"):
        st.markdown("### 🔥 Hole-by-Hole Win Heatmap (across 1,000 simulations)")
        st.bar_chart(win_df.set_index("Hole"))
        st.markdown("### 📋 Full Match Result Table")
        st.dataframe(result_counts, use_container_width=True)

    else:
        course_handicap = handicap_index_1 * (slope_rating / 113)
        expected_score = course_rating + course_handicap
        std_dev = get_std_dev(handicap_index_1)
        lower_bound = expected_score - 8
        upper_bound = expected_score + 25
        a = (lower_bound - expected_score) / std_dev
        b = (upper_bound - expected_score) / std_dev
        dist = truncnorm(a, b, loc=expected_score, scale=std_dev)
        probability_better = dist.cdf(actual_score)
        percentile = round(probability_better * 100, 1)

        st.success(f"Expected Score: **{expected_score:.1f}**")
        comparison = "better" if actual_score < expected_score else "worse"
        st.markdown(f"Your actual score of **{actual_score:.1f}** is {comparison} than **{percentile}%** of expected rounds.")

        scores = list(range(int(expected_score - 5), int(expected_score + 10)))
        probs = dist.pdf(scores)
        fig, ax = plt.subplots()
        ax.bar(scores, probs, width=0.8)
        ax.axvline(actual_score, color='red', linestyle='--', label='Your Score')
        ax.set_title("Probability Distribution of Scores")
        ax.set_xlabel("Score")
        ax.set_ylabel("Probability")
        ax.legend()
        st.pyplot(fig)
