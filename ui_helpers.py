# ui_helpers.py

import streamlit as st

def sanitize_key(s):
    return s.replace(" ", "_").replace("|", "_").replace(":", "_")

def render_match(p1, p2, default="Tie", readonly=False, key_prefix="", stage=""):
    options = [p1["name"], p2["name"], "Tie"]
    return st.radio(
        f"{p1['name']} vs {p2['name']}",
        options,
        index=options.index(default) if default in options else 2,
        key=f"{key_prefix}_{stage}"
    )

def get_winner_player(p1, p2, winner_name):
    if winner_name == p1["name"]:
        return p1
    elif winner_name == p2["name"]:
        return p2
    else:
        return {"name": "Tie"}
