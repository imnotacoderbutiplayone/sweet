import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

st.title("🏌️ Golf Score Probability Calculator")

handicap_index = st.number_input("Handicap Index", value=10.0)
course_rating = st.number_input("Course Rating", value=72.0)
slope_rating = st.number_input("Slope Rating", value=132.0)
actual_score = st.number_input("Actual Score", value=85.0)

if st.button("Calculate"):
    course_handicap = handicap_index * (slope_rating / 113) + (course_rating - 72)
    expected_score = course_handicap + 72 + 2.5
    std_dev = 2.5

    probability_better = stats.norm.cdf(actual_score, loc=expected_score, scale=std_dev)
    probability_worse = 1 - probability_better

    st.markdown(f"### Results:")
    st.write(f"**Expected Score:** {expected_score:.1f}")
    st.write(f"**Probability of Better Score:** {probability_better*100:.2f}%")
    st.write(f"**Probability of Worse Score:** {probability_worse*100:.2f}%")

    # Plotting
    scores = np.linspace(expected_score - 3*std_dev, expected_score + 3*std_dev, 100)
    prob_density = stats.norm.pdf(scores, expected_score, std_dev)

    fig, ax = plt.subplots()
    ax.plot(scores, prob_density, label="Expected Score Distribution", linewidth=2)
    ax.axvline(actual_score, color="red", linestyle="--", label=f"Actual Score: {actual_score}")
    ax.axvline(expected_score, color="blue", linestyle="--", label=f"Expected Score: {expected_score:.1f}")
    ax.fill_between(scores, prob_density, where=(scores >= actual_score), color='red', alpha=0.3, label="Worse Score Probability")
    ax.fill_between(scores, prob_density, where=(scores <= actual_score), color='green', alpha=0.3, label="Better Score Probability")
    ax.set_xlabel("Score")
    ax.set_ylabel("Probability Density")
    ax.set_title("Golf Score Probability Distribution")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
