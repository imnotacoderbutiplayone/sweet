import tkinter as tk
from tkinter import messagebox
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats

# Function to calculate and display results
def calculate_probability():
    try:
        handicap_index = float(entry_handicap.get())
        course_rating = float(entry_course_rating.get())
        slope_rating = float(entry_slope.get())
        actual_score = float(entry_actual_score.get())
        
        # Calculate Course Handicap
        course_handicap = handicap_index * (slope_rating / 113) + (course_rating - 72)
        
        # Calculate Expected Score
        expected_score = course_handicap + 72 + 2.5  # 2.5 stroke adjustment factor
        
        # Standard deviation assumption
        std_dev = 2.5  # Average round variability
        
        # Calculate Probability
        probability_better = stats.norm.cdf(actual_score, loc=expected_score, scale=std_dev)
        probability_worse = 1 - probability_better
        
        # Display results
        result_label.config(text=f"Expected Score: {expected_score:.1f}\nProbability of Better Score: {probability_better*100:.2f}%\nProbability of Worse Score: {probability_worse*100:.2f}%")
        
        # Generate distribution graph
        plot_distribution(expected_score, std_dev, actual_score)
    except ValueError:
        messagebox.showerror("Input Error", "Please enter valid numerical values for all fields.")

# Function to plot the probability distribution
def plot_distribution(expected_score, std_dev, actual_score):
    scores = np.linspace(expected_score - 3*std_dev, expected_score + 3*std_dev, 100)
    prob_density = stats.norm.pdf(scores, expected_score, std_dev)
    
    plt.figure(figsize=(8,5))
    plt.plot(scores, prob_density, label="Expected Score Distribution", linewidth=2)
    plt.axvline(actual_score, color="red", linestyle="--", label=f"Actual Score: {actual_score}")
    plt.axvline(expected_score, color="blue", linestyle="--", label=f"Expected Score: {expected_score:.1f}")
    
    plt.fill_between(scores, prob_density, where=(scores >= actual_score), color='red', alpha=0.3, label="Worse Score Probability")
    plt.fill_between(scores, prob_density, where=(scores <= actual_score), color='green', alpha=0.3, label="Better Score Probability")
    
    plt.xlabel("Score")
    plt.ylabel("Probability Density")
    plt.title("Golf Score Probability Distribution")
    plt.legend()
    plt.grid()
    plt.show()

# Create GUI
root = tk.Tk()
root.title("Golf Score Probability Calculator")

# Labels and entry fields
tk.Label(root, text="Handicap Index:").grid(row=0, column=0)
entry_handicap = tk.Entry(root)
entry_handicap.grid(row=0, column=1)

tk.Label(root, text="Course Rating:").grid(row=1, column=0)
entry_course_rating = tk.Entry(root)
entry_course_rating.grid(row=1, column=1)

tk.Label(root, text="Slope Rating:").grid(row=2, column=0)
entry_slope = tk.Entry(root)
entry_slope.grid(row=2, column=1)

tk.Label(root, text="Actual Score:").grid(row=3, column=0)
entry_actual_score = tk.Entry(root)
entry_actual_score.grid(row=3, column=1)

# Calculate Button
tk.Button(root, text="Calculate", command=calculate_probability).grid(row=4, column=0, columnspan=2)

# Result Label
result_label = tk.Label(root, text="", justify=tk.LEFT)
result_label.grid(row=5, column=0, columnspan=2)

# Run the GUI
root.mainloop()
